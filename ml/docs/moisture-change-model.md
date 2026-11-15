# Soil moisture: persistence plus predicted change

The model predicts mean valid surface soil moisture in the next seven days. Instead of learning absolute moisture directly, XGBoost now learns the difference from the observed preceding-week baseline:

```text
baseline = smap_mean_7d
training_change = target_weekly_moisture - baseline
predicted_weekly_moisture = baseline + XGBoost(features)
```

The baseline is the average of valid observed AM/PM daily moisture estimates during the seven calendar days ending at t-2. It is calculated independently for each cell and forecast date. The target averages valid observations between t+1 and t+7. This predicts a correction to recent observed moisture; it does not use a forecast or future measurement as its baseline.

The expanded prepared dataset and feature list are unchanged. Training reuses exactly the prior model's frozen partitions: 2,310 training rows, 738 validation rows and 792 test rows. All locations on a date stay in the same partition, and overlapping target periods are purged at boundaries. Source SHA-256 is checked before fitting. Hyperparameters remain the previous depth-3 configuration; validation MAE selects the round count, with 10 rounds selected. MAE on moisture changes is equivalent to MAE on reconstructed absolute moisture because the same row-specific baseline is added to both targets and predictions.

## Results

Errors are in m3/m3, with lower MAE/RMSE preferred. Scores use the same test rows, August 8, 2021 through January 8, 2022.

| Method | Test MAE | Test RMSE | Test bias | Test R2 |
|---|---:|---:|---:|---:|
| Previous absolute XGBoost | 0.077293 | 0.087240 | -0.076663 | -4.658153 |
| Persistence | 0.037633 | 0.047908 | 0.001384 | -0.706297 |
| Baseline plus predicted change | **0.035938** | **0.045883** | -0.001468 | -0.565090 |

The correction model reduces MAE by about 53.5% relative to the previous absolute model and by about 4.5% relative to persistence. Validation MAE is 0.034649 versus persistence 0.035492. On 114 seven-day-spaced test rows with non-overlapping target windows, MAE is 0.037883 versus persistence 0.039400 and the prior absolute model 0.080120. There was no blend, prediction clipping or parameter search based on test results.

The existing test set had already been examined and motivated this experiment. These scores are an exploratory same-holdout comparison, not an untouched confirmation. Negative test R2 indicates substantial remaining errors relative to the test target variation; the modest baseline improvement does not establish reliable forecasts. Overlapping windows, nearby cells, sparse SMAP coverage, variable target observation counts and missing uncertainty remain limitations. Future independent data or additional prespecified chronological evaluation is needed before deployment.

## Artifacts and inference

Artifacts are in `ml/artifacts/moisture_change_experiment/`. `evaluation_model.json` is the tested residual model. `model.json` is refitted on all prepared rows with the selected 10 rounds and has no independent post-refit score. Both JSON files predict a **change**, not absolute moisture. `training.json` records the required baseline, ordered feature list, source hash, split source, metrics and limitations. Per-partition predictions record the baseline, correction and absolute prediction.

Use the inference wrapper to reconstruct the absolute output correctly:

```python
from ml.inference.moisture_change import MoistureChangePredictor

predictor = MoistureChangePredictor("ml/artifacts/moisture_change_experiment")
predicted_moisture = predictor.predict(feature_dataframe)
```

For reproducing test scores, pass `evaluation=True` to load the evaluated artifact. The wrapper enforces finite predictors and the saved feature order. It adds `smap_mean_7d` exactly once and performs no clipping. Loading this residual JSON through the older absolute-regression path without adding the baseline would produce incorrect units/meaning.

Reproduce the experiment from the repository root:

```powershell
.\.venv-data\Scripts\python.exe -m ml.scripts.train_moisture_change
```

The script verifies split purging, original dataset identity, alignment with the old test predictions, and equality of reconstructed predictions after saving/reloading both artifacts. The other four models remain in their existing experiment directories. No production model registry is changed.
