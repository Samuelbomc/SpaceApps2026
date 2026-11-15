# Desarrollo: ingesta, ciclo ML, persistencia y aplicación

PostgreSQL conserva identidad, fincas, observaciones recientes y programación.
MongoDB almacena resultados, catálogo agronómico, métricas y registro ML en el
nuevo despliegue. El histórico procesado y los snapshots siguen en Parquet.
La aplicación muestra datos y estados aunque no haya modelos entrenados.
La guía de [reentrenamiento autónomo](autonomous-training.md) describe los tres
jobs, la promoción condicional y los adapters científicos todavía pendientes.

## Ejecutar con Docker

```bash
cp .env.example .env
docker compose up --build -d
```

Servicios: MongoDB en la red interna de Compose, PostgreSQL en `localhost:5432`, FastAPI en `http://localhost:8000`,
documentación interactiva en `http://localhost:8000/docs` y frontend en
`http://localhost:3000`. Los puertos publicados se enlazan solo a loopback.
El password de ejemplo es únicamente de desarrollo; reemplazarlo para otro entorno.
No sobrescribir un `.env` existente con credenciales propias.

La API y los tres workers aplican migraciones versionadas bajo un bloqueo PostgreSQL. La
región inicial es el punto de referencia técnica ya usado, configurable con
`REGION_ID`, `REGION_NAME`, `REGION_LATITUDE` y `REGION_LONGITUDE`. Registrar una
ubicación de referencia no la convierte en una región piloto validada.

## Ejecutar por separado

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install '.[api,storage,geospatial,test]'

