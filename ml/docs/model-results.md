# Current model test results

This document covers seven-day models. Separate 15-, 30- and 60-day aggregate backtests are documented in `ml/docs/horizon-results.md`.

Current datasets use daily issue dates and seven-day targets. Temperature and precipitation use nine POWER query locations without a SMAP dependency; moisture uses accepted AM/PM measurements from six native SMAP cells. Feature lists and exact dataset periods are in `data/prepared/expanded/manifest.json`.

## Four climate models

These results are read from `ml/artifacts/environmental_conditions/report.json` and verified against saved test predictions. Scores apply to each `evaluation_model.json`, not the model refitted on all rows. MAE is mean absolute error, RMSE is root mean squared error, and bias is prediction minus observation. Lower MAE and RMSE are preferred.

| Model | Train / validation / test rows | Test MAE | Persistence MAE | Test RMSE | Test bias | Test R2 |
|---|---|---:|---:|---:|---:|---:|
| Mean temperature (C) | 28,782 / 9,540 / 9,621 | 0.575908 | 0.638650 | 0.771435 | -0.118880 | 0.941252 |
| Minimum temperature (C) | 28,782 / 9,540 / 9,621 | 0.457642 | 0.520170 | 0.584107 | -0.200555 | 0.964445 |
| Maximum temperature (C) | 28,782 / 9,540 / 9,621 | 0.916883 | 1.007309 | 1.209370 | -0.022864 | 0.879987 |
| Precipitation (mm/week) | 28,737 / 9,531 / 9,612 | 37.054691 | 46.310188 | 51.300500 | -8.002806 | 0.064353 |

Temperature test dates are September 30, 2023–September 2, 2026. Precipitation test dates are October 1, 2023–September 2, 2026. Minimum and maximum targets are weekly means of daily extrema, not absolute weekly extrema. Persistence predicts the preceding seven-day observed value using measurements through t-2.

All four beat persistence on these test rows. Precipitation still has low explained variance and substantial weekly error; beating persistence does not establish agronomic usefulness. Temperature R2 is pooled across locations and partly reflects spatial temperature differences.

## Non-overlapping target-week check

The same frozen models were evaluated on a seven-day-spaced subset, containing 1,377 rows per climate model. This reduces target overlap but retains dependence between spatial samples.

| Model | XGBoost MAE | Persistence MAE |
|---|---:|---:|
| Mean temperature (C) | 0.557534 | 0.635569 |
| Minimum temperature (C) | 0.450803 | 0.502744 |
| Maximum temperature (C) | 0.900049 | 1.008014 |
| Precipitation (mm/week) | 36.850166 | 45.475892 |

## Current moisture model

The current moisture recipe predicts change relative to recent observed moisture: `prediction = smap_mean_7d + predicted_change`. It uses the same expanded dataset with 2,310 training, 738 validation and 792 test rows. Test dates are August 8, 2021–January 8, 2022.

| Method | MAE (m3/m3) | RMSE (m3/m3) | Bias (m3/m3) | R2 |
|---|---:|---:|---:|---:|
| Baseline plus predicted change | 0.035938 | 0.045883 | -0.001468 | -0.565090 |
| Persistence | 0.037633 | 0.047908 | 0.001384 | -0.706297 |

On 114 non-overlapping-target rows, MAE is 0.037883 versus persistence 0.039400. Full details and inference instructions are in `ml/docs/moisture-change-model.md`; artifacts are in `ml/artifacts/soil_moisture/`. The absolute-moisture model in the expanded experiment is retained as the frozen comparator for this correction experiment, not as the current moisture predictor.

## Validation and limitations

Chronological approximately 60/20/20 partitions group all samples from an issue date together. Rows whose targets reach the next partition's observation cutoff are purged. Validation MAE selects tree count; test labels do not select the tree count. Saved artifacts, source hashes, sampled raw labels, finite features, temporal alignment and metrics are checked by the current validation scripts.

Daily targets overlap, nearby cells share information, and native source resolution limits the number of independent observations. No unseen-region or gauge/field validation was performed. Source publication delays are not independently backtested. SMAP labels have variable observation coverage and missing uncertainty. The moisture holdout had already informed development, so its improvement is exploratory rather than independent confirmation. All-data refits include test rows; reported holdout scores apply only to evaluation artifacts. None of these results constitutes validation of rotation recommendations.

## Previous iterations

The initial recipes required recent SMAP for every model and emitted one example per week at selected POWER locations. This left 94 examples per temperature model, 42 for precipitation and 86 for moisture, all from one location. Their test sets had only 19, 9 and 18 rows respectively. Test MAEs were: mean temperature 1.11695 C, minimum temperature 0.40998 C, maximum temperature 1.79125 C, precipitation 52.97165 mm/week and moisture 0.07245 m3/m3. Only minimum temperature beat persistence in that iteration.

That short-dataset workflow and its datasets, validation entry point, model binaries, reports and standalone documentation have been removed. These numbers are retained here only as development history. They use different recipes and test periods and must not be interpreted as a controlled comparison with current scores. The current workflow is the expanded dataset preparation, climate-model training and moisture-change training documented above.
