# Validación de clientes NASA

## Backend, job y frontend inicial

Se verificaron **78 pruebas** con PostgreSQL temporal real, incluyendo migraciones
idempotentes, upsert y lectura HTTP, calendario persistente de 604800 segundos,
bloqueo entre workers, reintentos y catálogos de otras fuentes ante un fallo POWER.
Los tipos del frontend se generan desde el OpenAPI de FastAPI y se comprueba
que los artefactos correspondan al contrato actual.

Next.js completó comprobación de tipos y build de producción. El recorrido HTTP
Next.js → FastAPI → PostgreSQL leyó **32 observaciones NASA POWER reales** del
2025-12-25 al 2026-01-01. La consulta de análisis informó `pending_model` y ninguna
predicción inventada. El resultado está en `data/manifests/application-smoke.json`.

Se validó la configuración Docker Compose, pero el motor Docker no respondió y
no se activaron contenedores ni el job permanente. Los procesos temporales de
prueba fueron cerrados. No hubo QA visual automatizado en navegador. Los comandos,
interfaces y límites están en [development.md](development.md).

## AOI de 10 × 10 m con acceso público

Se ejecutaron consultas reales para un área WGS84 verificada de aproximadamente
100 m² alrededor de 6.2442, -75.5812, en enero de 2026 y enero de 2024. Se obtuvieron
372 observaciones POWER y 25 filas de catálogo normalizadas. Las lecturas GET
acotadas de los activos científicos de muestra devolvieron HTTP 401, aunque sus
cabeceras HEAD eran públicas. No se leyeron píxeles de esos productos.

El [informe completo](aoi-10m-validation.md) separa ambos periodos, documenta
el tratamiento de POWER y catálogos, y define las siguientes etapas de limpieza
sin atribuir resolución de 10 m a productos de resolución más gruesa.

## POWER histórico, procesamiento y almacenamiento

Se ejecutó el flujo `power-sync` contra NASA con el punto de referencia
**6.2442, -75.5812**, fechas inclusivas **2020-01-01 a 2025-12-31** y variables
`T2M`, `RH2M`, `WS10M`, `ALLSKY_SFC_SW_DWN`.

| Verificación | Resultado |
| --- | --- |
| Ingesta inicial | 8768 observaciones en 2192 fechas, cuatro variables |
| Persistencia | Seis archivos Parquet anuales y respuestas originales archivadas |
| API reportada | `v2.10.3` |
| Calidad básica | 8768 filas `provider_value_unvalidated`, sin huecos para esas variables/fechas |
| Repetición exacta | Cero bloques consultados, cero inserciones, cero actualizaciones |
| Extensión a 2026-01-01 | Un bloque de un día y cuatro inserciones adicionales |
| Estado tras extensión | 8772 observaciones únicas; sin días pendientes |

Se usó PyArrow **26.0.1** para verificar escritura y lectura reales. Las pruebas
automatizadas cubren nodata, datos inválidos, unidades ausentes, valores fuera
de rango, backfill de variables nuevas, recuperación de huecos, revisiones,
reanudación tras fallo de red y conservación del archivo anterior ante fallo de
escritura. La consulta final verificó unicidad y existencia de todos los originales
referenciados por las observaciones guardadas.

Los informes locales están en `data/manifests/power-medellin-2020-2025.json`,
`power-medellin-repeat.json` y `power-medellin-increment.json`. El punto de Medellín
es una referencia de validación técnica, no una selección de región piloto ni
validación agronómica. No se entrenó ni evaluó un modelo con estos datos.

## Consulta unificada por punto

Se probó `collect` contra los proveedores reales con latitud **6.0**, longitud
**-75.0**, periodo **2026-01-01 a 2026-01-31** y límite de un granule por producto.
Las ocho entradas compartieron el mismo `query_id` y contexto solicitado:

| Fuente / producto | Resultado |
| --- | --- |
| POWER | `ok`, respuesta puntual diaria |
| GPM IMERG Final | `empty`, sin granules para esa consulta |
| SMAP | `ok`, un granule |
| SRTM | `ok`, un tile, sin filtro temporal |
| GRACE | `ok`, un archivo con múltiples fechas |
| ECOSTRESS ET | `ok`, un granule |
| ECOSTRESS LST | `ok`, un granule |
| HLS Landsat | `ok`, un granule |

