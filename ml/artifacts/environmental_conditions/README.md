# Artefactos experimentales de condiciones ambientales

Este directorio contiene cuatro regresores climáticos de siete días y un
comparador de humedad absoluta. La formulación residual de humedad se encuentra
en `ml/artifacts/soil_moisture/`.

Cada objetivo conserva `evaluation_model.json`, `model.json`, `training.json`,
particiones, curvas y predicciones. `report.json` contiene fuentes, hiperparámetros,
iteraciones y métricas. Los scores de holdout corresponden al artefacto de
evaluación; el reajuste con todas las filas no tiene test independiente posterior.

La evaluación agrupa celdas por fecha y purga ventanas solapadas. Las fuentes son
estimaciones con resolución y disponibilidad propias; estos artefactos no están
publicados como modelos agrícolas validados.

Ver [evaluación de siete días](../../../docs/reference/ml/seven-day-results.md),
[humedad residual](../../../docs/reference/ml/moisture-model.md) y
[contrato de inferencia](../../../docs/reference/model-inference.md).
