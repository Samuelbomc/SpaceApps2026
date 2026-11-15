# Preparar el entorno de desarrollo

Ejecutar desde la raíz. Python requiere 3.11 o superior; los contenedores usan
Python 3.14 y Node 26. El frontend tiene lockfile npm. Instalar `mongod` para el
modo local con MongoDB; en macOS, XGBoost requiere el runtime OpenMP del host.

## Instalación nativa

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install '.[api,storage,geospatial,local,mongo,ml,test,dev]'
npm ci --prefix frontend
python -m scripts.dev_stack --seed-reference --with-mongo --with-workers
```

Abrir frontend en `http://localhost:3000` y API en `http://localhost:8000/docs`.
`--seed-reference` carga observaciones reales de referencia disponibles si la
región no tiene registros; no crea usuarios o fincas ficticias. Las bases locales
se conservan en `data/local/` y los CSV privados en `data/farms/`.

`--with-workers` inicia tres consumidores independientes: ingesta diaria,
evaluación de entrenamiento diaria y recomendaciones cada hora. Comparten las
conexiones y directorios del backend, y consumen los calendarios y reintentos
persistidos. Sin esta opción, el stack inicia solo el consumidor manual y no
descarga ni entrena sin solicitudes. `--api-only` inicia backend y bases; el frontend
puede arrancarse con `npm start --prefix frontend`. El proxy `/backend/*` utiliza
API_INTERNAL_URL para conectarse a `/api/v1/*`. No se detienen servicios ajenos
si los puertos están ocupados.

La CLI hereda el entorno y no carga `.env`. Para modificar conexiones o rutas,
consultar [configuración](../reference/configuration.md). Los scripts científicos
de preparación raster requieren además pandas, h5py y rasterio; entrenar desde
tablas procesadas no necesita esas dependencias de extracción.

## Instalación con Docker

Preparar `.env` desde [.env.example](../../.env.example) sin sobrescribir una
configuración existente. Compose lee ese archivo.

```bash
docker compose config --quiet
docker compose up --build -d
```

Compose inicia bases, API, web, tres workers periódicos y el consumidor manual. Usa sus propios volúmenes y
red; no comparte automáticamente el PostgreSQL del stack nativo. Ver
[despliegue](../architecture/deployment.md) y [operación](../operations/runbook.md).

## Primer recorrido

1. Abrir `/explorar` para consultar territorio y fuentes.
2. Crear una cuenta en `/registro` e iniciar sesión en `/acceso`.
3. Registrar una finca en `/fincas`, delimitando su ubicación y ficha.
4. Opcionalmente cargar un CSV según el catálogo y unidades admitidas.
5. En `/explorar#resultados`, elegir ubicación y 7/15/30/60 días. Los estados dependen de
   resultados guardados y entradas disponibles; no se generan por abrir la página.

Con sesión, el botón de actualización manual encola los jobs y muestra su progreso;
no garantiza publicar modelos si faltan entradas o validación.

La pantalla de análisis es regional. La personalización con la ficha requiere
las condiciones de [contexto de finca](../architecture/farm-personalization.md).

## Migraciones, contratos y verificación

```bash
python -m scripts.migrate
python -m scripts.export_openapi --check
python -m scripts.check_repository
```

Las migraciones SQL verifican hashes y se aplican bajo bloqueo. No modificar una
ya aplicada. La geometría validada se guarda con JSONB; no se requiere PostGIS.
Si cambia un DTO, regenerar con `python -m scripts.export_openapi` y revisar el diff.

Para pruebas, formato y build seguir [CONTRIBUTING.md](../../CONTRIBUTING.md) y
[verificación](../quality/verification.md). Para ejecutar jobs, consultar el
[runbook](../operations/runbook.md).
