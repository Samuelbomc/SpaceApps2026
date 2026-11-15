# Análisis por ubicación

El explorador envía la geometría delimitada a una cola pública. No requiere
cuenta y no sustituye la selección por Medellín u otra región de referencia.
El mapa utiliza MapLibre; la información científica procede de los proveedores.

## Contrato y recorrido

1. El visitante selecciona un municipio y elige 7, 15, 30 o 60 días.
   Puede pulsar **Analizar municipio** sin dibujar. Se utiliza un punto de referencia
   comprobado dentro de su geometría oficial, respetando huecos y multipolígonos.
   Opcionalmente delimita un lote y pulsa **Analizar esta área**; al borrar el lote
   vuelve al análisis municipal. Un dibujo incompleto o inválido no se sustituye
   silenciosamente por el municipio.
2. `POST /api/v1/geographic-analyses` valida geometría, ámbito y origen HTTP;
   registra área y solicitud en PostgreSQL y responde `202`. El día de consulta
   se fija en el servidor con zona `America/Bogota`.
3. El consumidor `python -m scripts.geographic_worker` prepara la tarea fuera
   de HTTP. Adquiere un lock, recupera interrupciones y respeta los reintentos.
4. Busca un snapshot compatible en `FEATURE_DIRECTORY` o tablas `features.csv` e
   `inference.csv` en `TRAINING_DATA_DIRECTORY/{moisture,temperature_mean}/`.
   Prioriza las entradas de la ubicación exacta, incluyendo clima sin suelo.
   Una referencia completa no desplaza una predicción climática local. Si no
   existen entradas exactas, busca la
   referencia completa más cercana dentro del ámbito del modelo y del máximo
   `NEAREST_INPUT_MAX_DISTANCE_KM` (200 km por defecto). Si ninguna referencia
   permite ambos modelos, conserva las entradas parciales disponibles.
   Todas las candidatas deben tener la misma emisión requerida y receta;
   no se unen clima y suelo de coordenadas diferentes.
5. Si falta una entrada exacta completa, `ModelPointPreparation` consulta POWER LST
   y los catálogos específicos GPM IMERG Late V07 y SMAP L3 Enhanced V006 para
   las coordenadas elegidas. Extrae sus celdas nativas, aplica la receta compartida
   de entrenamiento y publica el snapshot solo cuando sus variables son finitas.
   Este paso se ejecuta antes de usar una referencia cercana o la muestra pública.
6. El pipeline calcula las predicciones cuando dispone de las variables válidas,
   evalúa rotación y guarda resultados en el backend seleccionado. MongoDB es
   el predeterminado de Compose; PostgreSQL es una alternativa explícita.
7. `GET /api/v1/geographic-analyses/{request_id}` devuelve progreso y resultado.
   Cambiar de lote o periodo cancela la lectura anterior y limpia su presentación.

`AnalysisResult.spatial_match` conserva coordenadas solicitadas y utilizadas,
método `exact` o `nearest`, distancia aproximada en kilómetros (gran círculo),
identificador del punto, hash y emisión del snapshot. La geometría seleccionada
no se modifica y las coordenadas de las observaciones tampoco se reasignan.
La vista prioriza las predicciones del punto seleccionado. Si no existen,
muestra automáticamente la estimación regional compatible disponible, conservando
la distancia, la ubicación de origen y las fechas originales. Una entrada local
parcial se muestra sin exigir humedad del suelo; una referencia completa puede
consultarse desde el control regional. Cambiar municipio, geometría o periodo
limpia el resultado anterior. Proximidad no acredita precisión del lote.

La búsqueda omite referencias corruptas, incompatibles o fuera del ámbito.
Un límite cero desactiva referencias a distancia. No busca en archivos de fincas
privadas ni utiliza una emisión anterior o posterior para sustituir la requerida.

## Referencia regional adicional

Si no hay entradas completas para el periodo solicitado, el worker busca una
referencia adicional con su emisión original. Prioriza los snapshots preparados
públicos recientes y, en su ausencia, el snapshot público incluido en
`ml/examples`. Solo admite emisiones hasta el día de consulta y con antigüedad
máxima de siete días. Se mantienen el ámbito y el límite de distancia configurado.

La preparación puntual evalúa los siete cortes diarios más recientes dentro del
histórico descargado: emisión solicitada y seis anteriores. Cada corte exige
las 49 variables climáticas y 71 de suelo finitas con la receta causal completa,
no solo un valor reciente ni un archivo presente en el catálogo. Conserva clima
actual parcial cuando está listo y guarda el primer corte completo anterior con
su emisión, coordenadas, límites temporales y manifiesto originales. No descarga
de nuevo cada sensor por cada corte; utiliza las series adquiridas y respeta
las esperas independientes de las fuentes.

