# Available-data model datasets

Use `data/prepared/available/manifest.json` for the exact feature lists, target column names, counts and date ranges. Dataset paths in the table below are relative to `data/prepared/available/`. Metadata columns must not be included as predictors.

| File | Complete rows | Target |
|---|---:|---|
| temperature/temperature_mean.csv | 94 | Mean daily T2M over t+1 through t+7, C |
| temperature/temperature_min.csv | 94 | Mean daily T2M_MIN over t+1 through t+7, C |
| temperature/temperature_max.csv | 94 | Mean daily T2M_MAX over t+1 through t+7, C |
| water/precipitation.csv | 42 | Late Run rainfall accumulated over t+1 through t+7, mm |
| water/moisture.csv | 86 | Mean valid AM surface-moisture observations within t+1 through t+7, m3/m3 |

All accepted rows have finite required predictors and targets, unique location/issue-date keys, and observations ending at t-2. No interpolated inputs or labels were created. All accepted samples currently come from one POWER query location. The archive and quality screening limit coverage; these tables support prototype experiments, not robust regional validation.

User-authorized changes: use available Late Run instead of Final Run rainfall targets; omit unavailable GPM quality/error predictors; accept recommended SMAP retrievals with missing uncertainty recorded in audit columns. Exact daily moisture lags were omitted because the sparse archive cannot provide them reliably; observed recent moisture and seven-day summary remain. Moisture target observation counts are preserved, since the label need not represent seven measured days.

Strict-contract outputs remain separately under `data/prepared/water/`.

Reproduce and validate from the repository root:

```powershell
.\.venv-data\Scripts\python.exe -m ml.scripts.prepare_temperature_datasets --output data/prepared/available/temperature
.\.venv-data\Scripts\python.exe -m ml.scripts.prepare_water_datasets --available-data --output data/prepared/available/water
.\.venv-data\Scripts\python.exe -m ml.scripts.validate_available_datasets
```

Use chronological evaluation with all locations from a given issue date kept together. Do not randomly split overlapping time windows or treat several source-grid samples as independent measurements. No train/test split or model training was performed here.
