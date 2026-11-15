# Field Shift — NASA Space Apps 2026

El frontend activo es **Angular en `frontend/`**, integrado desde
`feature/agricultural-platform-frontend`. Next.js fue retirado. La
[guía de integración](docs/frontend-migration.md) documenta los flujos conectados,
los contratos y los límites actuales. El cliente compartido está en
[packages/api-client](packages/api-client/README.md).

```bash
npm ci --prefix frontend
python -m scripts.dev_stack --with-mongo
```

La web queda en `http://localhost:3000`, con proxy hacia FastAPI.
También puede iniciarse solo el backend con `--api-only`.

La base de integración incluye **PostgreSQL, MongoDB, FastAPI, Angular y jobs
independientes de ingesta, reentrenamiento y recomendaciones**. El ciclo de vida ML
incluye snapshots, candidatos XGBoost, validación temporal y promoción condicional.
Las recetas científicas, etiquetas verificadas y reglas agrícolas deben conectarse
antes de publicar modelos reales. Ver [reentrenamiento autónomo](docs/autonomous-training.md).

```bash
cp .env.example .env  # Solo si no existe ya un archivo con tu configuración.
docker compose up --build -d
```

Frontend: `http://localhost:3000`. API: `http://localhost:8000/docs`.
La primera ingesta queda pendiente al iniciar el worker; el calendario se
conserva en PostgreSQL. Se requiere un motor Docker disponible para activar
los servicios permanentes. Consulta [la guía de desarrollo](docs/development.md)
para ejecución por separado, contratos, migraciones y verificación.

Clientes Python para consumir **NASA POWER, GPM, SMAP, SRTM, GRACE, ECOSTRESS
y Landsat**, como primera etapa de la plataforma de apoyo a decisiones agrícolas.

**Prioridad actual: NASA POWER de extremo a extremo.** Ya están implementados
el GET histórico puntual, procesamiento, persistencia Parquet y actualización
incremental. El orden es ingesta → procesamiento → almacenamiento → ML → inferencia.
Después se completarán GPM, SMAP, SRTM, Landsat y ECOSTRESS; GRACE queda para una
fase posterior. Sus clientes de descubrimiento existentes se conservan.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install '.[storage]'

python -m scripts.ingest power-sync \
  --latitude 6.2442 --longitude -75.5812 \
  --start 2020-01-01 --end 2025-12-31 \
  --parameters T2M RH2M WS10M ALLSKY_SFC_SW_DWN \
  --output data/manifests/power-sync.json
```

El comando conserva respuestas originales y observaciones por fecha/variable en
`data/`, sin duplicarlas al repetir la operación. El histórico real del punto de
referencia de Medellín contiene **8768 observaciones de cuatro variables en 2192
días** para 2020–2025. Ese punto no implica una región piloto elegida.
Consulta [la guía de ingesta POWER](docs/power-ingestion.md).

La persistencia es **híbrida**: históricos procesados y snapshots en Parquet;
modelos XGBoost en JSON; métricas, catálogo agronómico y resultados en MongoDB.
PostgreSQL conserva cuentas, fincas, observaciones recientes y calendarios durables.
Se mantiene un modo PostgreSQL explícito para resultados en desarrollo local.
No se almacenan imágenes satelitales completas por defecto. Consulta la
[estrategia de almacenamiento](docs/storage-strategy.md).

El flujo es **ingesta → procesamiento → histórico → candidato XGBoost → validación
y publicación condicional → inferencia y recomendaciones → MongoDB → FastAPI →
Angular**. El entrenamiento usa el histórico completo disponible hasta el corte,
no solo las observaciones de los últimos siete días. Una falta de etiquetas,
un candidato peor o una caída del proveedor conservan el modelo vigente.
El [diagrama y responsabilidades](docs/architecture.md) distingue los componentes
implementados de los adapters científicos que todavía deben definirse.

También se probó un **área de 10 × 10 m** con acceso público: 372 observaciones
POWER procesadas y catálogos de las siete fuentes en dos periodos separados.
Los archivos satelitales de muestra devolvieron HTTP 401 a GET sin credenciales.
El [informe de la prueba](docs/aoi-10m-validation.md) incluye datos reales,
limitaciones de resolución y el procesamiento pendiente por fuente; la
[muestra pequeña](samples/aoi-10m/README.md) permite revisar los resultados.

Cada fuente tiene un cliente en `pipelines/ingestion/sources/nasa/` y un repositorio
de acceso externo en `apps/api/app/repositories/`. La consulta conjunta está en
`apps/api/app/services/nasa_data.py`; los contratos están en `packages/contracts/`.
En esta etapa su responsabilidad es crear/recibir clientes y consumir las APIs.
Los criterios de dominio, la preparación de entradas y los outputs de XGBoost
se definirán posteriormente. Estos repositorios son módulos Python dentro del
monorepo; no son repositorios Git separados. Los repositorios de acceso a NASA
son distintos del repositorio de almacenamiento `PowerParquetRepository`, ubicado
en `pipelines/ingestion/storage/power.py`.

```python
from packages.contracts import DataQuery
from apps.api.app.services.nasa_data import NASADataService
from apps.api.app.repositories import SMAPRepository

