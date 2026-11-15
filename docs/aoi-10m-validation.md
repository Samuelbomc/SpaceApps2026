# Prueba pública de un área de 10 × 10 m

Se consultaron las siete fuentes NASA sobre el mismo sector alrededor del punto
de referencia de Medellín **6.2442, -75.5812**. No se eligió una finca o región piloto.
El usuario indicó continuar solo con acceso público; no se usaron credenciales.

## Área y periodos

El bbox se construyó con desplazamientos geodésicos WGS84 de 5 m desde el centro
hacia cada punto cardinal. Se verificaron dimensiones y área con GeographicLib:

```text
oeste: -75.58124518203465
sur:     6.244154786897631
este:  -75.58115481796534
norte:   6.244245213102294

ancho en el centro:  10.000000001 m
alto en el centro:   9.9999999999 m
área geodésica:     100.000000009 m²
```

La geometría es un rectángulo geográfico local cuyas dimensiones se verifican
geodésicamente; no una delimitación catastral. `area.geojson` conserva el polígono.

Se ejecutaron dos experimentos separados: **2026-01-01 a 2026-01-31** y
**2024-01-01 a 2024-01-31**. No se mezclaron sus fechas ni se sustituyeron
productos/versiones para ocultar resultados vacíos. Las fechas se consultan en UTC.

POWER se consultó en el centro del área: su endpoint regional exige una ventana
mucho mayor. Para los otros productos se envió a CMR el bbox exacto mostrado.
Seleccionar un archivo por intersección no equivale a recortar ni leer sus píxeles.

## Qué llegó de cada fuente

Se limitó cada catálogo a **tres granules por producto**; las cifras son muestras,
no conteos completos de archivos disponibles.

| Fuente / producto | Enero 2026 | Enero 2024 | Resolución nativa | Qué se obtuvo |
| --- | --- | --- | --- | --- |
| POWER | 186 observaciones | 186 observaciones | Meteorología 0.5° × 0.625°; radiación 1° × 1° | Valores diarios reales y metadatos |
| GPM IMERG Final v07 | 0 archivos | 3 archivos, límite alcanzado | 0.1° | Catálogo; lectura científica HTTP 401 |
| SMAP L4 v008 | 3 archivos, límite alcanzado | 3 archivos, límite alcanzado | 9 km | Catálogo; lectura científica HTTP 401 |
| SRTMGL1 v003 | 1 tile | 1 tile | 1 segundo de arco, aproximadamente 30 m | Catálogo estático; lectura científica HTTP 401 |
| GRACE CRI RL06.3Mv04 | 1 archivo | 1 archivo | Malla de 0.5°, mascons de aproximadamente 3° | Catálogo de archivo con múltiples fechas; lectura HTTP 401 |
| ECOSTRESS ET v003 | 3 archivos, límite alcanzado | 0 archivos | 70 m | Catálogo; lectura científica HTTP 401 |
| ECOSTRESS LST v003 | 3 archivos, límite alcanzado | 0 archivos | 70 m | Catálogo; lectura científica HTTP 401 |
| Landsat HLSL30 v2.0 | 3 archivos, límite alcanzado | 3 archivos, límite alcanzado | 30 m | Catálogo; lectura científica HTTP 401 |

Hay **372 observaciones POWER procesadas** y **25 filas de catálogo normalizadas**
entre ambos experimentos. No se obtuvieron precipitaciones, humedad del suelo,
elevación, pendiente, NDVI o evapotranspiración como valores científicos.

Un detalle relevante: los activos científicos de muestra respondieron **200 a
HEAD**, pero **401 a GET** con `Range: bytes=0-15`. Las comprobaciones GET no usaron
autenticación y no descargaron cuerpos de imágenes. HEAD permitió ver metadatos
como tipo y tamaño del archivo, pero no demostró acceso a su contenido.

Los estados de consulta `ok` indican acceso correcto al catálogo/API, no permiso
de descarga ni calidad científica del píxel. Cada respuesta conserva por separado
`science_values_read`, `access_probe` y `content_access_probe`.

## Ejemplo real de POWER

Valores del **1 de enero de 2026**, consultados en el centro del área:

| Variable | Valor | Unidad reportada |
| --- | --- | --- |
| Temperatura media, `T2M` | 17.19 | C |
| Temperatura mínima, `T2M_MIN` | 15.06 | C |
| Temperatura máxima, `T2M_MAX` | 20.04 | C |
| Humedad relativa, `RH2M` | 93.51 | % |
| Viento a 10 m, `WS10M` | 0.98 | m/s |
| Radiación, `ALLSKY_SFC_SW_DWN` | 15.92 | MJ/m²/día |

En las 372 filas no se detectaron ausentes ni fallos de los controles básicos.
Se conserva `quality="provider_value_unvalidated"`: no hay comparación con estaciones
locales ni validación agronómica. Estos valores representan el soporte espacial
del producto, no una medición independiente de la superficie de 100 m².

## Limpieza y normalización realizadas

**Observaciones POWER:** se reutilizó el procesador existente. Las fechas se
convirtieron de `YYYYMMDD` a fecha ISO/Parquet `date32`; cada variable y día produce
una fila. Se preservan unidades, valores originales, sentinelas, controles básicos,
coordenadas solicitadas/reportadas, resolución, versión de API y procedencia.
Se añadieron `aoi_id` y `spatial_selection="center_point_native_grid"`.

