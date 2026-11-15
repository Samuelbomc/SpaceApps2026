# Contrato de entradas e inferencia XGBoost

La receta integrada es `daily-direct-1-60-v1`. Cinco modelos compartidos predicen
cada día objetivo entre 1 y 60 días después de la emisión. Sus pesos están en
`ml/artifacts/forecasts/{modelo}/model.json`, acompañados de `training.json`.
`ml/configs/pretrained-bundle.json` fija sus hashes y se comprueba antes de inferir.

## Entradas y fechas

`GET /api/v1/models/input-contract` expone las columnas ordenadas y metadatos.
El productor entrega 49 variables climáticas o 71 de suelo, incluidas las comunes.
El predictor añade `lead_days`, `target_day_of_year_sin`,
`target_day_of_year_cos` y `target_week_of_year`: los Boosters reciben 53 o 75
columnas. Estas cuatro variables se derivan del calendario conocido, no de
observaciones futuras.

Se requieren `point_id`, coordenadas WGS84, `issue_date`, `observation_cutoff`
exactamente emisión menos dos días y `radiation_observation_cutoff` exactamente
emisión menos siete días. El receptor calcula SHA-256 y asigna `region_id`.
Clima y suelo deben compartir sus variables comunes; suelo completo u omitido.
No se requieren etiquetas futuras para inferir.

POWER utiliza días LST; GPM y SMAP, UTC. El productor debe respetar ventanas,
rellenos causales acotados, edades y contadores de calidad de la receta entrenada.
El receptor exige entradas finitas y no rellena huecos. No convierte datos UTC
en LST renombrando su metadato ni cambia coordenadas o emisiones de las observaciones.
La selección de una referencia cercana es explícita y conserva esa diferencia
en el resultado geográfico.

## Salidas diarias y periodos

Las salidas son temperatura media, mínima y máxima diarias (°C), precipitación
diaria (mm) y humedad superficial (m³/m³). Humedad reconstruye
`smap_mean_7d + XGBoost(features)` una sola vez. La lluvia es una salida absoluta;
no se multiplica por el horizonte.

Para una consulta el día D se exige emisión D−1. Se calculan D hasta D+H−1 y
se conservan los valores diarios. Los resúmenes de 7/15/30/60 días son medias
de las temperaturas y humedad y suma de lluvia diaria. Predecir el día 30 no
equivale a predecir la media de los treinta días.

## Recepción, uso y trazabilidad

`ml/features/daily.py` recibe CSV sin etiquetas. Admite filas por lead solo cuando
sus variables base son idénticas; rechaza duplicados contradictorios, columnas
incompletas, entradas no finitas y fechas incompatibles. `ExpandedFeatureStore`
conserva snapshots diarios y revisiones por contenido. El nombre histórico de
esa clase no cambia la receta que debe declarar el documento recibido.

```bash
python -m scripts.import_model_features \
  --dataset ml/examples/inputs/moisture.csv \
  --region-id ejemplo-publico --point-id smap_0 \
  --issue-date 2026-11-15 --horizon-days 7 --preview
```

El ejemplo conserva sus coordenadas y fecha; `--preview` no escribe en las bases.
La carga automática por ubicación y la búsqueda de referencias cercanas están
descritas en [análisis geográfico](geographic-analysis.md). La respuesta conserva
las coordenadas solicitadas y utilizadas en `spatial_match`; las coordenadas del
snapshot no cambian. La cercanía no permite sustituir la fecha requerida.

`DailyModelBundle` resuelve campeones en slots `<region>:daily:<modelo>` cuando
existen, verifica artefactos y alcance y, en ausencia de campeón, identifica el
bundle distribuido como experimental. El resultado conserva versiones por
componente, versión compuesta, snapshot, fecha de entrada y serie diaria.

## Evaluación y límites

Los pesos distribuidos se reajustaron con todas las etiquetas observadas. Las
métricas incluidas proceden de la evaluación pre-test local y no son una evaluación
independiente posterior al reajuste. Los archivos de evaluación completos no se
incluyen en Git. Los MAE diarios conjuntos de leads 1–60 tampoco son errores
medidos del resumen de un periodo.

La disponibilidad de pesos no completa la extracción reciente multisensor ni
publica campeones científicos. La inferencia y la evaluación de rotación se
realizan en workers; HTTP solo encola o consulta resultados almacenados.
