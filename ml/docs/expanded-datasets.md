# Expanded available-data recipes

The exact ordered feature lists, target names, row counts, date ranges and spatial sample counts are in `data/prepared/expanded/manifest.json`. The `preparation.json` and `validation.json` files in that same dataset directory record sources, policies and completed checks. Raw downloads and previous prepared datasets remain intact.

| Model | Rows | Spatial samples | Previous rows |
|---|---:|---:|---:|
| Mean temperature | 48,105 | 9 POWER query locations | 94 |
| Minimum temperature | 48,105 | 9 POWER query locations | 94 |
| Maximum temperature | 48,105 | 9 POWER query locations | 94 |
| Precipitation | 48,042 | 9 POWER query locations | 42 |
| Soil moisture | 3,948 | 6 native SMAP cells with accepted rows | 86 |

All models issue daily predictions for days t+1 through t+7, using measurements no later than t-2. Climate models no longer require SMAP, allowing the full usable historical climate archive to contribute. They use historical POWER temperature, humidity, wind and radiation; historical GPM Late precipitation; elevation; and seasonal calendar features.

Moisture samples use native SMAP cell centres inside the study AOI. AM and PM retrievals are screened using recommended-retrieval bits, finite surface metadata, published moisture ranges, and error ranges when available. Missing uncertainty is permitted as authorized and its observation count is retained. Valid AM/PM moisture estimates are averaged within each day, then valid days within the target week are averaged. Target observation and retrieval counts remain audit metadata. SoilGrids and terrain values are sampled at the native moisture-cell centre; meteorology comes from the nearest downloaded POWER query location. This provides coarse context, not finer weather resolution.

No linear temporal interpolation, spatial upsampling or synthetic labels were used. A latest-observation moisture feature may retain a prior valid observation for at most six days, with its age and preceding-week observation count supplied as predictors. All target values are built from actual valid source estimates. Missing POWER/rainfall window days invalidate the window. All accepted predictors and labels are finite.

The extra rows are correlated: consecutive seven-day forecast targets overlap, neighbouring grids share environmental information, and several POWER query locations may map to shared source cells. Row counts are not counts of independent measurements. Chronological holdout partitions keep all locations on each date together and purge target periods reaching the next partition's observation cutoff. This does not test transfer to unseen regions.

Reproduce from the repository root:

```powershell
.\.venv-data\Scripts\python.exe -m ml.scripts.prepare_expanded_datasets
.\.venv-data\Scripts\python.exe -m ml.scripts.train_prepared_models --manifest data/prepared/expanded/manifest.json --output ml/artifacts/expanded_xgboost_experiment --max-depth 3 --max-rounds 800
.\.venv-data\Scripts\python.exe -m ml.scripts.validate_expanded_datasets
```

Dependencies: numpy, pandas, rasterio, h5py and xgboost. Model features changed and holdout dates differ from the earlier sparse experiment; compare each new model against its baseline on the same new test rows rather than treating old/new aggregate metrics as a controlled comparison.