**Catálogos:** se aplanaron fuente, producto, versión, granule, fechas de cobertura,
extensión nativa y enlaces. Las fechas llevan UTC explícito; tamaños inválidos o
no finitos pasan a `null`. El esquema Parquet es explícito y versionado. Los enlaces
de XML, previews o auxiliares no se toman como activos científicos para las sondas.

Los catálogos se guardan separados de las observaciones. Un archivo disponible
no se convierte en una fila climática, una ausencia de archivos no se convierte en
cero y un área de interés no se interpreta como la resolución del sensor.

## Procesamiento que falta por producto

| Fuente | Limpieza/normalización a implementar después de acceder al contenido |
| --- | --- |
| GPM | Leer precipitación, unidades, escala/offset, nodata y tiempo del archivo; seleccionar la celda/recorte; distinguir tasa y acumulado antes de agregar |
| SMAP | Interpretar EASE-Grid y sus coordenadas, seleccionar soporte espacial y variables superficial/radicular; aplicar nodata y calidad; conservar intervalos de 3 horas antes de derivar diarios con cobertura conocida |
| SRTM | Leer elevación, nodata y referencia vertical; para pendiente usar vecinos, como mínimo una ventana de 3 × 3 píxeles, y distancias en metros; un AOI menor que un píxel no basta para derivarla |
| Landsat HLS | Leer B04/B05 y Fmask del mismo granule; aplicar escalas, nodata y máscaras de calidad; calcular NDVI solo para valores válidos y denominador no nulo |
| ECOSTRESS | Leer unidades, nodata, escala y máscaras de cada capa; separar ET diaria de otras estimaciones y LST de temperatura del aire; conservar hora real de adquisición |
| GRACE | Seleccionar periodo y soporte regional del archivo con múltiples fechas; conservar anomalías, unidades y su incertidumbre; no interpretarlo como humedad parcelaria |

Estas operaciones no se simularon ni se ejecutaron sobre imágenes inaccesibles.
Las unidades y máscaras deberán leerse y verificarse en cada producto antes de
convertir valores. La intersección CMR no garantiza píxeles válidos: puede haber
nodata o nubes sobre el sector solicitado.

## Organización propuesta a partir de la prueba

```text
áreas:       aoi_id, geometría, centro, dimensiones, CRS
catálogos:   aoi_id, fuente, producto, versión, granule_id, cobertura, enlaces
observaciones:
  aoi_id, soporte/celda nativa, fuente, variable, fecha/intervalo,
  valor, unidad, calidad, resolución, versión y procedencia
features:
  derivadas posteriormente con reglas espaciales/temporales versionadas
```

Para unir fuentes se necesitarán reglas explícitas: relación área–celda, ventanas
de tiempo, agregación por variable y cobertura mínima válida. No corresponde unir
simplemente por coordenadas y fecha ni interpolar todo a 10 m. HLS y SRTM pueden
intersectar uno o varios píxeles según los bordes de la malla, pero no resuelven
por sí solos variaciones internas a 10 m. SMAP, GPM y GRACE aportan contexto de
escalas mucho mayores. Ninguno de estos productos representa una cuadrícula
nativa de 10 × 10 m para esta prueba.

## Artefactos y reproducción

Resultados completos locales, excluidos de Git:

```text
data/probes/medellin-10m-2026-01/
data/probes/medellin-10m-2024-01/
  area.geojson
  request.json
  raw/power-result.json
  raw/catalog-results.json
  power-observations.parquet
  granule-catalog.csv
  granule-catalog.parquet
  summary.json
```

Una muestra pequeña revisable está en [samples/aoi-10m](../samples/aoi-10m/README.md).
La ejecución usa directorios vacíos para no mezclar evidencias de pruebas previas:

```bash
python -m pip install '.[storage,geospatial]'

python -m scripts.probe_area \
  --latitude 6.2442 --longitude -75.5812 --side-m 10 \
  --start 2026-01-01 --end 2026-01-31 --limit 3 \
  --directory data/probes/mi-prueba-10m-2026-01

python -m scripts.probe_area \
  --latitude 6.2442 --longitude -75.5812 --side-m 10 \
  --start 2024-01-01 --end 2024-01-31 --limit 3 \
  --directory data/probes/mi-prueba-10m-2024-01
```

Las pruebas validan dimensiones, geometría, separación centro/bbox, esquemas,
conservación de valores y sondeos GET acotados incluso si el servidor ignora Range.
Para completar la extracción satelital harán falta credenciales/autorizaciones
Earthdata, fuera del alcance público elegido para esta ejecución.

## Fuentes oficiales de referencia

- [POWER: resolución nativa y solicitudes](https://power.larc.nasa.gov/docs/tutorials/service-data-request/api/).
- [CMR: selección espacial y temporal](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html).
- [SMAP L4 v8: resolución, asimilación y acceso](https://nsidc.org/data/spl4smgp/versions/8).
- [SRTMGL1: resolución y tiles](https://doi.org/10.5067/MEaSUREs/SRTM/SRTMGL1.003).
- [HLS: guía y calidad](https://hls.gsfc.nasa.gov/documents/).
- [GRACE: producto CRI](https://podaac.jpl.nasa.gov/dataset/TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4).
