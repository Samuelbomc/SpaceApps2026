# NASA POWER de extremo a extremo

El flujo de adquisición es **GET histórico → procesamiento → Parquet**. Se ejecuta
localmente y usa el mismo `DataQuery` de las consultas por fuente, con un punto
WGS84 y fechas explícitas. No entrena XGBoost ni genera pronósticos.

## Responsabilidades y archivos

| Componente | Archivo | Responsabilidad |
| --- | --- | --- |
| Cliente | `pipelines/ingestion/sources/nasa/power.py` | GET y respuesta original, timeout y reintentos HTTP compartidos |
| Procesador | `pipelines/processing/cleaning/power_point.py` | Registros por día/variable, unidades originales y controles de calidad |
| Repositorio de almacenamiento | `pipelines/ingestion/storage/power.py` | Lectura y upsert Parquet sin duplicados |
| Flujo | `pipelines/ingestion/flows/power.py` | Plan incremental, archivo original y persistencia por bloques |
| Contrato | `packages/contracts/observations.py` | `PowerObservation` e identidad de ubicación |

## Ejecutar

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

El ejemplo es el punto de referencia de Medellín indicado en el contexto;
no representa una región piloto agronómicamente validada. Las fechas son
inclusivas en UTC. No se permiten fechas futuras. La persistencia incremental es puntual. Las consultas por bbox tienen su
procesamiento regional separado.

El comando `power` conserva su salida sin procesar y `collect` conserva
la consulta unificada de todas las fuentes. `power-sync` es el comando explícito
para procesar y almacenar solo POWER; no descarga otros productos satelitales.

## Observaciones persistidas

El formato largo contiene una fila por variable, fecha y ubicación solicitada.
Se conservan `source`, `product`, `date`, `variable`, `value`, `raw_value`, `unit`,
`quality`, coordenadas solicitadas y reportadas, `time_standard`, resolución,
`api_version`, `product_version`, `cell_id`, `data_sources`, fecha de acceso,
`response_sha256` y `raw_path`.

- `product="POWER_DAILY"` es el nombre interno del producto de la API, no un
  identificador de colección CMR.
- La versión que POWER reporta en `header.api.version` es la de la API. No se
  presenta como versión científica del producto. `product_version` queda `null`
  si no está reportada.
- `location_id` identifica las coordenadas de consulta. `cell_id` queda `null`
  porque la respuesta usada no identifica inequívocamente la celda nativa.
- Las unidades se conservan tal como las reporta NASA. No se transforma radiación
  de MJ/m²/día a otras unidades ni se mezcla viento a 2 m con viento a 10 m.
- El sentinel `-999`, valores nulos y fechas/variables ausentes producen `value=null`
  con `quality="missing"`. Los valores no numéricos o no finitos son inválidos.
- Humedad relativa fuera de [0,100] cuando la unidad es `%`, y viento/radiación
  negativos, quedan señalados como `out_of_range`; se conserva el valor original.
- `provider_value_unvalidated` significa que el valor pasó controles básicos,
  no validación agronómica ni comparación con estaciones.
- Falta de unidades, estructura inválida, fechas inválidas o tiempo distinto
  de UTC detienen el procesamiento. No se imputan ceros ni se entrena con nodata.

## Archivos y trazabilidad

```text
data/
  raw/nasa_power/<location_id>/<inicio>_<fin>_<hash>.json
  observations/nasa_power/<location_id>/2020.parquet
  observations/nasa_power/<location_id>/2021.parquet
  ...
  manifests/power-sync.json
```

La escritura conserva primero la respuesta original completa. Cada fila apunta
a ese archivo y al SHA-256 de su respuesta. Parquet usa esquema explícito
`power_observation_v1`, fecha nativa `date32`, valores `float64` y compresión
Snappy. Las nuevas salidas operativas de `data/` están excluidas de Git; los datasets
científicos previamente versionados conservan su trazabilidad.

Estos JSON son respuestas compactas de la API, no imágenes satelitales. Se
mantienen por trazabilidad; no se eliminan originales existentes ni se aplica
retención automática. El histórico procesado permanece en Parquet
y no se duplicará completo en PostgreSQL. La política para resultados operativos,
modelos JSON y futuros temporales está en [persistencia](../architecture/persistence.md).

La identidad para upsert es fuente, producto, ubicación, fecha, variable y estándar
temporal. Se mantiene la última observación recibida para esa identidad; las
respuestas anteriores permanecen en el archivo de originales. El ciclo de entrenamiento utiliza snapshots identificados; no se debe entrenar
contra un Parquet mutable sin versión. Ver [entrenamiento](model-training.md).

## Actualización incremental

Antes de consumir NASA se inspeccionan las filas realmente persistidas:

1. Se detectan huecos por fecha **y por variable**, incluyendo variables nuevas.
2. Se agrupan fechas consecutivas que requieren consulta, en bloques de hasta
   366 días. Se consulta secuencialmente, sin ráfagas paralelas por punto.
3. Se archiva, procesa y almacena cada bloque antes de continuar.
4. Al reanudar, los bloques ya completos no se vuelven a consultar.

Un día solo está cubierto si tiene valores no nulos y sin marcas de error para
todas las variables pedidas. Nodata y valores fuera de rango permanecen guardados
pero se vuelven a consultar. El resultado informa `remaining_gap_days`, que cuenta
fechas con alguna variable pendiente, no cantidad de celdas/observaciones faltantes.

Por defecto se reconsulta la parte solicitada que cae en los **últimos 90 días
respecto a hoy UTC**, para recoger revisiones del proveedor. No son los últimos
90 días del rango histórico. `--refresh-days 0` desactiva este repaso; `--force`
reconsulta todo el rango. Los GET seleccionados por este flujo omiten la caché
HTTP por defecto para no reutilizar una revisión anterior.

```bash
# Al ampliar el rango, solo se solicita lo nuevo o lo pendiente.
python -m scripts.ingest power-sync \
  --latitude 6.2442 --longitude -75.5812 \
  --start 2020-01-01 --end 2026-01-01 \
  --parameters T2M RH2M WS10M ALLSKY_SFC_SW_DWN
```

`status="incomplete"` y código de proceso 1 indican que aún hay huecos. Las
observaciones completas quedan persistidas. Una excepción a mitad del flujo
también conserva los bloques ya escritos para poder reanudar.

Cada partición anual se reemplaza atómicamente y un bloqueo local impide
escritores simultáneos. No hay transacción distribuida para todo el histórico ni
versionado automático de datasets. Si el proceso termina abruptamente puede
quedar `.write.lock`; debe retirarse solo después de comprobar que ya no hay
escritor activo. Esta implementación es para ingestas locales de tamaño MVP.

## Consultar lo almacenado

```python
from packages.contracts import DateRange, GeoPoint
from pipelines.ingestion.storage.power import PowerParquetRepository

rows = PowerParquetRepository().read(
    GeoPoint(6.2442, -75.5812),
    DateRange.parse("2020-01-01", "2025-12-31"),
    variables=("T2M", "RH2M"),
)
```

La construcción de variables y etiquetas corresponde a la receta de ML y no a
este flujo POWER. El procesamiento multisensor y sus requisitos de acceso se
definen en [datasets](ml/datasets.md) y [capacidades](capabilities.md).

## Referencias oficiales

- [API diaria POWER](https://power.larc.nasa.gov/docs/services/api/temporal/daily/).
- [Resoluciones y revisiones de datos POWER](https://power.larc.nasa.gov/docs/tutorials/service-data-request/api/).
- [Apache Arrow: lectura y escritura Parquet](https://arrow.apache.org/docs/25.0/python/parquet.html).
