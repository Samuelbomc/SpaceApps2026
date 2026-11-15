# Contrato de entradas e inferencia XGBoost

El worker usa snapshots procesados de la receta `expanded-v1` y modelos propios
para 7, 15, 30 y 60 días. FastAPI consulta resultados guardados y metadatos;
no descarga fuentes, entrena ni calcula predicciones durante esa consulta.

## Modelos y versiones

Los veinte artefactos están en `ml/artifacts/forecasts/{H}d/{modelo}/`.
Los nombres son `temperature_mean`, `temperature_min`, `temperature_max`,
`precipitation` y `moisture`. `models.json` indexa la colección científica y
`ml/configs/pretrained-bundle.json` fija SHA-256 de metadatos, Booster reajustado
y Booster de evaluación. Una alteración se rechaza antes de inferir.

`ForecastPredictor` implementa la carga compartida entre reproducción científica
y `ExpandedModelBundle`. `model.json` es un reajuste con todos los datos;
`evaluation_model.json` fue ajustado sin las filas del test. Las métricas del
catálogo pertenecen al segundo. Ninguno se convierte en campeón operativo por
estar disponible en el repositorio; el catálogo los identifica como experimentales.
La selección usa cuatro ventanas expansivas purgadas. Ver
[resultados por horizonte](ml/horizon-results.md) y [protocolo](ml/rolling-origin-results.md).

## Salidas y periodo

| Modelo | Salida |
| --- | --- |
| temperature_mean | Temperatura media del periodo, °C |
| temperature_min | Media de mínimas diarias, °C |
| temperature_max | Media de máximas diarias, °C |
| precipitation | Precipitación acumulada del periodo, mm |
| moisture | Humedad superficial media de observaciones válidas, m³/m³ |

Los objetivos cubren **t+1..t+H**, con observaciones hasta **t-2**. Para mostrar
predicciones desde el día de consulta D se exige `issue_date=D-1` y
`observation_cutoff=D-3`. No son condiciones de un día aislado ni trayectorias diarias.
Cada horizonte usa sus propios Boosters; no se extrapola recursivamente un modelo.

La humedad reconstruye `smap_mean_7d + XGBoost(features)` exactamente una vez.
Las salidas climáticas son absolutas. La escala H/7 de la lluvia corresponde a
su baseline de persistencia, no a una multiplicación de la predicción del Booster.

## Contrato de recepción

`GET /api/v1/models/input-contract` devuelve la receta, las columnas ordenadas,
fuentes y reglas de recepción. El mismo objeto está en `input_contract` del
catálogo `GET /api/v1/models`. Ambos endpoints leen JSON y verifican hashes;
no ejecutan los modelos. Los tipos HTTP se generan en `packages/contracts/`.

| Entrada | Regla |
| --- | --- |
| region_id | Parámetro del receptor; vincula el snapshot a una región registrada |
| point_id | Selección exacta de la celda del archivo; se conserva en el snapshot |
| latitude / longitude | Coordenadas finitas WGS84; deben coincidir con las de la región al consumir |
| issue_date | Fecha exacta de la receta, anterior al día actual en America/Bogota |
| observation_cutoff | Exactamente issue_date − 2 días |
| climate | Las 31 variables completas de los modelos climáticos |
| soil | Las 52 variables completas, incluidas las 31 climáticas, u omisión total del grupo |
| source_sha256 | Calculado por el receptor sobre el archivo original |

Clima necesita POWER —incluidos QV2M y viento a 2 m—, GPM IMERG Late, elevación
y calendario. Suelo añade SMAP, pendiente y SoilGrids. Las ventanas son 7/14/30
días; lluvia añade ventanas 1/3 y máximos y conteos. Se respeta la preparación de
`ml/scripts/prepare_expanded_datasets.py`, sus unidades, rejillas nativas y calidad.
Los datos recientes deben producir esas mismas variables; un GET o catálogo CMR
no equivale a un snapshot procesado de toda la receta.

Todas las variables deben ser finitas. No se sustituyen ausencias por cero,
valores interpolados, vecinos ni fechas cercanas. Suelo parcial se rechaza;
clima completo sin ninguna variable adicional de suelo permite inferencia solo
climática. Clima y suelo deben compartir exactamente sus variables comunes.
El orden de columnas del CSV puede variar; el orden que recibe XGBoost es el
publicado en los metadatos, verificado contra el propio Booster.

## Importar y conservar un snapshot

El productor entrega CSV UTF-8 con las columnas de metadatos y variables del
contrato. **No necesita target, target_start ni target_end futuros.** Si se
incluyen fechas de etiquetas históricas, se verifica que correspondan al horizonte.
`features_available_on`, cuando está presente, no puede ser posterior a issue_date.
Se rechazan encabezados duplicados, filas mal formadas y celdas/fechas duplicadas.
El hash se comprueba antes y después de leer para detectar cambios durante la recepción.

Ejemplo con una fila histórica real de la muestra versionada:

```bash
python -m scripts.import_model_features \
  --dataset samples/xgboost/moisture_99_20220108.csv \
  --region-id ejemplo-historico --point-id moisture_99 \
  --issue-date 2022-01-08 --horizon-days 7 --preview
```

`--preview` calcula sin escribir en las bases. Sin esa opción se guarda un
snapshot JSON en FEATURE_DIRECTORY, tras validar sus entradas contra los modelos.
Es una demostración histórica, no un pronóstico actual. Las rutas Windows
contenidas en los artefactos se interpretan de forma portable; no se modifican
los archivos científicos ni se permiten rutas de fuente que escapen del proyecto.

`ExpandedFeatureStore` conserva revisiones por contenido en `versions/` y un
puntero por región/fecha. Los snapshots anteriores sin point_id siguen siendo
legibles. El job pide exclusivamente la fecha y coordenadas exactas. Guardar CSV
privados de finca no los incorpora automáticamente al modelo regional.

## Trabajo programado, resultados y límites

`CropRecommendationJob` prioriza campeones publicados con receta compatible.
Cuando no existen usa el bundle experimental identificado; si falta el snapshot
reciente devuelve `insufficient_data`, sin recuperar observaciones antiguas como
si fueran actuales. Clima sin suelo también puede producir ese estado parcial.
Los errores de integridad o ejecución conservan resultados y activan el backoff.

Las predicciones, versiones y hash de entradas pasan al motor de rotación y se
guardan en el backend de resultados configurado. Las recomendaciones necesitan
reglas agronómicas revisadas. Ni integrar artefactos ni recibir variables supone
publicación científica o autorización de siembra.

La extracción y preparación reciente de toda la receta multisensor sigue siendo
DATA-01 en [capacidades](capabilities.md). La actualización diaria no elimina ese
requisito. Entrenamiento y publicación se rigen por [su contrato](model-training.md).
