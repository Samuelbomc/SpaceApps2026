# Artefactos experimentales de humedad residual

Los Boosters predicen un cambio respecto de `smap_mean_7d`. La salida absoluta es
baseline observado + cambio predicho. `MoistureChangePredictor` realiza esa suma
exactamente una vez.

`evaluation_model.json` es el artefacto evaluado sobre la partición reservada;
`model.json` está reajustado con todas las filas. `training.json` conserva receta,
fuentes, baseline, columnas y métricas. La comparación sobre un holdout examinado
durante desarrollo es exploratoria y no valida un pronóstico operativo de finca.

Ver [método y evaluación](../../../docs/reference/ml/moisture-model.md) y
[contrato de inferencia](../../../docs/reference/model-inference.md).
