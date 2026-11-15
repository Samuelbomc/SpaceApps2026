# Configuración de ejecución

La fuente de configuración es `apps/api/app/config.py`, junto con las opciones
operativas de los scripts y [docker-compose.yml](../../docker-compose.yml).
[.env.example](../../.env.example) contiene valores de desarrollo. La CLI Python
hereda variables; no carga `.env` automáticamente. Compose sí lo utiliza.

## Conexiones y seguridad

| Variable | Uso / valor local predeterminado |
| --- | --- |
| DATABASE_URL | PostgreSQL; debe apuntar al entorno elegido |
| POSTGRES_PASSWORD | Inicialización/conexión Compose; reemplazar el valor de desarrollo |
| RESULTS_BACKEND | postgresql en Settings; mongodb en Compose |
| MONGODB_URI | mongodb://127.0.0.1:27017; en Compose, host mongo |
| MONGODB_DATABASE | fieldshift |
| CORS_ORIGINS | localhost:3000 y 127.0.0.1:3000; lista separada por comas |
| AUTH_COOKIE_SECURE | false en HTTP local; true al servir HTTPS |
| API_INTERNAL_URL | FastAPI para el proxy de desarrollo; Compose usa su red interna |
| GEOCODER_URL | Servicio reverse compatible con Photon; etiqueta orientativa |

No publicar URIs con credenciales. La autenticación de la aplicación y Earthdata
son independientes. EARTHDATA_TOKEN o EARTHDATA_USERNAME/EARTHDATA_PASSWORD se
configuran únicamente en el entorno de descarga que los necesite. Los scripts
raster tienen requisitos adicionales de proveedor; ver
[adquisición](../guides/data-acquisition.md).

## Directorios

| Variable | Ruta local predeterminada | Contenido |
| --- | --- | --- |
| FARM_UPLOAD_DIRECTORY | data/farms | CSV originales privados |
| TRAINING_DATA_DIRECTORY | data/prepared | Tablas procesadas y validación de origen |
| TRAINING_CONFIG_PATH | Sin override | Configuración empaquetada expanded-training.json |
| DATASET_DIRECTORY | data/datasets | Snapshots inmutables y muestras preparadas |
| MODEL_DIRECTORY | data/models | Artefactos de candidatos/registro |
| PRETRAINED_MODEL_DIRECTORY | ml/artifacts | Bundle experimental empaquetado |
| FEATURE_DIRECTORY | data/features/expanded-v1 | Variables recientes para inferencia |
| ROTATION_WATER_RULES_PATH | Sin archivo predeterminado | RotationWaterRules revisadas |

Compose monta `./data` en `/app/data` y fija allí los directorios operativos.
Los overrides de configuración/reglas deben usar rutas accesibles en el contenedor.
Las rutas privadas no se sirven como archivos públicos.

## Región y ventanas operativas

| Variable | Significado |
| --- | --- |
| REGION_ID / REGION_NAME | Identidad y etiqueta operativa de la región |
| REGION_LATITUDE / REGION_LONGITUDE | Coordenadas WGS84 de referencia |
| RECENT_OBSERVATION_DAYS | Ventana operativa reciente, 90 días por defecto |
| INGESTION_LAG_DAYS | Corte del job de ingesta, 3 días por defecto |

La retención reciente no limita el dataset histórico Parquet de entrenamiento.
La cadencia semanal tampoco obliga a publicar un modelo semanalmente. La receta,
las políticas y los horizontes están en [entrenamiento](model-training.md).
El nombre de una región no acredita equivalencia con un lote privado.