La referencia prioriza un corte completo de la misma ubicación frente a uno
más reciente de otra zona. Se recalcula después de preparar las fuentes para
utilizarlo en la misma ejecución. La pantalla lo identifica como «Último corte
completo de esta ubicación», con su periodo original. No se transforma un
pronóstico antiguo en uno emitido hoy ni se extiende más allá de los leads
entrenados. Si ningún corte cumple la receta, permanece pendiente; la antigüedad
no resuelve la falta de acceso Earthdata o de capas estáticas.

La muestra de suelo contiene las variables climáticas del mismo punto; no se
mezclan las coordenadas de sus CSV de clima y suelo. Los ejemplos no se importan
al almacén operativo ni se usan como etiquetas de entrenamiento.

`GeographicAnalysis.reference` devuelve tipo de referencia y `AnalysisResult`
con predicciones, evaluación de cultivos y correspondencia espacial. Su periodo
comienza el día posterior a su emisión, conservando las fechas reales. El periodo
original, `result` y `forecast_start_date` de la solicitud no se reemplazan.

La referencia se guarda en un espacio de resultados `geo-reference-<area_id>`;
la migración 009 conserva sus punteros separados. Así la consulta ordinaria de
resultados del área no puede devolver esa referencia como si fuera el análisis
del periodo solicitado. La interfaz identifica la referencia, su distancia y
periodo y muestra predicciones, cultivos y rotaciones en una vista compacta. La tabla diaria
expone cada salida del horizonte; los ausentes no se sustituyen por cero.
No consulta observaciones del punto seleccionado para acompañar
un pronóstico calculado en otro punto.

La vista principal prioriza las predicciones calculadas y los cultivos compatibles
del catálogo. Coordenadas de muestreo, receta, identificadores y diagnósticos de
fuentes están en un detalle técnico cerrado. Sin predicciones no muestra tarjetas
vacías ni reemplaza los pronósticos por observaciones históricas. La compatibilidad
térmica se distingue de una recomendación aprobada y mantiene sus requisitos
pendientes; ver [motor de cultivos](crop-rotation.md).

El cuerpo del POST contiene `geometry` GeoJSON Point o Polygon y `horizon_days`.
El frontend envía Point para el punto municipal y Polygon para un lote delimitado.
La consulta municipal representa ese punto, no un promedio de todo el municipio.
Orden de coordenadas: **[longitud, latitud]** WGS84.
La respuesta conserva geometría original normalizada, `area_id`, `request_id`,
punto y método de muestreo, fecha objetivo, periodo, intentos y próximo reintento.
Los DTOs y tipos generados están en `packages/contracts/`.

## Observaciones disponibles sin bloquear por otros sensores

`GeographicAnalysis.observations` contiene el último valor válido de cada variable
POWER del punto solicitado, con coordenadas, fecha, unidades, resolución, estándar
temporal y fecha de recuperación. Se guardan antes de exigir elevación, GPM, SMAP
o SoilGrids. La pantalla muestra estas observaciones del punto junto a la
estimación regional identificada; ambas mantienen su propia procedencia.

Las observaciones LST conservan originales inmutables, Parquet en
`observations/nasa_power_lst/` y una copia operativa en PostgreSQL. La migración
010 admite UTC y LST con claves separadas. Un fallo temporal de Parquet no impide
consultar las observaciones si su original verificable está conservado; su archivo
Parquet queda pendiente para reconstruirse. Las observaciones no constituyen por
sí solas un vector completo de XGBoost ni etiquetas de entrenamiento verificadas.

La lectura selecciona el último valor válido por variable, descarta faltantes y
no incorpora fechas posteriores al día solicitado. No copia observaciones de
otra selección para presentarlas como locales. Las referencias se publican antes
de las peticiones externas y las observaciones se conservan aunque el resto del
análisis quede pendiente. Si solo existe una referencia climática compatible, se
muestran sus cuatro salidas y se conserva el estado pendiente de suelo.

Los resultados asociados se leen por su identificador inmutable, comprobando
además región y periodo. Otra versión del mismo periodo no reemplaza el resultado
apuntado por la solicitud. Cuando todas las fuentes están inaccesibles y no hay
caché ni referencia válida, se conserva el faltante; nunca se inventan valores
para aparentar disponibilidad.

## Identidad, soporte espacial y alcance

