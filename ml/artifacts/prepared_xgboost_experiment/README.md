# Experimental prepared-data XGBoost models

Reproduce from the repository root with:

```powershell
.\.venv-data\Scripts\python.exe -m ml.scripts.train_prepared_models
```

The input feature lists and targets are taken from `data/prepared/available/manifest.json`. Source hashes, exact partitions, XGBoost version, parameters, and counts are recorded in `report.json` and per-model `training.json`.

Training uses chronological approximately 60/20/20 partitions grouped by issue date. Earlier rows whose target periods reach the next partition's observation cutoff are purged. Validation MAE selects the tree count with early stopping; the test partition is used only for final evaluation. The deliberately small trees and strong regularization are fixed settings, not a hyperparameter search.

Each model directory contains:

- `evaluation_model.json`: trained on the training partition; validation selected its tree count. The held-out test metrics apply to this artifact.
- `model.json`: refitted on every prepared row using the selected tree count. This artifact has no independent test score after refitting.
- `training.json`: ordered features, target, units, selected rounds, source hash, metrics and constant features.
- `partitions.csv`: all input rows classified as train, validation, test or purged.
- `test_predictions.csv`: actual values and model, persistence and training-mean baseline predictions.
- `learning_curves.json`: training/validation MAE across boosting rounds.

| Model | Test rows | XGBoost test MAE | Persistence test MAE | Unit |
|---|---:|---:|---:|---|
| Mean temperature | 19 | 1.11695 | 1.00850 | C |
| Minimum temperature | 19 | 0.40998 | 0.51030 | C |
| Maximum temperature | 19 | 1.79125 | 1.62376 | C |
| Precipitation | 9 | 52.97165 | 29.53722 | mm per week |
| Surface moisture | 18 | 0.07245 | 0.04747 | m3/m3 |

Persistence means the recent seven-day value: mean temperature, mean daily minimum/maximum, accumulated rainfall, or average valid observed surface moisture. Only minimum temperature beats this baseline on the available holdout. Small test sizes mean even that result is uncertain. The precipitation model selected only one boosting round and shows no useful predictive advantage here.

All datasets represent one location and sparse SMAP-selected weeks. Static terrain and soil features cannot teach spatial effects in a one-location experiment. Missing SMAP uncertainty, incomplete weekly moisture measurements, Late Run rainfall targets, unverified publication-time availability, and source estimation errors limit interpretation. Temperature minimum/maximum targets are weekly averages of daily extrema. None of these artifacts is promoted to production or validates agricultural recommendations. No uncertainty intervals are supplied.
