# Model workspace

Los cinco modelos del equipo ya tienen [integración de inferencia](../docs/xgboost-integration.md):
catálogo HTTP, job, snapshots de variables y visualización Angular. Cubren siete
días y conservan su estado experimental; los pronósticos actuales requieren
entradas recientes completas de su receta.

- `artifacts/`: saved XGBoost models, experiment reports, partitions and predictions.
- `docs/`: dataset recipes, reproduction instructions, moisture-change design and limitations.
- `scripts/`: dataset preparation, validation and experiment training entry points.
- `inference/`: prediction adapters, including baseline-plus-change moisture inference.
- `training/`: reusable trainer contracts, XGBoost adapter and verified artifact storage for application pipelines.
- `evaluation/`: temporal splitting, MAE and model-promotion decisions for application pipelines.
- `recommendations/`: crop-catalog loading and explainable suitability screening.
- `configs/`: packaged crop catalog used by `recommendations/` and the API.

Folder dependencies and the distinction between experiment artifacts and registered application models are documented in [architecture.md](docs/architecture.md). Current test results are in [model-results.md](docs/model-results.md).

The separately trained 15-, 30- and 60-day variants are documented in [horizon-results.md](docs/horizon-results.md), with datasets under `data/prepared/horizons/` and artifacts under `ml/artifacts/forecasts/`.

Run commands as Python modules from the repository root:

```powershell
.\.venv-data\Scripts\python.exe -m ml.scripts.prepare_expanded_datasets
.\.venv-data\Scripts\python.exe -m ml.scripts.train_prepared_models --manifest data/prepared/expanded/manifest.json --output ml/artifacts/environmental_conditions --max-depth 3 --max-rounds 800
.\.venv-data\Scripts\python.exe -m ml.scripts.train_moisture_change
.\.venv-data\Scripts\python.exe -m ml.scripts.validate_expanded_datasets
```

Current datasets are under `data/prepared/expanded/`, and source downloaders remain under `scripts/`. Detailed recipes are in `ml/docs/expanded-datasets.md`; test results for all five models are in `ml/docs/model-results.md`. The moisture-change experiment requires the inference wrapper to add its recent-observation baseline. Superseded short-dataset work is documented only in the Previous iterations section of that results document.