Un área se identifica por el hash de su geometría normalizada. El inicio y el
sentido del anillo no alteran su identidad. Cambiar ubicación, periodo o día de
consulta produce otra solicitud; repeticiones concurrentes comparten la existente.
El polígono permite hasta 500 vértices, sin agujeros ni cruces. Se exige que toda
la selección esté dentro del ámbito de los modelos, definido por
`ANTIOQUIA_ORIENTE` en `packages/contracts/models.py`.

Para Polygon se obtiene un punto interior mediante intersecciones horizontales,
incluso si el centro del bbox queda fuera de un contorno cóncavo. El método es
`interior_reference_point`. Las fuentes se muestrean en sus celdas nativas en
ese punto. **No se calcula un promedio de todos los píxeles del polígono ni se
acredita precisión de parcela.** La geometría queda disponible para implementar
extracción por intersección y estadísticas zonales verificadas.

Las áreas usan regiones internas `geo-<area_id>` y no se enumeran en el catálogo
público de regiones de referencia. Ninguna cuenta, finca privada o CSV del usuario
se incorpora a esta ruta pública. El identificador UUID permite consultar la
solicitud; no debe usarse esta ruta para compartir mediciones privadas.

## Estados y recuperación

| Estado | Significado |
| --- | --- |
| queued | Solicitud persistida pendiente del consumidor |
| running | Preparación en curso |
| waiting_inputs | Faltan variables completas; próximo intento según el estado de cada fuente |
| retry_scheduled | Fallo transitorio; backoff durable desde un minuto hasta una hora |
| completed | Clima y suelo calculados; revisar validación y aprobación agronómica por separado |
| failed | Solicitud de un día anterior vencida sin completar; requiere consulta actual |

Las esperas se conservan por proveedor en `source-recovery.json`, dentro del
punto y emisión. Un fallo aumenta la espera aproximadamente a 1, 2, 4, 8 minutos,
hasta una hora, con variación aleatoria y respetando `Retry-After` cuando exige
más tiempo. La cola se programa para la primera fuente pendiente disponible;
las demás conservan su propia espera y no se consultan antes de tiempo.
La espera se cuenta desde el final del intento, incluso si la descarga tarda.
No se mantienen sleeps largos dentro del proceso.

El final consultado retrocede hasta cinco días antes de la consulta cuando el
proveedor no devuelve datos o rechaza las fechas con HTTP 400/422. En la receta
puntual, el intento normal termina tres días antes de la consulta; los respaldos
terminan cuatro y cinco días antes. `SOURCE_FALLBACK_MAX_LAG_DAYS=5` controla
este límite. Se mantiene el inicio del histórico y se registran `query_end` y
`attempted_end_dates`. Si el intervalo amplio ya contiene valores, se aprovechan
esos datos sin repetir consultas por cada día.

Los HTTP 401/403, 429, caídas y `Retry-After` se delegan a la recuperación de la
fuente; cambiar fechas no permite eludir sus restricciones. Una respuesta vacía
no sustituye la última caché POWER válida. Los trabajos Harmony se aíslan también
por el final consultado para no reutilizar un subconjunto de otro intervalo.

El retroceso no cambia la emisión de XGBoost ni sus cortes. Los rellenos causales
acotados y contadores de edad de la receta determinan si los datos anteriores
son suficientes. La radiación conserva su corte de emisión menos siete días.
Si se completa la entrada, el pronóstico comienza en el día de consulta; de lo
contrario se conservan observaciones y la referencia regional identificada.

Cada fuente guarda su avance antes de consultar la siguiente. Reiniciar el
worker conserva intentos, próxima ejecución, archivos verificados y trabajo
Harmony. Un éxito reinicia el contador de fallos. Los datos descargados se
revisan nuevamente después de quince minutos; el caché HTTP puntual utiliza el
mismo intervalo para permitir recuperar observaciones publicadas tardíamente.

Ante una caída de POWER, la preparación puede utilizar su última respuesta
válida de **ese mismo punto, periodo y receta**, verificada por SHA-256. Esto no
reasigna datos de otras coordenadas ni convierte observaciones antiguas en
recientes. Una caché corrupta se rechaza. Los fallos no borran archivos completos
ni snapshots válidos. GPM y SMAP aprovechan los archivos verificados y la
reanudación Harmony. Configurar acceso Earthdata libera su espera de configuración
en el siguiente intento; las credenciales no se guardan en estos registros.

Las descargas conservan los archivos completos cuando falla un archivo posterior.
Antes de reutilizarlos se verifican tamaño, producto y SHA-256. Los subconjuntos
Harmony tienen una identidad estable por trabajo, elemento STAC y activo; renovar
la firma del URL no obliga a descargar otra vez el archivo verificado. Un cambio
de trabajo o producto exige una identidad distinta. Los metadatos de caché dañados
se reconstruyen descargando y verificando de nuevo; no se acepta un archivo
corrupto como observación.