docker compose up -d postgres
python -m scripts.migrate
uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000
```

En otra terminal con el entorno activado:

```bash
python -m scripts.worker --job ingestion
```

Frontend:

```bash
cd apps/web
npm ci
npm run dev
```

`DATABASE_URL` se configura por entorno. La CLI Python no carga `.env`
automáticamente; Docker Compose sí usa el archivo. Para desarrollo local se
puede exportar `DATABASE_URL` o utilizar el valor local de ejemplo.
`API_INTERNAL_URL` es una URL del servidor Next.js; el navegador usa el proxy
del mismo origen `/backend/*`, sin recibir credenciales de PostgreSQL.

## Job cada siete días

`scripts/worker.py` es un proceso independiente de FastAPI. El intervalo guardado
en `job_schedules` es **604800 segundos**, es decir, 168 horas. No usa una
expresión cron `*/7`, que no representa de forma general un intervalo de siete días.

- La migración registra la primera ejecución como inmediatamente pendiente.
- La próxima fecha se persiste en PostgreSQL y sobrevive reinicios.
- Un advisory lock impide que dos workers ejecuten el mismo job simultáneamente.
- Se conserva el calendario anclado al slot original; al reiniciar se omiten
  slots pasados y se realiza una actualización, sin lanzar una por semana perdida.
- Una ejecución parcial/fallida registra fuentes pendientes y contador de fallos
  en PostgreSQL. Reintenta después de 1, 2, 4, 8, 16 y luego 24 horas entre intentos,
  respetando una espera mayor indicada por NASA mediante `Retry-After`.
- Los reintentos recuperan únicamente las fuentes fallidas. Al vencer el siguiente
  ciclo semanal se vuelven a consultar todas las fuentes, evitando dejar sin
  actualizar aquellas que funcionaban. Una espera pendiente del proveedor puede
  retrasar ese disparo; el worker nunca consulta antes del reintento autorizado.
- El calendario semanal se conserva separado de la recuperación. Tras recuperar
  las fuentes se limpian contador y pendientes; los datos existentes no se borran
  por una falla de red. Una caída total sin resultado obliga a repetir la ejecución.
- `--job ingestion --once` ejecuta únicamente la ingesta bajo el mismo bloqueo;
  los jobs dependientes quedan pendientes después de una actualización exitosa.

```bash
python -m scripts.worker --job ingestion --once
```

El worker debe permanecer ejecutándose, o estar administrado por Docker con
su política de reinicio, para que el job se dispare. Guardar una fila de calendario
no crea una automatización en el sistema operativo. No se instaló un servicio
host ni se publicó el proyecto.

El job procesa POWER con el flujo incremental existente y guarda la ventana
reciente en PostgreSQL después de escribir Parquet. `RECENT_OBSERVATION_DAYS`
vale 90 por defecto y `INGESTION_LAG_DAYS` vale 3. La ventana no sustituye una
validación de disponibilidad real; las observaciones faltantes quedan señaladas.
Para GPM, SMAP, SRTM, ECOSTRESS, HLS y GRACE se guardan catálogos y estados por
fuente: todavía no se descargan ni procesan sus archivos científicos protegidos.

Un catálogo vacío se registra como vacío, no como precipitación cero. Los errores
de una fuente no descartan los catálogos de las otras. El estado de ingesta y la
disponibilidad de modelos se mantienen separados. El job de entrenamiento revisa
el histórico por separado y solo publica si hay etiquetas suficientes y una
validación aprobada; no se publica un modelo por el mero paso de siete días.

## Resiliencia HTTP y recuperación

El cliente JSON realiza hasta tres intentos por GET para errores transitorios
(408, 429, 500, 502, 503, 504), desconexiones, timeouts y JSON inválido/incompleto.
La espera exponencial incorpora una variación aleatoria pequeña para evitar que
varios clientes repitan a la vez. Los errores 401, 403 y de validación no se
reintentan dentro de la misma petición: requieren revisar acceso o parámetros.
Si persisten, el job conserva el fallo y vuelve a evaluar la fuente más adelante.

`Retry-After` admite segundos y fecha HTTP. Esperas de hasta 60 segundos se
realizan en el cliente; las mayores se trasladan al scheduler persistente. El
último intento también conserva esa indicación para la siguiente ejecución.

`GET /api/v1/status` expone `schedule.pending_sources`, `consecutive_failures`,
`retry_at` y el último error. El frontend muestra las fuentes pendientes. Los
catálogos vacíos son respuestas válidas, no fallos de transporte. Los huecos de
POWER siguen marcados como incompletos y pendientes; nunca se convierten en cero.
Una ingesta incompleta deja fuentes pendientes; los jobs ML mantienen sus
calendarios y solo pueden usar observaciones válidas ya disponibles. Reintentar mejora
la recuperación, pero no garantiza disponibilidad ni publicación de datos por NASA.
Las descargas protegidas siguen fuera del job público actual.

## Persistencia PostgreSQL

`infra/database/migrations/001_initial.sql` crea:

| Tabla | Contenido |
| --- | --- |
| `regions` | Ubicaciones de referencia configuradas |
| `observations` | Ventana reciente de observaciones, con identidad única y metadatos JSONB |
| `ingestion_runs` | Ejecuciones, tiempos y estados reales |
| `source_snapshots` | Catálogos/metadatos por fuente y ejecución |
| `job_schedules` | Intervalo, próximo slot, reintento y último error |
| `analyses` | Resultados del adapter de compatibilidad `RESULTS_BACKEND=postgresql` |

La migración `002_ingestion_retries.sql` agrega el contador de fallos y las
fuentes pendientes al calendario; no modifica `001_initial.sql` ya aplicada.
La migración 003 añade identidad y fincas privadas. La 004 añade los dos
calendarios ML, el último resultado del job y `ml_records` para el adapter local.
Con `RESULTS_BACKEND=mongodb`, análisis y registro ML se leen y escriben en
MongoDB; no se duplican ni se migran automáticamente desde PostgreSQL.

Los originales compactos y todo el histórico Parquet siguen fuera de la base
operativa. Las consultas SQL usan parámetros; no se devuelven cadenas de conexión
en los errores HTTP. La integración actual no requiere PostGIS.

## Contrato FastAPI ↔ frontend

| Método y ruta | Comportamiento |
| --- | --- |
| `GET /api/v1/health` | Liveness de la API; no certifica conexión a la base |
| `GET /api/v1/regions` | Ubicaciones configuradas |
| `GET /api/v1/status` | Adapters configurados, calendario y últimas ingestas |
| `GET /api/v1/automation` | Backend de resultados, tres calendarios, versiones publicadas y estado de entrenamiento |
| `GET /api/v1/regions/{id}/observations?limit=1000&offset=0` | Todo el histórico PostgreSQL por páginas, total y última actualización |
| `GET /api/v1/regions/{id}/analyses` | Análisis almacenados |
| `GET /api/v1/regions/{id}/latest-analysis?horizon_days=7` | Resultado o estado para la última observación válida disponible; `null` si no hay observaciones |
| `POST /api/v1/analyses` | Consulta por región, último día histórico y horizonte; devuelve un resultado existente o su estado pendiente |

La API de lectura no consulta NASA ni ejecuta modelos. El contrato distingue:

- `reference_date`: fecha de corte de las observaciones de entrada.
- `forecast_start_date`: primer día del periodo objetivo.
- `horizon_days`: cantidad de días del periodo objetivo, contando el primero.

`GET latest-analysis` acepta `as_of`, que por defecto es el día actual en
America/Bogota. Consulta la última observación válida anterior a ese día, pero
el periodo de predicción comienza en `as_of`, independientemente de la antigüedad
de los datos. Para una consulta del 14 de noviembre y un plazo de siete días,
el intervalo objetivo va del 14 al 20, ambos incluidos. El frontend no utiliza campos Desde/Hasta: ambos perfiles consultan todos los
registros almacenados para la ubicación. La exploración técnica conserva sus
series históricas y sus fechas reales en los ejes y registros.

La identidad del resultado incluye región, corte de entradas, inicio objetivo y
horizonte. No se cambia la etiqueta de un forecast antiguo para presentarlo como
actual. Si el resultado exacto no existe, devuelve el estado pendiente; si no hay
observaciones válidas devuelve `null`. La pantalla muestra por separado el
periodo solicitado y la fecha de las últimas observaciones. Una programación
semanal no garantiza que NASA publique datos nuevos cada semana.

Para compatibilidad con consultas históricas, `POST /analyses` admite omitir
`forecast_start_date`: en ese caso el periodo comienza al día siguiente del corte.
Los modelos deben devolver el inicio objetivo explícito para consultas actuales;
el servicio rechaza otro periodo. Un adaptador debe validar variables, lags,
cobertura y el desfase entre entradas y periodo objetivo. No basta con desplazar
las fechas de las salidas de un modelo entrenado para otro horizonte.

El entrenamiento y validación aprovecharán el histórico procesado en Parquet,
con separación temporal para evaluar sin utilizar datos futuros. La inferencia
utilizará las variables y los rezagos que exija el modelo entrenado. El servicio
actual reserva 90 días como contrato provisional; no envía todo el histórico en
cada predicción y todavía no hay modelos entrenados. El job admite adaptadores y
actualmente solicita siete días desde el día de ejecución; se debe habilitar y
validar la generación de los demás horizontes al conectar los modelos.

El selector ofrece 7, 15, 30 y 60 días y cancela la solicitud anterior al cambiar.
La fecha de consulta usa America/Bogota; el límite de datos conserva sus fechas
UTC de origen. El modo Sencillo prioriza el periodo, las predicciones y las
alternativas de cultivo, seguidos por las últimas condiciones conocidas. No
presenta paneles de ingesta, gráficos de control ni registros en bruto. Su
contexto meteorológico se consulta desde el corte más reciente, independientemente
del periodo que se haya explorado en el otro perfil.

El modo Técnico prioriza la exploración del histórico: serie por fuente, variable,
unidad y resolución; conteos de calidad y nulos; días recibidos; registros
paginados; estado de ingesta y trazabilidad de modelos y entradas. Los gráficos
no unen huecos ni mezclan distintas fuentes o unidades. Estos conteos describen
los registros recibidos y no certifican cobertura completa de los productos.
No se inventan métricas de validación, incertidumbre ni recomendaciones.

Los DTOs Pydantic viven en `packages/contracts/api.py`. OpenAPI y los tipos
TypeScript se generan juntos y se guardan en `packages/contracts/`:

```bash
python -m scripts.export_openapi
cd apps/web
npm run typecheck
npm run build
```

`scripts/export_openapi.py` genera la forma estática TypeScript del subconjunto
de JSON Schema utilizado por estos DTOs y falla ante tipos no soportados. Las
restricciones de valores permanecen en Pydantic/OpenAPI. Una prueba comprueba
que ambos artefactos generados correspondan a la API actual.

## Interfaces para ML y recomendaciones

`ml/inference/contracts.py` define tres puertos:

```text
ClimatePredictor.predict(request, observations) -> Forecast
SoilPredictor.predict(request, observations, climate) -> Forecast
RecommendationEngine.recommend(request, climate, soil) -> Recommendations
```

`AnalysisService` ordena clima → suelo → motor agronómico, verifica región,
fecha/horizonte/tipo de cada forecast, calcula una huella de entradas y guarda
salidas idempotentes. Los adaptadores futuros deben validar sus variables, unidades,
lags y preprocesamiento antes de predecir. La ventana inicial del servicio es de
90 días, pendiente de ajustar a los requisitos de los modelos validados.

`WeeklyIngestionJob` admite inyectar ese servicio cuando existan adaptadores
válidos. Por defecto no hay modelos ni reglas ficticias. Los estados HTTP son
`pending_model`, `pending_run`, `insufficient_data`, `pending_recommendations`
y `ready`; este último exige ambos forecasts y al menos tres alternativas.

El frontend inicial consulta región/periodo, muestra mapa de referencia,
observaciones y calidad, programación y secciones de análisis/recomendaciones.
Tiene estados de carga, vacío y error; no presenta números inventados para rellenar
tarjetas cuando el backend o los modelos no están disponibles.

## Verificación

```bash
python -m unittest discover -s . -p 'test_*.py' -v

