# Datos recientes y selección de áreas pequeñas

Validación pública del 14 de noviembre de 2026 en el punto de referencia existente
(6.2442, -75.5812). Esta ubicación técnica no se presenta como una parcela rural
validada. Periodo consultado: **29 de octubre a 11 de noviembre de 2026**.

## Datos realmente obtenidos

| Fuente/producto | Resultado de la consulta de 10 × 10 m |
| --- | --- |
| POWER | 84 registros normalizados: 70 valores con control básico y 14 ausentes de radiación solar |
| GPM IMERG Final | Sin granules en este periodo; no equivale a precipitación cero |
| SMAP L4 v008 | 3 granules de catálogo, búsqueda limitada; GET científico respondió 401 |
| SRTMGL1 v003 | 1 granule estático; GET científico respondió 401 |
| GRACE mascons | Sin granules para el intervalo solicitado |
| ECOSTRESS ET v003 | Sin granules para el área y periodo solicitados |
| ECOSTRESS LST v003 | 3 granules de catálogo, búsqueda limitada; GET científico respondió 401 |
| Landsat HLSL30 v2 | 1 granule de catálogo; GET científico respondió 401 |

Solo POWER tiene extracción científica en esta prueba. Los valores ausentes se
conservan como nulos; no se imputaron ni se convirtieron en cero. El resto aporta
metadatos de archivos que intersectan el AOI, sin lectura de píxeles ni comprobación
de nubes. Los archivos protegidos siguen requiriendo una cuenta Earthdata; no se
configuraron credenciales ni se efectuaron descargas grandes.

