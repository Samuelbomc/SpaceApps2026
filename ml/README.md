# Model workspace

Los cinco modelos del equipo ya tienen [integración de inferencia](../docs/xgboost-integration.md):
catálogo HTTP, job, snapshots de variables y visualización Angular. Cubren siete
días y conservan su estado experimental; los pronósticos actuales requieren
entradas recientes completas de su receta.

- `artifacts/`: saved XGBoost models, experiment reports, partitions and predictions.
- `docs/`: dataset recipes, reproduction instructions, moisture-change design and limitations.
- `scripts/`: dataset preparation, validation and experiment training entry points.
- `inference/`: prediction adapters, including baseline-plus-change moisture inference.
- `training/`, `evaluation/`, `features/`, `configs/`: existing model infrastructure.

Run commands as Python modules from the repository root:

```powershell
.\.venv-data\Scripts\python.exe -m ml.scripts.prepare_expanded_datasets
.\.venv-data\Scripts\python.exe -m ml.scripts.train_prepared_models --manifest data/prepared/expanded/manifest.json --output ml/artifacts/expanded_xgboost_experiment --max-depth 3 --max-rounds 800
.\.venv-data\Scripts\python.exe -m ml.scripts.train_moisture_change
.\.venv-data\Scripts\python.exe -m ml.scripts.validate_expanded_datasets
```

Dataset files remain under `data/prepared/`, and source downloaders remain under `scripts/`. Detailed recipes are in `ml/docs/`. All previous experiment artifacts are preserved under `ml/artifacts/`; the moisture-change experiment requires the inference wrapper to add its recent-observation baseline.
