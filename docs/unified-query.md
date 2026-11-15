# Contrato unificado de consulta NASA

Todos los repositorios reciben el mismo objeto `DataQuery` y devuelven el mismo
envoltorio `SourceResult`. `NASADataService` distribuye la consulta a las siete
fuentes y reúne los resultados. ECOSTRESS incluye ET y LST, por lo que la respuesta
conjunta tiene ocho entradas de producto.

## Entrada

```json
{
  "latitude": 6.0,
  "longitude": -75.0,
  "start": "2026-01-01",
  "end": "2026-01-31",
  "limit": 5,
  "page_size": 100,
  "power_parameters": ["T2M", "T2M_MIN", "T2M_MAX", "RH2M", "ALLSKY_SFC_SW_DWN", "WS2M"]
}
```

| Campo | Regla |
| --- | --- |
| `latitude`, `longitude` | Ambos juntos, WGS84; rangos [-90, 90] y [-180, 180] |
| `bbox` | Alternativa exclusiva al punto: [oeste, sur, este, norte] |
| `start`, `end` | Ambas fechas ISO, inclusivas en UTC; inicial <= final |
| `limit` | Máximo de granules por producto, 1–10000; por defecto 20 |
| `page_size` | Paginación CMR, 1–2000; por defecto 100 |
| `power_parameters` | Variables POWER, por defecto las seis atmosféricas; puntual hasta 20 |

La CLI usa un límite conservador de 5 granules por producto. Los parámetros
desconocidos se rechazan para evitar ignorar filtros por accidente. Los filtros
propios de un proveedor solo afectan a ese proveedor: `power_parameters` no
selecciona bandas de Landsat ni variables SMAP.

Sin fechas solo se permite consultar SRTM individualmente, porque es estático.
Una consulta a todas las fuentes siempre requiere un periodo. No se usa un periodo
implícito ni se sustituye un intervalo sin datos por otras fechas.

## Consumo en Python

```python
from packages.contracts import DataQuery
from apps.api.app.services.nasa_data import NASADataService
from apps.api.app.repositories import GPMRepository

query = DataQuery.from_dict({
    "latitude": 6.0, "longitude": -75.0,
    "start": "2026-01-01", "end": "2026-01-31", "limit": 5,
})

all_data = NASADataService().fetch(query)
gpm_data = GPMRepository().fetch(query)
subset = NASADataService().fetch(query, sources=("power", "gpm", "smap"))
```

Para un área, reemplazar latitud/longitud por:

```json
{"bbox": [-75.5830, 5.4110, -74.6167, 6.5866], "start": "2026-01-01", "end": "2026-01-31"}
```

## Salida

La consulta conjunta devuelve `schema_version`, `query_id`, `requested`,
`completed_at`, `status`, `sources` y `notes`. En `sources` aparecen `power`, `gpm`,
`smap`, `srtm`, `grace`, `ecostress`, `ecostress-lst` y `landsat`.

Cada entrada tiene:

| Campo | Contenido |
| --- | --- |
| `query_id` | Huella SHA-256 determinista de la consulta; compartida por todas las fuentes |
| `source` | Fuente/producto consultado |
| `requested` | Ubicación, periodo y parámetros comunes originales |
| `status` | `ok`, `empty` o `error` |
| `data_kind` | `provider_response` para POWER; `granule_catalog` para los demás |
| `metadata` | Producto, versión, resolución nativa, selección espacial, consulta efectiva y fecha de acceso |
| `data` | Payload original con trazabilidad; `null` si la consulta falló |
| `error` | Mensaje de error operativo; `null` en consultas exitosas o vacías |

El estado global es `ok` si todas las consultas terminaron sin error, `partial`
si solo algunas fallaron y `error` si fallaron todas. Un estado global `ok` puede
incluir productos `empty`: no implica que todas las fuentes tengan cobertura.
`ok` tampoco certifica calidad científica ni que los valores no sean nodata.

`query_id` identifica el contexto solicitado, no una ejecución ni una versión
inmutable de los datos. Dos ejecuciones iguales comparten el identificador aunque
el proveedor publique nuevas observaciones. Conservar también las versiones,
metadatos originales y fechas de acceso para reproducibilidad.

## Correspondencia espacial y temporal

- **Punto:** POWER usa latitud/longitud en el endpoint puntual. CMR usa
  `point=longitud,latitud`, sin crear un bbox ni un radio implícito.
- **Área:** CMR busca intersecciones con el bbox. POWER puede ampliar su ventana
  regional al mínimo admitido; ambos límites quedan explícitos en el payload.
- **Cobertura real:** los granules conservan `raw_metadata` con extensiones
  (`boxes`, `polygons`, etc.) y fechas reales; POWER conserva geometría y cabeceras.
- **Tiempo:** CMR selecciona archivos por solapamiento, no necesariamente por la
  fecha exacta de inicio. SRTM ignora el periodo; GRACE incluye múltiples fechas
  en un mismo archivo. Esto no equivale a alinear observaciones por día.

La precisión física sigue limitada por cada producto. Solicitar el mismo punto
no convierte un mascon GRACE en humedad de parcela ni garantiza que un píxel
Landsat y una celda SMAP midan la misma superficie. Las respuestas marcan
`spatial_alignment_applied=false` y `temporal_alignment_applied=false`.
La extracción raster, el control de calidad y la alineación para ML corresponden
a una etapa posterior; el contrato actual conserva lo necesario para implementarlos.

## CLI

```bash
python3 -m scripts.ingest collect \
  --latitude 6.0 --longitude -75.0 \
  --start 2026-01-01 --end 2026-01-31 --limit 5 \
  --output data/manifests/sector.json
```

`collect` exige ubicación explícita, admite también `--bbox` y devuelve código 1
ante resultados `partial` o `error`, conservando el resultado completo en la salida.
Las consultas vacías no generan error de proceso. No hay descargas automáticas.
Los comandos previos `power`, `search` y `download` conservan su formato de salida.

## Referencias de los adaptadores

El mapeo de coordenadas sigue las APIs oficiales:
[POWER diario](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) y
[CMR: filtros espaciales de granules](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html).