El diagnóstico adicional de **GPM IMERG Early (GPM_3IMERGDE v07)** sí encontró
archivos diarios del 9, 10 y 11 de noviembre. Es únicamente descubrimiento público,
no valores de precipitación ni una sustitución silenciosa del producto Final.
NASA distingue [Early, Late y Final](https://gpm.nasa.gov/resources/documents/imerg-v07-technical-documentation)
por su latencia; Final está orientado a investigación con meses de retraso.

En el último día válido, 11 de noviembre, POWER devolvió para el punto:

- Temperatura media: 18.60 °C.
- Humedad relativa: 82.56 %.
- Viento a 10 m de altura: 0.61 m/s.
- La radiación solar se mantiene sin dato en el periodo consultado.

Los valores y unidades originales se conservan en el archivo de observaciones.
No se efectuaron inferencias agronómicas ni recomendaciones de cultivos.

## Resolución de las fuentes

| Producto integrado | Tamaño de celda/posteo o soporte espacial nominal |
| --- | --- |
| [POWER](https://power.larc.nasa.gov/docs/tutorials/service-data-request/api/) | Meteorología 0.5° × 0.625°; aproximadamente 55 × 69 km a esta latitud. Solar: 1° × 1° según el tutorial de API |
| [GPM IMERG](https://gpm.nasa.gov/resources/documents/imerg-v07-technical-documentation) | 0.1° × 0.1°, aproximadamente 11 × 11 km |
| [SMAP L4](https://nsidc.org/data/spl4smgp/versions/8) | Cuadrícula de 9 km; producto de asimilación/modelo |
| [SRTMGL1](https://www.earthdata.nasa.gov/s3fs-public/2025-05/SRTM_Quick_Guide.pdf) | 1 segundo de arco, aproximadamente 30 m; elevación estática de la misión de 2000 |
| [Landsat HLSL30](https://hls.gsfc.nasa.gov/products-description/) | Píxeles de 30 m |
| [ECOSTRESS ET](https://data.nasa.gov/dataset/ecostress-tiled-evapotranspiration-pt-jpl-instantaneous-and-daytime-l3-global-70-m-v003) | Cuadrícula de 70 m; cobertura y calidad dependen de cada adquisición |
| [GRACE JPL mascons](https://podaac.jpl.nasa.gov/dataset/TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4) | Mascons independientes de 3°, de escala regional; salida muestreada a 0.5°, que no representa detalle independiente de 0.5° |

**Delimitar un terreno no aumenta la resolución de las observaciones.** Un área
10 × 10 m puede ser menor que un píxel y compartir valores con las áreas vecinas.
El tamaño de píxel tampoco garantiza exactitud de medición de ese mismo tamaño.

La prueba empírica pidió T2M y RH2M de los días 10 y 11 de noviembre para el punto
original y para puntos a 10 y 100 metros al este, calculados sobre WGS84. Las tres
series fueron exactamente iguales. Esto demuestra el comportamiento en estos
puntos y fechas; no garantiza igualdad en toda ubicación, ni mide precisión.

## Selección en el mapa

El frontend usa Leaflet 1.9.4 sobre OpenStreetMap, con atribución visible. Permite:

1. Escribir un tamaño libre, con decimales, para un cuadrado y colocarlo con un clic.
2. Marcar el cuadrado alrededor del centro del mapa usando un botón accesible.
3. Indicar siempre una superficie: metros cuadrados (m²), kilómetros cuadrados
   (km²) o hectáreas (ha). Por ejemplo, 1000 m² = 0,001 km² = 0,1 ha forman un
   cuadrado de unos 31,62 m de lado. Cambiar de unidad conserva su tamaño.
   Editar la superficie redimensiona el cuadrado en su ubicación y mantiene el
   zoom, para comparar proporciones sobre el mismo mapa. La primera selección
   se encuadra una sola vez; «Ver área completa» permite encuadrarla de nuevo.
4. Revisar dimensiones/superficie aproximadas, bbox en vista técnica y exportar GeoJSON.

La geometría local del navegador usa aproximación esférica y admite lados de
1 m a 10 km de lado (0,0001 a 10000 ha). El mismo selector se usa en la ficha
privada de la finca. Los límites antiguos guardados se conservan al abrir una ficha;
las nuevas delimitaciones siempre son cuadradas. Es un límite de este prototipo, no un
límite de las APIs NASA. La prueba científica de 10 m usa WGS84 y validación
geodésica del pipeline, independiente de esa aproximación de interfaz.

**La selección es una prueba geométrica:** no está conectada a una nueva ingesta,
no cambia la región de los indicadores existentes y no aplica recorte raster ni
inferencia por parcela. La interfaz lo indica al delimitar un área. La integración
posterior debe conservar el AOI y la celda/soporte de cada fuente, aplicar máscaras
de calidad y comunicar qué fuentes permiten distinguir sectores de la parcela.

## Evidencia reproducible

```bash
python -m scripts.probe_area --latitude 6.2442 --longitude -75.5812 \
  --side-m 10 --start 2026-10-29 --end 2026-11-11 --limit 3 \
  --directory data/probes/otra-ejecucion-reciente
```

La prueba exige un directorio vacío para no mezclar ejecuciones. Evidencia local:

- `data/probes/recent-20261114-aoi10m/summary.json`.
- `power-observations.parquet`, `raw/power-result.json` y `raw/catalog-results.json`.
- `power-nearby-comparison.json` y `gpm-early-diagnostic.json`.

Las 84 filas también se incorporaron al repositorio Parquet incremental del punto.
La vista previa temporal se carga con estas observaciones y los snapshots de los
catálogos. La muestra incompleta se registra como ejecución parcial; no se activó
un worker permanente ni se generan predicciones sin modelos.


## Verificación de la interfaz

La compilación de producción y ocho pruebas de presentación/geometría pasaron.
La API de la vista previa devolvió las 84 filas recientes y tomó 2026-11-11 como
corte de observaciones. Se revisó una captura real de Chrome headless con perfil
local aislado: el mapa y los controles se renderizan con las teselas y atribución
OpenStreetMap. No se automatizaron los clics de delimitación ni la descarga del
GeoJSON; estas interacciones deben revisarse manualmente en la vista local.


## Lugar del centro del mapa

El selector de regiones se reemplazó en la interfaz por «Explorando en el mapa».
La marca central identifica el punto consultado. Al terminar un movimiento se
esperan 900 ms y se consulta `GET /api/v1/places/reverse`; se descartan respuestas
anteriores cuando cambia el centro. Si no hay nombre disponible, se muestran
coordenadas, sin reutilizar como nombre la región de las observaciones NASA.

El servicio usa [Photon sobre OpenStreetMap](https://github.com/komoot/photon),
con URL sustituible mediante `GEOCODER_URL`. Redondea el punto a tres decimales,
cachea resultados, limita las consultas del proceso a una cada 1,1 segundos y
restringe los reintentos del navegador. La instancia pública de Photon ofrece
uso moderado sin garantía de disponibilidad; se puede configurar una propia.
La atribución OpenStreetMap permanece visible. La ficha privada de fincas no
activa esta búsqueda de nombres. Este endpoint no modifica regiones, observaciones,
modelos o ingestas y no solicita la geolocalización del dispositivo.
