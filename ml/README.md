# Modelos XGBoost de AgroGeo

Los veinte modelos canónicos se encuentran en `artifacts/forecasts/<horizonte>d/<modelo>/`.
Los horizontes son 7, 15, 30 y 60 días; los nombres son `temperature_mean`,
`temperature_min`, `temperature_max`, `precipitation` y `moisture`.

La selección utiliza cuatro ventanas temporales expansivas anteriores al test,
con purga de etiquetas por horizonte. La humedad predice una corrección que se
suma una sola vez a `smap_mean_7d`; las otras salidas son agregados absolutos.
`evaluation_model.json` conserva el ajuste anterior al test. `model.json` está
reajustado con todas las filas y no tiene una evaluación independiente posterior.
Estos artefactos son experimentales; el registro operativo aplica sus políticas
de validación y publicación.

## Uso y contratos

- [Entrenamiento, datasets y publicación](../docs/reference/model-training.md).
- [Entradas e inferencia](../docs/reference/model-inference.md).
- [Resultados rolling-origin](../docs/reference/ml/rolling-origin-results.md).
- [Evaluación por horizonte](../docs/reference/ml/horizon-results.md).
- [Arquitectura y flujo completo](../docs/architecture/flows.md).

## Reproducción científica

Desde la raíz, con las dependencias científicas y las fuentes verificadas:

```bash
python -m ml.scripts.prepare_expanded_datasets --horizons 7 15 30 60
python -m ml.scripts.train_rolling_origin
python -m ml.scripts.validate_rolling_origin
python -m ml.scripts.summarize_rolling_origin
python -m ml.sample_forecasts
```

Las fuentes y etiquetas no se reconstruyen a partir de predicciones. Los scripts
científicos no se ejecutan al importar FastAPI. Las consultas HTTP leen resultados
almacenados; el worker diario evalúa nuevas versiones cuando existen entradas
procesadas y etiquetas disponibles.
