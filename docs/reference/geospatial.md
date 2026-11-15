# Área de interés y soporte geoespacial

Las coordenadas de consulta usan WGS84. Un punto es latitud/longitud; un bbox se
ordena como oeste, sur, este, norte. La geometría seleccionada identifica el área
de interés; el soporte nativo identifica qué parte del producto respalda un valor.

## Geometría en el frontend

Angular usa MapLibre para exploración y delimitación. La finca conserva el polígono
GeoJSON y su bbox, con un centro coherente. El selector admite cuadrados por
superficie: m², km² y hectáreas. `1000 m² = 0.1 ha = 0.001 km²` corresponde a un
lado de aproximadamente 31.62 m. Cambiar unidades debe conservar superficie.
Las utilidades geodésicas y la validez de polígonos se comprueban en pruebas.

El mapa no convierte una selección en una ingesta privada o una predicción de
parcela. La asociación con fuentes/modelos debe conservar geometría, ámbito,
resolución, fechas y calidad. Los nombres geográficos son etiquetas de orientación.

## Productos del catálogo de ingesta

Los identificadores, versiones y resoluciones declaradas están en
`pipelines/ingestion/sources/nasa/catalog.py`. La versión del producto forma parte
de su procedencia y debe contrastarse antes de procesar un nuevo origen.

| Producto | Soporte nominal declarado | Interpretación |
| --- | --- | --- |
| POWER | Meteorología 0.5° × 0.625°; radiación según producto | Estimación de grilla, no estación de finca |
| GPM IMERG | 0.1° | Precipitación con latencia según producto |
| SMAP L4 del catálogo | 9 km | Humedad modelada/asimilada; no confundir con la receta de los experimentos |
| SRTMGL1 | 1 segundo de arco, aproximadamente 30 m | Elevación estática; pendiente exige vecindad y distancias métricas |
| HLS Landsat | 30 m | Reflectancia; NDVI requiere bandas y máscaras compatibles |
| ECOSTRESS | 70 m | Hora, capa, unidades y calidad específicas de la adquisición |
| GRACE mascons | Soporte regional de mascons; malla de salida más fina | Anomalía regional de almacenamiento; no humedad de parcela |

Los experimentos ML pueden emplear otras colecciones que los clientes de catálogo.
La receta concreta y los productos utilizados están en
[datasets de modelos](ml/datasets.md); una coincidencia de misión no los hace intercambiables.

## Consultar un área pequeña

`scripts.probe_area` construye un AOI con GeographicLib, consulta POWER en el
centro y descubre productos CMR con el bbox exacto. Conserva por separado
observaciones científicas y filas de catálogo. Las sondas de acceso son acotadas;
HEAD satisfactorio no demuestra que el contenido científico sea accesible por GET.

```bash
python -m scripts.probe_area \
  --latitude 6.2442 --longitude -75.5812 --side-m 10 \
  --start 2026-01-01 --end 2026-01-31 --limit 3 \
  --directory data/probes/consulta-area
```

Usar un directorio vacío. El punto y las fechas son parámetros del ejemplo, no
una finca ni una promesa de disponibilidad. El directorio contiene request,
geometría, resumen, respuestas originales y tablas normalizadas. La
[muestra de datos](../../samples/aoi-10m/README.md) ilustra sus contratos.

## Invariantes del procesamiento

- Descubrimiento CMR no equivale a lectura, recorte ni píxeles válidos.
- El tamaño del AOI no aumenta la resolución ni el número de observaciones independientes.
- Conservar celda/soporte nativo, CRS, periodo, unidad, escala, nodata y controles de calidad.
- Interpretar tasas, acumulados, medias y anomalías antes de agregarlos.
- La unión entre fuentes requiere reglas espaciales y temporales de la receta.
- No interpolar targets ni reemplazar ausencias por ceros para completar un área.

El acceso público permite POWER y catálogos; muchos contenidos científicos
requieren Earthdata. Las credenciales se configuran fuera del repositorio.
