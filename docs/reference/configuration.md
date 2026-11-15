# Configuración de ejecución

La fuente de configuración es `apps/api/app/config.py`, junto con las opciones
operativas de los scripts y [docker-compose.yml](../../docker-compose.yml).
[.env.example](../../.env.example) contiene valores de desarrollo. La CLI Python
hereda variables; no carga `.env` automáticamente. Compose sí lo utiliza.

## Conexiones y seguridad

| Variable | Uso / valor local predeterminado |
| --- | --- |
| DATABASE_URL | PostgreSQL; debe apuntar al entorno elegido |
| POSTGRES_USER / POSTGRES_DB | agrogeo; inicialización y conexión interna de Compose |
| POSTGRES_PASSWORD | Inicialización/conexión Compose; reemplazar el valor de desarrollo |
| COMPOSE_PROJECT_NAME | agrogeo; nombre del conjunto de servicios |
| POSTGRES_VOLUME_NAME / MONGO_VOLUME_NAME | agrogeo_postgres_data / agrogeo_mongo_data |
| RESULTS_BACKEND | postgresql en Settings; mongodb en Compose |
| MONGODB_URI | mongodb://127.0.0.1:27017; en Compose, host mongo |
| MONGODB_DATABASE | agrogeo |
| CORS_ORIGINS | localhost:3000 y 127.0.0.1:3000; lista separada por comas |
| AUTH_COOKIE_SECURE | false en HTTP local; true al servir HTTPS |
| API_INTERNAL_URL | FastAPI para el proxy de desarrollo; Compose usa su red interna |
| GEOCODER_URL | Servicio reverse compatible con Photon; etiqueta orientativa |

No publicar URIs con credenciales. La autenticación de la aplicación y Earthdata
son independientes. EARTHDATA_TOKEN o EARTHDATA_USERNAME/EARTHDATA_PASSWORD se
configuran únicamente en el entorno de descarga que los necesite. Los scripts
raster tienen requisitos adicionales de proveedor; ver
[adquisición](../guides/data-acquisition.md).

## Identidad y almacenamiento existente

El producto se llama **AgroGeo**. El paquete Python es `agrogeo` y su comando de
ingesta es `agrogeo-ingest`. El frontend es `@agrogeo/web`, el proyecto Angular es
`agrogeo` y el cliente compartido se importa desde `@agrogeo/api-client`.
La API publica el título `AgroGeo API`; la identidad visible del frontend se
centraliza en `frontend/src/app/core/config/app-identity.ts`.

Los nombres de conexión y volúmenes son configuración, no identificadores de
observaciones ni modelos. Para conectar una instalación existente, indicar sus
nombres reales mediante las variables anteriores. Cambiar `POSTGRES_USER` o
`POSTGRES_DB` no renombra usuarios ni bases dentro de un volumen inicializado.
Cambiar `MONGODB_DATABASE` selecciona otra base; no transfiere colecciones.
Los nombres de volúmenes permiten reutilizar el almacenamiento existente sin
crear uno vacío. Ver [operación y recuperación](../operations/runbook.md).

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
La ingesta y la evaluación de entrenamiento son diarias; no obligan a publicar
un modelo cada día. La receta,
las políticas y los horizontes están en [entrenamiento](model-training.md).
El nombre de una región no acredita equivalencia con un lote privado.
