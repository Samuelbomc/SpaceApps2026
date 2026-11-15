# Integración de los modelos XGBoost recibidos

La rama principal remota es `main`. Se integraron los artefactos ya presentes en
`origin/main` (`ee98d4c`), preservando el frontend Angular y los modelos originales.
La integración se desarrolla en `feature/prepare-frontend-migration`.

## Modelos conectados por horizonte

- Media de temperatura: `environmental_conditions/temperature_mean`.
- Media de temperaturas mínimas y máximas: `temperature_min` y `temperature_max`.
  Son medias de los extremos diarios, no el mínimo o máximo absoluto del periodo.
- Lluvia acumulada del horizonte: `precipitation`, entrenado con GPM Late.
- Humedad superficial: `soil_moisture`. Su salida absoluta es
  **smap_mean_7d + XGBoost(features)**, sumando el baseline una sola vez.

Para 15, 30 y 60 días se usan las variantes de `forecasts/{H}d/{modelo}`.
En total son veinte artefactos: cinco por cada uno de los cuatro horizontes.
No se reutilizan recursivamente los modelos de siete días.

Se usan los archivos `model.json`, reajustados con todos los datos preparados.
Las métricas registradas pertenecen a `evaluation_model.json`; no son una
validación independiente del reajuste. Los propios informes del equipo califican
estos artefactos como experimentales y requieren evaluación independiente antes
de un despliegue agrícola validado. Esta integración los mantiene identificados
como experimentales y no los promueve al registro de campeones publicados.

`ml/configs/pretrained-bundle.json` fija hashes SHA-256 de cada JSON de modelo y
metadatos. Una alteración bloquea su uso hasta integrar expresamente otra versión.
Cada inferencia ordena las variables según training.json y comprueba el orden
interno del Booster. Rechaza variables ausentes y valores no finitos; no rellena
variables con cero ni aplica clipping a las salidas.

El informe recibido señala que la humedad a 30 días no supera la persistencia
en el test completo. Se conserva ese resultado y no se declara validado por
el hecho de integrar su artefacto. Ver [evaluación del equipo](../ml/docs/horizon-results.md).

## Periodo y entradas

Cada grupo predice **t+1 a t+H**, donde H es 7, 15, 30 o 60, usando observaciones hasta **t-2**.
Para mostrar desde el día de consulta D, el job requiere emisión D-1 y corte D-3.
Son medias o acumulados del periodo completo, no condiciones específicamente
en el día H. No se multiplica un resultado semanal ni se ejecuta recursivamente
con variables futuras desconocidas.

Las entradas de los cuatro horizontes comparten la misma receta histórica.
El contrato de entrada es `ExpandedFeatures`, en `packages/contracts/pretrained.py`:

- Identidad de región, coordenadas WGS84 y receta `expanded-v1`.
- issue_date, observation_cutoff y SHA-256 del origen procesado.
- climate: las 31 variables de entrenamiento, en sus unidades y receta originales.
- soil: las 52 variables de humedad; es opcional para admitir clima sin suelo.

La preparación debe respetar `ml/scripts/prepare_expanded_datasets.py` y sus reglas
para POWER, GPM Late, elevación, SMAP y SoilGrids. Los snapshots de inferencia no
incluyen target ni observaciones futuras. No basta con tener T2M y RH2M: se necesitan
todas las ventanas, fuentes, variables estáticas y controles de la receta original.
Guardar un CSV privado de finca tampoco lo convierte automáticamente en esas entradas.

`ExpandedFeatureStore` guarda snapshots JSON pequeños en FEATURE_DIRECTORY.
Cada revisión conserva una copia por hash en `versions/`; actualizar una misma
fecha no elimina las variables usadas en una inferencia anterior. El
productor de procesamiento llama a `save(snapshot)`; el job consume únicamente la
fecha exacta y exige que las coordenadas coincidan con las de la región registrada.
No selecciona filas antiguas, vecinos ni fechas cercanas por defecto.