La salida está en `data/manifests/unified-point-smoke.json`. El estado global
`ok` indica consultas sin error; no implica cobertura en todas las fuentes.
No se rellenó GPM con ceros ni se cambió silenciosamente de periodo o producto.
Se validó el envío del punto, no la extracción o coincidencia de píxeles raster.

Las pruebas automatizadas adicionales verifican el contrato por punto y bbox,
orden longitud/latitud en CMR, correlación común, fechas obligatorias, ausencia
de radios implícitos, conservación de nodata y éxitos parciales.

## Comprobaciones iniciales

Comprobaciones ejecutadas el **14 de noviembre de 2026**, usando el bbox
`[-75.5830, 5.4110, -74.6167, 6.5866]` y respuestas reales de los proveedores.
Las muestras locales se guardan en `data/`, fuera del control de versiones.

Estas comprobaciones corresponden a los clientes iniciales. La reorganización en
repositorios mantiene los consumos HTTP y CMR. El comando `power` ahora devuelve
respuestas originales mediante `PowerRepository`; los 34 registros normalizados
de la tabla corresponden a la utilidad de normalización inicial. Ahora está en
`pipelines/processing/cleaning/power.py::normalize_power_daily`, fuera del cliente
de ingesta y del contrato de los repositorios.

| Fuente / producto | Periodo consultado | Resultado de la muestra |
| --- | --- | --- |
| POWER, seis variables predeterminadas | 2024-01-01 a 2024-01-02 | 34 registros normalizados dentro del bbox; API v2.10.3 |
| GPM IMERG Final v07 | Enero de 2024 | 2 granules recuperados, límite de prueba alcanzado |
| SMAP L4 v008 | Enero de 2024 | 2 granules recuperados, límite de prueba alcanzado |
| SRTMGL1 v003 | Sin filtro temporal | 2 tiles recuperados, límite de prueba alcanzado |
| GRACE CRI RL06.3Mv04 | Enero de 2024 | 1 archivo con múltiples fechas |
| ECOSTRESS ET v003 | Enero de 2024 | 0 granules |
| ECOSTRESS LST v003 | Enero de 2024 | 0 granules |
| ECOSTRESS ET v003 | 2026-01-01 a 2026-11-14 | 1 granule recuperado (límite 1); fecha inicial 2026-01-09 |
| ECOSTRESS LST v003 | 2026-01-01 a 2026-11-14 | 1 granule recuperado (límite 1); fecha inicial 2026-01-02 |
| HLS Landsat L30 v2.0 | Enero de 2024 | 2 granules recuperados, límite de prueba alcanzado |

Los conteos están limitados deliberadamente y **no son inventarios completos**.
Los intervalos CMR se basan en solapamiento: un granule puede empezar antes de
la fecha inicial y terminar dentro del intervalo solicitado. Esto ocurrió en SMAP.

Se comprobaron nombre, versión y proveedor de cada colección. Se obtuvieron
enlaces HTTPS de datos, excluyendo enlaces heredados, previews y servicios.
Algunos DAAC también etiquetan archivos auxiliares como GET DATA; los patrones
`--asset` permiten elegir los archivos científicos y de calidad necesarios.

El endpoint regional POWER rechazó inicialmente el bbox por ser menor de 2°
por eje (HTTP 422). Se comprobó el ajuste a `[-76, 5, -74, 7]` y el filtrado de
puntos al bbox original. Las variables meteorológicas y solares pueden tener
distintos puntos de respuesta y resoluciones; no deben contarse como estaciones
independientes ni combinarse espacialmente sin definir una política de alineación.

## Límites de lo verificado

Las consultas POWER y CMR se ejecutaron contra servicios reales. La ruta de
descarga se verificó con sesiones simuladas: selección de archivos, escritura,
checksum, reutilización, rechazo de HTML/archivos incompletos y límites de bytes.
No se ejecutaron descargas protegidas con una cuenta Earthdata y no se instaló
el extra `earthaccess` en esta sesión. Esa integración requiere validación con
credenciales del proyecto y espacio disponible.

No se validaron valores raster, máscaras, unidades internas, modelos ni precisión
agronómica. Las versiones se mantienen fijas para reproducibilidad; la disponibilidad
de colecciones y archivos puede cambiar y debe revisarse antes de una ingesta histórica extensa.
