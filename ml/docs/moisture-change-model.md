# Moisture forecast

The canonical name is `moisture` at horizons 7, 15, 30 and 60 days. XGBoost predicts the change from the recent seven-day observed moisture mean, `smap_mean_7d`, to the mean valid SMAP moisture in the future period.

Absolute prediction equals the raw booster change plus the baseline. The default loader reconstructs this automatically:

```python
from ml.inference.forecast import ForecastPredictor
predictor = ForecastPredictor("moisture", horizon_days=7)
absolute_moisture = predictor.predict(feature_frame)
```

Use `evaluation=True` for the pre-test evaluation model. The directory-based MoistureChangePredictor helper also supports these artifacts.

Training uses `python -m ml.scripts.train_rolling_origin` and the same four purged expanding-window folds as the other outputs. Candidate selection and evaluation use reconstructed absolute moisture. Artifacts are in `ml/artifacts/forecasts/<horizon>d/moisture/`. Metadata records the baseline, ordered predictors, sources, folds, settings and scores. `model.json` is refitted on all rows; `evaluation_model.json` uses eligible development rows only.

Quality-screened retrievals supply labels without interpolation. Missing uncertainty is recorded. Recent observation features can retain a value for at most six days, with age/count predictors. Sparse retrievals, six native cells, overlapping windows and shared meteorology limit independence and spatial generalization. See [model-results.md](model-results.md).

## Previous iterations

Short complete-case data and an absolute-moisture formulation preceded the current baseline-plus-change pipeline. Their obsolete trained artifacts and training commands have been removed.