El descargador aplica un presupuesto de cinco minutos por llamada, comprobado
entre operaciones, además de los timeouts HTTP de conexión y lectura. Una lectura
bloqueada termina según su timeout; el presupuesto no interrumpe una llamada de
red en curso. Al agotarse el tiempo, elimina el archivo parcial y conserva los
archivos completos para el siguiente intento. No implementa reanudación por
bytes de un archivo incompleto.

Harmony conserva su identificador ante errores transitorios o límites de tasa.
Si el trabajo o catálogo desaparece (404/410), o `dataExpiration` indica resultados
vencidos, invalida el puntero remoto y solicita otro trabajo en un intento
posterior, conservando los archivos locales. Si el trabajo está pausado, solicita
su reanudación. Los sidecars identifican que esos archivos proceden de un
subconjunto remoto. El protocolo se basa en la
[documentación de Harmony](https://harmony.earthdata.nasa.gov/docs).

Si todas las fuentes responden pero faltan mediciones o capas estáticas, el
análisis continúa pendiente y vuelve a comprobarlas en una hora. Credenciales,
capas ausentes y falta de cobertura requieren resolver su causa; reintentar no
crea esos datos. Los diagnósticos se conservan sin llenar la vista simple de
información técnica.

Una interrupción deja una tarea recuperable por el siguiente consumidor dueño
del lock. No se reutilizan entradas de otra fecha para fabricar actualidad.
Solicitudes repetidas no adelantan el reintento ni disparan otra ingesta.
HTTP limita tamaño de cuerpo, origen, solicitudes por dirección y presión global
de la cola. No interpreta URLs de archivos ni comandos suministrados por usuarios.

## Preparación puntual y dependencias científicas

`pipelines/ingestion/flows/model_point.py` conecta adquisición, extracción y
almacenamiento. `ml/features/recipe.py` contiene las mismas funciones causales
utilizadas por los scripts de entrenamiento: 49 variables climáticas y 71 de
suelo, meteorología hasta emisión menos dos días y radiación hasta emisión menos
siete días. Las coordenadas seleccionan observaciones; no se añaden columnas a
los pesos XGBoost existentes. Construir esta entrada no reentrena los modelos.

`MODEL_SOURCE_DIRECTORY` contiene `GPM/`, `SMAP/`, `SRTM/` y `SOILGRIDS/`.
Las capas estáticas conservan los nombres y escalas de
[adquisición de datos](../guides/data-acquisition.md). Se muestrea la celda que
contiene el punto; NoData o falta de cobertura no se reemplazan por ceros ni por
valores arbitrarios cercanos. Las capas estáticas deben aprovisionarse con esos
scripts; el worker no descarga ni deriva automáticamente el DEM y la pendiente.

La adquisición requiere el extra `processing` para HDF5/NetCDF y GeoTIFF y
`download` para Earthdata. Sin credenciales consulta los catálogos públicos y
conserva el bloqueo de descarga; no cambia los productos por otros públicos
incompatibles. GPM se descarga con un presupuesto por intento
`MODEL_DOWNLOAD_MAX_MB` y caché verificada. SMAP utiliza un subconjunto espacial
Harmony, sin reproyección ni cambio de escala, para evitar archivos globales de
cientos de MB por día. Su trabajo remoto se guarda y continúa en intentos
posteriores. Los subconjuntos se aíslan por selección y emisión; no se mezclan
con archivos de otro punto. Por día SMAP se selecciona la revisión más reciente
del nombre de archivo, como en la preparación de entrenamiento.

En `point-inputs/<hash-región>/<emisión>/` se guardan POWER, inventarios, estado
por fuente y manifiestos con hashes. Estos registros locales conservan unidades,
resolución, fechas y celdas GPM/SMAP. El snapshot referencia un manifiesto
inmutable por SHA-256. Los faltantes no generan vectores incompletos; clima puede
publicarse sin suelo si sus propias entradas están completas. El reintento
respeta `Retry-After`; mostrar una referencia cercana no cancela los intentos
para obtener una entrada exacta.

DATA-01 permanece abierto hasta verificar extracción reciente completa en el
entorno desplegado y la actualización de históricos y etiquetas para
reentrenamiento. Las pruebas con archivos sintéticos y modelos reales verifican
la integración, no la precisión agronómica del punto ni el acceso efectivo a
productos protegidos. La autenticación y el servicio Harmony requieren una
prueba con credenciales y datos reales; su contrato está en la
[documentación oficial](https://harmony.earthdata.nasa.gov/docs).