# Habilitar los tests reales de DB contra una base de pruebas:
TEST_DATABASE_URL=postgresql://... python -m unittest tests.test_postgres -v
```

Las pruebas PostgreSQL crean y eliminan un esquema propio, sin truncar tablas del
proyecto. Alternativamente `scripts.verify_postgres` puede iniciar un servidor
temporal si está instalado el paquete opcional de verificación `embedded-postgres`.
No es una dependencia de producción.

En esta sesión se verificaron migraciones, upserts, API y scheduler contra PostgreSQL
temporal real. Docker no respondió al ping, por lo que los contenedores y el job
permanente no se activaron. La configuración Compose se valida por separado del
funcionamiento del motor Docker. No hay despliegue ni modelos entrenados.

La verificación final pasó **99 pruebas Python y 12 pruebas de presentación**, incluyendo integración contra PostgreSQL
real temporal. Next.js pasó comprobación de tipos y compilación de producción
con su compilador nativo. El smoke HTTP ejecutó Next.js → FastAPI → PostgreSQL y
leyó **32 observaciones POWER reales** del periodo 2025-12-25 a 2026-01-01;
la solicitud de análisis devolvió `pending_model`, sin forecasts ficticios.
El informe local está en `data/manifests/application-smoke.json`.

```bash
# Opcional, requiere el paquete de verificación embedded-postgres y una build del frontend:
python -m scripts.verify_stack
```

Esta prueba usa puertos libres 3000/8000 y cierra sus servidores al finalizar.
No se realizó verificación visual automatizada en navegador; la validación del
frontend cubre compilación, tipos y recorrido HTTP. No dejó un worker permanente
ejecutándose. Tras iniciar Docker Desktop, el comando Compose indicado arriba
levanta la base, API, worker y frontend con persistencia local.


## Datos recientes y mapa de selección

La vista previa local ahora utiliza la muestra pública de POWER de 2026-10-29 a
2026-11-11. El selector Leaflet permite delimitar cuadrados o rectángulos y
exportar GeoJSON. No dispara consultas NASA ni cambia los datos de referencia.
La selección se distingue expresamente de un recorte científico. Ver
[validación y tamaños de fuente](recent-data-and-area-selection.md).

```bash
cd apps/web
npm test
```

Las pruebas de geometría verifican dimensiones pequeñas, orden de coordenadas,
cierre del polígono y rechazo de áreas inválidas. El render del mapa se revisó en una captura real de Chrome aislado. Los clics de
delimitación y la descarga GeoJSON deben revisarse manualmente; tipos y
compilación no validan esas interacciones.


## Histórico completo y última actualización

La consulta de observaciones admite omitir ambas fechas para recorrer todo lo
almacenado en PostgreSQL, con orden determinista y paginación `limit`/`offset`.
La respuesta incluye `total`, `first_date`, `last_date` y `last_updated_at`.
Este último es el máximo `updated_at` de las observaciones persistidas de la
ubicación: no es la fecha de la última observación del satélite, ni una garantía
de que todos los datos estén completos o validados.

`loadObservationHistory` recorre todas las páginas, incluso por encima de 10000
registros. Si los metadatos cambian mientras se leen páginas, reinicia una vez y,
si el cambio persiste, informa un error en vez de mostrar un histórico parcial
como completo. Una base sin observaciones devuelve total cero y actualización
nula. Ambos perfiles comparten esta misma colección; la vista sencilla resume
las últimas condiciones y la técnica explora las series y registros.

La interfaz muestra **Última actualización de los datos** y permite refrescar
la lectura de la base. No filtra por 30 o 90 días ni envía fechas a ese endpoint.
El selector de 7/15/30/60 días sigue siendo el horizonte de las predicciones,
contado desde el día de consulta. El intervalo de entradas de cada futuro modelo
se debe definir al entrenarlo, independientemente de los filtros de interfaz.

Esta consulta abarca PostgreSQL; no modifica la política de retención operativa
ni importa automáticamente a la base todo el histórico Parquet externo. Las
fechas opcionales del endpoint se conservan para compatibilidad con herramientas
de diagnóstico anteriores, pero ya no se utilizan desde el frontend.


## Cuentas y catálogo de fincas

Las pantallas `/registro`, `/login` y `/fincas` permiten gestionar datos privados.
La migración 003 agrega cuentas, sesiones, fincas, metadatos de datasets y
observaciones locales; no mezcla esas mediciones con la tabla pública NASA.
La ejecución actual usa `scripts.dev_stack` y PostgreSQL persistente en
`data/local/postgres`, reemplazando la vista previa temporal para este flujo.
Los CSV privados se conservan en `data/farms`, fuera de las carpetas públicas.

La documentación de contratos, límites, seguridad de sesión, preparación para
modelos y ejecución local está en [farmer-accounts.md](farmer-accounts.md).
La verificación de automatización amplía las pruebas de cuentas con validación
temporal, promoción, artefactos, reintentos y MongoDB real. Consulta
[autonomous-training.md](autonomous-training.md) para los comandos y estados.
Las 14 pruebas de presentación/contrato frontend siguen disponibles.
