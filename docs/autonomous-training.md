# Reentrenamiento y recomendaciones autónomos

## Flujo implementado

El worker ejecuta tres jobs durables. La ingesta mantiene el histórico; el job
`model-training` crea snapshots y comprueba si puede entrenar candidatos; el job
`crop-recommendations` utiliza únicamente versiones publicadas. Las peticiones
FastAPI consultan resultados almacenados y no disparan ninguno de estos jobs.

Los horizontes iniciales son 7, 15, 30 y 60 días, con slots independientes
`<region_id>:<climate|soil>:<horizon>`. Cada slot conserva su campeón hasta que
otro candidato supere todos los criterios. La revisión diaria de entrenamiento
no implica publicar un modelo diariamente ni cada siete días.

## Conectar un experimento real

El punto de composición es `scripts/runtime.py::build_jobs`. Sus dependencias
opcionales permiten agregar implementaciones verificadas sin alterar el scheduler,
el frontend o los clientes NASA:

1. `TrainingDatasetBuilder`: recibe el snapshot y el archivo Parquet completo.
   Devuelve `PreparedDataset`, con receta versionada, features ordenadas, targets
   y unidades, baseline y muestras fechadas. Cada muestra identifica las fuentes
   de sus etiquetas y confirma que fueron verificadas. No se admite una etiqueta
   cuyo resultado real todavía no exista.
2. `CandidateTrainer`: implementa `fit` y `load`. El adapter `XGBoostTrainer` ya
   entrena un Booster por target y guarda modelos JSON. Se configura con versión,
   hiperparámetros e iteraciones explícitos; no viene conectado a targets
   agrícolas inventados.
3. `TrainingPolicy` por modelo/horizonte: mínimos de muestras y etiquetas nuevas,
   extensión de validación, mejora relativa mínima y límites MAE por target.
   Los límites deben usar las unidades de cada target y una justificación de
   evaluación. El valor inicial `max_mae={}` deshabilita la publicación.
4. `PublishedPredictorFactory`: carga las versiones publicadas y aplica la misma
   receta/preprocesamiento de entrenamiento para producir el contrato `Forecast`.
   Los Boosters de bajo nivel no pueden reemplazar por sí solos ese adapter.
5. `RecommendationEngine`: aplica requisitos agronómicos revisados y rotaciones.
   La salida debe identificar `engine_version` y `catalog_version`. La revisión
   del catálogo participa en la identidad del resultado, aunque el código del
   motor no haya cambiado.

El registro de modelos se selecciona automáticamente según `RESULTS_BACKEND`.
El constructor de datasets debe limitarse al scope autorizado. La subida de un
CSV por un agricultor no autoriza mezclar sus datos con los de otros usuarios.
La interfaz `FarmContextProvider` continúa disponible para un futuro modelo
privado, después de validar y alinear esas mediciones.

## Validación y publicación

- Solo se aceptan targets finitos con procedencia y etiquetas verificadas.
  `feature_date < label_start <= label_end <= label_available_on <= cutoff`.
- La validación es el tramo temporal final, sin barajar muestras. Se purgan las
  muestras de entrenamiento cuyas etiquetas alcancen las fechas de entrada de
  validación. Una tarea incluye una muestra regional por fecha y un horizonte
  exacto; no se mezclan parcelas bajo esa misma identidad.
- Candidato, baseline y campeón se evalúan sobre las mismas muestras. No se
  compara el MAE histórico del campeón en otro periodo con el MAE actual del
  candidato. Las métricas se calculan desde sus predicciones, no se confía en
  métricas proporcionadas por un trainer.
- Cada target debe respetar su error máximo y mejorar al baseline. Si existe un
  campeón, también debe mejorarlo por el margen configurado. Un empate conserva
  el campeón. No se publica si un target mejora y otro incumple los criterios.
- Un cambio de esquema o receta requiere migrar explícitamente el adapter de
  comparación; no se reinterpretan las features del campeón con otra semántica.
- Features, targets y baseline exactos se guardan en Parquet. Los artefactos JSON
  se guardan antes de publicar. El registro cambia de campeón mediante comparación
  atómica de la versión esperada; una publicación concurrente obliga a reevaluar.
- Repetir datos y configuración ya evaluados no vuelve a ajustar el mismo
  candidato. Los fallos técnicos no se guardan como rechazos terminales: se
  reintentan. Una alteración de hashes bloquea la carga, incluso si no hay datos
  nuevos para entrenar.

La lógica cubre estas barreras de ejecución. La receta todavía debe validar la
alineación UTC/local, resolución espacial, latencias y disponibilidad histórica
real de cada feature. Las predicciones climáticas utilizadas por suelo requieren
validación fuera de muestra para evitar filtraciones. No basta un booleano en
una medición sin un proceso científico que respalde su verificación.

## Ejecución

```bash
python -m pip install '.[api,storage,geospatial,mongo,ml]'
python -m scripts.migrate
python -m scripts.worker
```

En macOS XGBoost requiere OpenMP (`brew install libomp`). La imagen del worker
instala el runtime OpenMP de Linux y el extra `ml`; la API conserva una imagen
sin las dependencias de entrenamiento.

Jobs separados o una ejecución manual:

```bash
python -m scripts.worker --job ingestion --once
python -m scripts.worker --job training --once
python -m scripts.worker --job recommendations --once
```

`--once` fuerza únicamente los jobs seleccionados bajo sus mismos locks. Un
`--once` sin `--job` ejecuta los tres. Los comandos de entrenamiento y
recomendaciones no llaman a NASA. La cadencia y el backoff se conservan al
reiniciar; los errores de MongoDB no provocan escritura silenciosa en PostgreSQL.

Para la revisión local con bases persistentes y sin activar el worker:

```bash
python -m pip install '.[api,storage,geospatial,local,mongo]'
python -m scripts.dev_stack --seed-reference --with-mongo
```

Este comando requiere `mongod`, conserva PostgreSQL en `data/local/postgres`,
MongoDB en `data/local/mongo` y CSV en `data/farms`. MongoDB escucha únicamente en
`127.0.0.1:27018`. Sin `--with-mongo`, selecciona explícitamente el adapter
PostgreSQL de compatibilidad. No migra resultados entre los dos modos.

Compose arranca API, web, PostgreSQL, MongoDB y tres workers separados. Un
entrenamiento prolongado no bloquea la ingesta o el proceso de recomendaciones. El modo por defecto es
`RESULTS_BACKEND=mongodb` y la URI interna es `mongodb://mongo:27017`. No exportar
una URI con `localhost` dentro de los contenedores. Los adapters científicos
siguen pendientes en ambos modos; los jobs lo informan sin generar predicciones.

## Observabilidad y pruebas

`GET /api/v1/automation` muestra calendarios, errores, último resultado, modelos
publicados y estados informativos del entrenamiento. No contiene datos privados
de fincas. `GET /api/v1/status` conserva el contrato anterior de ingesta y adapters.

```bash
python -m scripts.export_openapi
python -m scripts.verify_automation
```

La verificación usa MongoDB y PostgreSQL temporales, con colecciones/esquemas de
prueba aislados. Requiere `mongod`, `embedded-postgres` y los extras `test,ml`.
También puede ejecutarse `unittest discover` con `TEST_DATABASE_URL` y
`TEST_MONGODB_URI` de pruebas. Sin esos recursos se omiten las integraciones de
forma explícita; la prueba del adapter real se omite si no se instala `ml`.
Los datos y modelos sintéticos de estas pruebas nunca se publican en las bases
operativas ni se presentan como resultados agrícolas.