query = DataQuery.from_dict({
    "latitude": 6.0,
    "longitude": -75.0,
    "start": "2026-01-01",
    "end": "2026-01-31",
    "limit": 5,
})
result = NASADataService().fetch(query)  # Las siete fuentes; dos productos ECOSTRESS.
smap = SMAPRepository().fetch(query)   # Mismo contrato para una fuente individual.
```

Cada repositorio recibe `DataQuery` y devuelve `SourceResult`: `query_id`, `source`,
`status`, `requested`, `metadata`, `data_kind`, `data` y `error`. POWER conserva
sus respuestas originales en `data.raw_responses`; las otras fuentes devuelven
catálogos con metadatos originales y enlaces dentro de `data`. Sus clientes HTTP/CMR
pueden inyectarse por constructor y reutilizarse entre repositorios.

El contrato acepta **latitud/longitud o bbox**, junto con el periodo. La coordenada
no se transforma en un área arbitraria. POWER consulta su endpoint puntual y CMR
selecciona archivos cuya cobertura intersecta ese punto. Se conserva la resolución
de origen, la consulta efectiva y el estado de cada fuente (`ok`, `empty`, `error`).
Un error parcial no descarta resultados de las demás fuentes.

La misma coordenada permite relacionar solicitudes, pero no hace equivalentes los
píxeles, las fechas ni las resoluciones. Este módulo no extrae todavía valores raster
ni los alinea para XGBoost. Consulta el [contrato completo](docs/unified-query.md).

## Región

Se usa el rectángulo suministrado del Oriente antioqueño en WGS84 / EPSG:4326:

```text
oeste = -75.5830    sur = 5.4110
este  = -74.6167    norte = 6.5866
bbox  = [oeste, sur, este, norte]
```

En longitudes negativas, el mínimo corresponde al extremo oeste.
Este rectángulo no es un límite administrativo validado.

## Uso local

Python 3.11 o posterior. POWER y CMR funcionan con la biblioteca estándar,
sin instalar dependencias:

```bash
python3 -m scripts.ingest catalog

# Una sola ubicación y periodo para las siete fuentes.
python3 -m scripts.ingest collect \
  --latitude 6.0 --longitude -75.0 \
  --start 2026-01-01 --end 2026-01-31 --limit 5 \
  --output data/manifests/sector.json

# Respuestas originales de la API diaria de POWER.
python3 -m scripts.ingest power \
  --start 2024-01-01 --end 2024-01-07 \
  --output data/processed/power.json

# Buscar archivos reales de las seis fuentes satelitales.
python3 -m scripts.ingest search --source all \
  --start 2026-01-01 --end 2026-01-31 --limit 5 \
  --output data/manifests/nasa.json

# SRTM es estático y no necesita fechas.
python3 -m scripts.ingest search --source srtm \
  --limit 20 --output data/manifests/srtm.json