**Estado de los datos:** los datasets recibidos tienen entradas climáticas hasta
septiembre de 2026 y de humedad hasta enero de 2022. La ingesta actual POWER y los catálogos
públicos no extraen automáticamente todos los raster y variables requeridos por
estos modelos. Falta producir snapshots recientes con esa receta para tener un
pronóstico actual. El sistema responde `insufficient_data` cuando no existen;
la integración de modelos está operativa y no presenta aquellos datos como actuales.

## Job, almacenamiento y API

`build_jobs` conecta el bundle y el feature store a `CropRecommendationJob`. Los
campeones publicados conservan prioridad. Cuando no hay campeones para un slot, el job usa los artefactos experimentales
del horizonte correspondiente. La falta de un snapshot produce
un diagnóstico sin predicción; los errores técnicos o de integridad siguen el
backoff durable existente. El entrenamiento autónomo conserva sus propios criterios
de validación y promoción, y no cambia por importar estos artefactos.

Las salidas, versiones, hashes y limitaciones se guardan en el repositorio de
resultados seleccionado (MongoDB o PostgreSQL). `pending_recommendations` significa
que hay clima y suelo y falta el motor agronómico. `insufficient_data` puede contener
solo clima si faltan las variables de suelo. No se fabrican recomendaciones.

La migración 005 permite input_snapshot_id null en diagnósticos sin datos, alineando
PostgreSQL con el contrato HTTP. Las predicciones conservan el hash de sus features.

- `GET /api/v1/models`: catálogo, variables requeridas, horizonte y métricas de evaluación.
  Solo lee JSON y hashes; la API no necesita cargar XGBoost para responder.
- `GET /api/v1/regions/{id}/latest-analysis`: resultado guardado para el periodo exacto.
  El corte de las variables se conserva aunque otras fuentes tengan datos más nuevos.
- FastAPI no consulta NASA, entrena ni calcula inferencias al abrir el frontend.

Angular muestra los modelos disponibles, estados reales y mensajes de datos faltantes.
Las predicciones tienen nombres y unidades legibles. La vista técnica añade versiones,
variables, métricas y la distinción entre evaluación y reajuste.

## Uso

```bash
python -m pip install '.[api,storage,geospatial,mongo,ml]'
python -m scripts.migrate
python -m scripts.worker --job recommendations --once
```

Variables opcionales: PRETRAINED_MODEL_DIRECTORY=ml/artifacts y
FEATURE_DIRECTORY=data/features/expanded-v1. Compose ya configura ambas rutas y
monta el directorio de datos. No se requiere pandas ni rasterio para cargar el
bundle o consumir snapshots preparados; la extracción raster sí tiene sus propias
dependencias. El worker conserva las tareas programadas al ejecutar --once.

Para comprobar una inferencia real sin tocar las bases:

```bash
python -m scripts.import_model_features \
  --dataset samples/xgboost/moisture_99_20220108.csv \
  --point-id moisture_99 --region-id historical-check \
  --issue-date 2022-01-08 --preview
```

Es una reproducción de inferencia histórica sobre una fila del dataset usado en el
reajuste, **no un backtest independiente** ni un pronóstico de hoy. Con datasets de `data/prepared/horizons/{H}d/` indicar `--horizon-days H`. Sin --preview,
el comando guarda únicamente un snapshot en el feature store. Para utilizarlo en
un job histórico debe existir una región registrada en esas coordenadas exactas;
no se debe asociar la celda SMAP a Medellín cambiando solo su nombre o identificador.
Los jobs operativos siempre usan el día actual y no cargan muestras históricas.

## Verificación

```bash
python -m scripts.verify_automation
npm test --prefix frontend -- --watch=false
npm test --prefix packages/api-client
npm run build --prefix frontend
```

Se comprueban la inferencia real, el baseline de humedad una sola vez, orden de
variables, integridad de modelos, fechas y coordenadas exactas, aislamiento del
registro publicado, persistencia PostgreSQL/MongoDB y lectura HTTP sin inferencia.
