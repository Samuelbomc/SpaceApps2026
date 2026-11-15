# Almacenamiento de Field Shift

El histórico necesario para reentrenar queda separado de los resultados que
consume el frontend. Compose usa MongoDB para resultados ML
y conserva PostgreSQL para identidad, fincas, observaciones y programación.

| Información | Persistencia |
| --- | --- |
| Histórico NASA procesado, unidades, calidad y procedencia | Parquet por punto y año |
| Snapshot de las veinte tablas procesadas de la receta | `data/datasets/<dataset_id>/<horizonte>/<target>.parquet` y `training-sources.json` |
| Snapshot del adapter genérico de observaciones | `data/datasets/<dataset_id>/observations.parquet` y manifiesto |
| Features, etiquetas y baseline exactos de cada experimento | `data/datasets/<dataset_id>/prepared/<fingerprint>.parquet` |
| Boosters XGBoost y manifiestos versionados | `data/models/<version>/*.json` |
| Candidatos, métricas y versión publicada por región/modelo/horizonte | MongoDB |
| Predicciones, escenarios y recomendaciones calculadas | MongoDB |
| Catálogo agronómico activo y revisiones de sus entradas | MongoDB |
| Usuarios, sesiones, fincas y observaciones CSV privadas | PostgreSQL |
| CSV originales privados | `data/farms/`, fuera de las rutas públicas |
| Observaciones NASA recientes y estado de ingesta | PostgreSQL |
| Calendarios, errores y reintentos de los tres jobs | PostgreSQL |

## Versiones recuperables

La ingesta puede corregir un Parquet histórico. Antes del entrenamiento se
materializa una copia completa con identidad por contenido y hash del archivo.
Una revisión genera otro snapshot; no sobrescribe el utilizado anteriormente.
El histórico reciente de PostgreSQL no limita la ventana de entrenamiento.

Cada candidato guarda sus modelos JSON, features ordenadas, targets y unidades,
receta, política, dataset y métricas sobre la validación temporal común. El
Parquet preparado conserva las muestras exactas, etiquetas, fuentes y baseline.
El adapter XGBoost guarda hiperparámetros, iteraciones y versión de la biblioteca.
Antes de cargar un modelo publicado se verifican los hashes de sus archivos.

La versión publicada se cambia con comparación de la versión vigente esperada.
La publicación ocurre después de guardar y comprobar los artefactos. Una caída
previa puede dejar un candidato sin publicar, pero no un campeón que apunte a
archivos todavía pendientes de guardar. Los candidatos rechazados quedan
registrados y no reemplazan al modelo vigente. No hay limpieza automática de
artefactos: borrar una versión referenciada impediría reproducir resultados.

## Colecciones MongoDB

- `training_attempts`: evaluación terminal por huella de datos y configuración.
- `model_versions`: versiones candidatas aceptadas para publicación.
- `published_models`: documento por región/modelo/horizonte; cambio atómico.
- `pipeline_status`: último resumen informativo del entrenamiento.
- `analyses`: resultados idempotentes; conserva versiones anteriores.
- `crop_catalog` y `crop_catalog_versions`: entradas activas y revisiones.

La identidad del análisis incluye periodo objetivo, snapshot de entradas,
versiones climática y de suelo, versión del motor y del catálogo agronómico.
Los resultados anteriores se conservan cuando cambian datos, catálogo o modelos.
Las predicciones no se escriben como observaciones ni se usan como etiquetas.

MongoDB no contiene usuarios, contraseñas, sesiones ni CSV privados. El catálogo
agronómico es distinto del catálogo personal de fincas y del formulario de suelo.
No hay reglas o cultivos inventados precargados como recomendaciones reales.

## Configuración y compatibilidad

`RESULTS_BACKEND=mongodb` selecciona MongoDB sin fallback automático. Si no está
disponible, FastAPI responde 503 y el job conserva el error para reintentarlo.
Compose utiliza este modo por defecto. `MONGODB_URI` y `MONGODB_DATABASE` eligen
la conexión; no se registra la URI en errores ni se publica el puerto en Compose.

`RESULTS_BACKEND=postgresql` selecciona el adapter de resultados PostgreSQL y
un registro ML en `ml_records`. Sirve para desarrollo sin MongoDB; es una selección
explícita, no una copia simultánea. Cambiar de backend no migra resultados previos.
Las cuentas y fincas siguen en la misma base PostgreSQL en ambos modos.

Las migraciones SQL mantienen el esquema de operación y registro. Son append-only
y se aplican con verificación de hashes.

## Retención ligera

No se conservan imágenes satelitales completas por defecto. POWER mantiene sus
respuestas JSON pequeñas como evidencia de procedencia. La liberación de archivos
grandes temporales solo debe ocurrir después de persistir y comprobar los datos
procesados. No hay una limpieza TTL aplicada a históricos o resultados evaluables.

Las credenciales, los datos privados y las salidas operativas generadas permanecen
fuera de Git. El repositorio conserva datasets y artefactos científicos aportados
por el equipo que ya estaban versionados; no deben confundirse con los CSV
privados de agricultores. El catálogo ECOCROP de referencia está empaquetado en
`ml/configs/`; el catálogo activo de recomendaciones y sus borradores se gestionan
por separado en el backend de resultados. Ver [la receta](../reference/model-training.md).