```

Las fuentes aceptadas por `--source` son `gpm`, `smap`, `srtm`, `grace`,
`ecostress`, `ecostress-lst` y `landsat`. `search` admite también `all`.

- `--bbox WEST SOUTH EAST NORTH` permite otra región.
- Las fechas son inclusivas, en UTC. Se necesitan ambas, excepto para SRTM.
- `--limit` limita granules por producto; `limit_reached` indica posibles resultados adicionales.
- `--refresh` evita reutilizar la caché JSON de 24 horas.
- `search --source all` conserva resultados exitosos, informa errores por producto
  y devuelve código 1 si alguna consulta falla. Un catálogo vacío no es una medición de cero.

## Fuentes y productos

| Fuente | Producto / acceso | Versión | Resolución y contenido |
| --- | --- | --- | --- |
| NASA POWER | API diaria regional | Reportada en respuesta | Meteorología 0.5° × 0.625°; radiación 1° × 1° |
| GPM | CMR / `GPM_3IMERGDF` | `07` | Precipitación IMERG Final diaria, 0.1° |
| SMAP | CMR / `SPL4SMGP` | `008` | Humedad superficial y radicular L4, 9 km, cada 3 horas |
| SRTM | CMR / `SRTMGL1` | `003` | Elevación estática, aproximadamente 30 m |
| GRACE/GRACE-FO | CMR / `TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4` | `RL06.3Mv04` | Anomalías mensuales de almacenamiento total regional |
| ECOSTRESS | CMR / `ECO_L3T_JET` y `ECO_L2T_LSTE` | `003` | Evapotranspiración y temperatura superficial, 70 m |
| Landsat | CMR / `HLSL30` | `2.0` | Producto NASA derivado de Landsat 8/9, 30 m |

Las versiones y proveedores son explícitos en
[catalog.py](pipelines/ingestion/sources/nasa/catalog.py). CMR resuelve el identificador de
colección en ejecución y rechaza resultados ambiguos. No cambia de versión automáticamente.

POWER consulta `T2M`, `T2M_MIN`, `T2M_MAX`, `RH2M`, `ALLSKY_SFC_SW_DWN` y `WS2M`.
`--parameters` permite seleccionar otros códigos admitidos por el proveedor.
No solicita precipitación por defecto para mantener GPM como fuente principal.

El endpoint regional POWER exige una ventana mínima de 2° por eje. Para esta región
se consulta `[-76, 5, -74, 7]` y se conserva la respuesta original completa, incluyendo
los puntos fuera del bbox solicitado. Se registra la ventana efectiva y una petición
por variable. La malla devuelta no aumenta la resolución de origen ni equivale a datos de finca.

## Descargas protegidas

La búsqueda CMR es pública. Los archivos protegidos requieren una cuenta gratuita
de [Earthdata Login](https://urs.earthdata.nasa.gov/) y las autorizaciones del DAAC.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install '.[download]'

# Configurar EARTHDATA_TOKEN en el entorno mediante tu gestor de secretos.
# Alternativa: EARTHDATA_USERNAME y EARTHDATA_PASSWORD.
# .env.example enumera las variables; la CLI no carga .env automáticamente.

python -m scripts.ingest download --source landsat \
  --start 2024-01-01 --end 2024-01-31 --limit 1 \
  --asset '*B04.tif' --asset '*B05.tif' --asset '*Fmask.tif' \
  --max-files 3 --max-mb 150 \
  --output data/manifests/landsat-download.json
```

Después de instalar el paquete está disponible `field-shift-ingest`;
`spaceapps-ingest` se conserva como alias del comando.
La autenticación usa `earthaccess`, sin prompts interactivos ni escritura de secretos.
`--asset` es un patrón de nombre repetible. Consulta primero `data_urls` del manifiesto
para seleccionar variables y archivos de calidad. Si se omite, se toman los primeros
activos hasta el límite; eso no garantiza un conjunto completo de bandas.

