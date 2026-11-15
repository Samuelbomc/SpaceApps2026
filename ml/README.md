# Forecast models

Rolling-origin validation is the default training pipeline for all five outputs and all four horizons. The canonical model names are:

- `temperature_mean`
- `temperature_min`
- `temperature_max`
- `precipitation`
- `moisture`

Models are stored exclusively under `ml/artifacts/forecasts/<horizon>d/<model_name>/`, with horizons 7, 15, 30 and 60. `models.json` in that root indexes the current models. The names are identical across the index, metadata and inference loader. Older model collections and their training commands have been removed.

## Train and validate

Run from the repository root using the local Python environment:

```powershell
# Rebuild prepared data only when source data or the recipe changes.
.\.venv-data\Scripts\python.exe -m ml.scripts.prepare_expanded_datasets --horizons 7 15 30 60

# Default pipeline: all five models at every horizon.
.\.venv-data\Scripts\python.exe -m ml.scripts.train_rolling_origin
.\.venv-data\Scripts\python.exe -m ml.scripts.validate_rolling_origin
.\.venv-data\Scripts\python.exe -m ml.scripts.summarize_rolling_origin
```

Training derives its chronological test split directly from the prepared issue dates, then uses four expanding-window folds entirely before that test period. Validation selects configuration and tree count. Horizon-aware purging prevents target leakage. Moisture predicts a correction to recent observed moisture; the other four outputs predict absolute horizon aggregates.

The workflow requires numpy, pandas, rasterio, h5py and xgboost. It reads `data/prepared/expanded/` for 7 days and `data/prepared/horizons/<horizon>d/` for longer horizons. No older artifacts are needed to train or validate.

## Default inference

```python
from ml.inference.forecast import ForecastPredictor

model = ForecastPredictor("temperature_mean", horizon_days=7)
predictions = model.predict(feature_dataframe)

moisture = ForecastPredictor("moisture", horizon_days=30)
predicted_moisture = moisture.predict(moisture_feature_dataframe)
```

Use the ordered feature list from each model's `training.json`. The loader validates model identity and horizon, requires finite features, and adds the observed baseline for moisture automatically. Default inference loads the all-data refit `model.json`. Pass `evaluation=True` to load `evaluation_model.json` when reproducing holdout results. Only the evaluation artifact has the reported independent-of-fitting holdout scores; those historical holdouts have nevertheless informed development.

## Folder map

- `scripts/`: current data preparation, rolling-origin training, validation and reporting commands.
- `artifacts/forecasts/`: the 20 canonical trained models and their reports.
- `inference/`: the default forecast loader, moisture reconstruction helper and application prediction interfaces.
- `training/` and `evaluation/`: reusable application lifecycle contracts, artifact integrity checks, metrics and publication policies.
- `configs/`: canonical output/horizon configuration and the packaged crop catalog.
- `recommendations/`: crop-catalog loading and explainable screening.
- `docs/`: [architecture](docs/architecture.md), [data recipes](docs/expanded-datasets.md), [training protocol](docs/rolling-origin-results.md), [current results](docs/model-results.md), [horizon semantics](docs/horizon-results.md) and [moisture inference](docs/moisture-change-model.md).

Source downloaders remain in the repository's `scripts/` folder, and datasets remain in `data/`. Making these the default local models does not bypass the application's separate registry and publication policies.