Por defecto se descargan como máximo **3 archivos y 100 MiB de bytes nuevos**.
El streaming comprueba el presupuesto y el espacio libre. Los parciales fallidos se
eliminan; cada archivo completo conserva un sidecar con procedencia, fechas solicitadas,
URL, fecha de acceso, tamaño y SHA-256. Repetir el comando verifica y reutiliza archivos
completos. No se reintentan automáticamente descargas grandes.

Estos son archivos originales completos: seleccionar una región en CMR **no recorta
su contenido**. Un solo archivo global de GPM, SMAP o GRACE puede superar el presupuesto.

## Datos obtenidos y alcance

- **POWER:** el repositorio devuelve `data.raw_responses` con valores y metadatos
  originales del proveedor, incluidos sus sentinelas de datos ausentes. No filtra
  puntos, transforma valores ni prepara variables de entrenamiento.
- **Otras fuentes:** catálogo real y descarga de archivos. Los manifiestos contienen
  metadatos y enlaces; no contienen valores científicos extraídos de esos archivos.
- CMR busca intersecciones espaciales y temporales. Faltan recorte, reproyección,
  extracción de variables, escalas, máscaras QA y agregación regional por producto.
- IMERG Final tiene latencia de meses. SMAP L4 combina observaciones y modelado.
  SRTM representa elevación de febrero de 2000; la pendiente se deriva después.
- GRACE contiene múltiples fechas en un archivo y requiere filtrarlas al procesarlo.
  Su malla de 0.5° representa mascons independientes de aproximadamente 3°;
  no permite atribuir humedad a una parcela.
- HLSL30 es un producto NASA derivado de Landsat; no sustituye al archivo original
  Landsat Collection 2. NDVI requiere B04/B05, escalas, nodata y máscara de nubes.
- ECOSTRESS tiene pasos irregulares y cobertura variable. En las pruebas, v003
  devolvió resultados en enero de 2026 y ninguno en enero de 2024 para esta región.
  No se sustituye silenciosamente por v002.

La siguiente etapa es extraer series científicas por producto y región para formar
el dataset de entrenamiento. Conviene evaluar los servicios de subsetting/OPeNDAP
de cada colección antes de descargar archivos globales. Para POWER puntual ya
existe la persistencia de observaciones; faltan la construcción de features y
objetivos de entrenamiento científicamente validados. La API, el ciclo de vida
ML y sus barreras temporales están implementados; las recetas agrícolas y el
motor agronómico siguen pendientes.

## Código y pruebas

```text
apps/
  # La web Angular está en frontend/src/
  api/
    app/
      main.py           # FastAPI v1 y contratos HTTP
      routers/          # Disponible para separar futuros endpoints por dominio
      services/         # NASADataService: consulta conjunta
      repositories/     # Acceso por fuente
      schemas/          # Contratos de entrada/salida de la API
      db/               # Conexión PostgreSQL
    tests/              # Pruebas de repositorios
pipelines/
  ingestion/
    sources/
      nasa/             # power, gpm, smap, srtm, grace, ecostress, hls y CMR común
      colombia/         # Pendiente: IDEAM y UPRA
      global/           # Pendiente: FAO y SoilGrids
    flows/              # Flujo local incremental POWER
    storage/            # PowerParquetRepository: persistencia de observaciones
    http.py
    download.py
    tests/
  processing/
    cleaning/           # Normalización POWER regional y procesamiento puntual
    geospatial/
    temporal/
    validation/
  training/             # Snapshots y ModelTrainingPipeline
  recommendations/      # Modelos publicados → resultados
  scheduling/           # Locks y reintentos de jobs ML
ml/{features,training,evaluation,inference,configs}/
packages/contracts/     # Contratos Python y JSON Schema
infra/{database/migrations,docker}/
tests/                  # Pruebas entre componentes
docs/
samples/
scripts/ingest.py       # Comando de desarrollo
scripts/worker.py       # Scheduler: ingesta, entrenamiento y recomendaciones
scripts/migrate.py      # Migraciones versionadas
.github/workflows/      # Reservado para CI/CD
data/                   # Salidas/caché locales, excluidas de Git
```

```bash
.venv/bin/python -m unittest discover -s . -p 'test_*.py' -v
```

Las pruebas cubren coordenadas, fechas, unidades, ausentes, filtros, paginación,
caché, reintentos, autenticación ausente, checksums, límites de descarga,
procesamiento puntual y persistencia incremental. Las pruebas Parquet requieren
el extra `storage`; sin PyArrow esas pruebas se omiten explícitamente.
La normalización opcional está en
`pipelines/processing/cleaning/power.py::normalize_power_daily`.
Los clientes de ingesta solo consumen fuentes y conservan sus respuestas originales.
Consulta [docs/validation.md](docs/validation.md) para las comprobaciones reales.

Angular, FastAPI, PostgreSQL y Docker Compose tienen implementaciones iniciales.
Las carpetas restantes conservan `.gitkeep` donde todavía no hay implementación.
No hay modelos entrenados, motor agronómico ni despliegue. El worker actual usa
PostgreSQL para programar las ejecuciones y no requiere Prefect.
La raíz actual del checkout representa
`field-shift/`; no se creó una carpeta adicional dentro del repositorio.
Consulta [docs/architecture.md](docs/architecture.md) para las responsabilidades.

## Documentación oficial

- [POWER: API diaria](https://power.larc.nasa.gov/docs/services/api/temporal/daily/)
  y [resoluciones y uso de la API](https://power.larc.nasa.gov/docs/tutorials/service-data-request/api/).
- [CMR: búsqueda y paginación](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html).
- [GPM IMERG](https://gpm.nasa.gov/data/imerg).
- [SMAP L4 versión 8](https://nsidc.org/data/spl4smgp/versions/8).
- [SRTMGL1 versión 3](https://www.earthdata.nasa.gov/data/catalog/lpcloud-srtmgl1-003).
- [GRACE Mascon CRI](https://podaac.jpl.nasa.gov/dataset/TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4).
- [ECOSTRESS ET v003](https://doi.org/10.5067/ECOSTRESS/ECO_L3T_JET.003)
  y [LST v003](https://doi.org/10.5067/ECOSTRESS/ECO_L2T_LSTE.003).
- [HLS: documentación](https://hls.gsfc.nasa.gov/documents/).
- [earthaccess: sesiones y descargas](https://earthaccess.readthedocs.io/en/latest/api/)
  y [credenciales por entorno](https://earthaccess.readthedocs.io/en/latest/user/howto/authenticate-with-environment-variables/).

La validación reciente del **29 de octubre al 11 de noviembre de 2026** obtuvo
84 registros POWER (70 con valor y 14 de radiación solar ausentes), comprobó
catálogos públicos y comparó puntos separados 10/100 m. El mapa permite delimitar
áreas como prueba geométrica. Consulta [datos recientes y selección de áreas](docs/recent-data-and-area-selection.md)
para resoluciones, limitaciones y evidencia de cada fuente.


Se agregaron cuentas de agricultores y un catálogo privado de fincas con carga
local de CSV, validación, procedencia y un contrato de entradas para futuros
modelos. Acceso en `/registro`, `/login` y `/fincas`. El entorno sin Docker puede
iniciarse con `python -m scripts.dev_stack --seed-reference --with-mongo`; requiere
`mongod` (sin la opción usa resultados PostgreSQL) y conserva cuentas y
archivos al reiniciar. Ver [cuentas y datasets privados](docs/farmer-accounts.md).


El [catálogo agronómico ECOCROP](docs/agronomic-catalog.md) aportado por el equipo
está normalizado: 12 perfiles de cultivo, 11 especies, rangos, procedencia y
valores ausentes explícitos. `GET /api/v1/crops/catalog` permite consultarlo.
La evaluación numérica de compatibilidad conserva la escala anual de lluvia y
la diferencia entre pronóstico corto y ciclo de cultivo. Los registros se
guardan como borradores; las recomendaciones de siembra y rotaciones requieren
integrar predicciones reales y reglas agronómicas locales verificadas.
