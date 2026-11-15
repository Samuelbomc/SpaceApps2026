# Expanded-data experimental XGBoost models

Follow-up: `ml/artifacts/soil_moisture/` evaluates moisture as persistence plus a predicted change. See `ml/docs/moisture-change-model.md`. That separate experiment improves moisture test MAE to 0.035938 m3/m3, compared with 0.037633 for persistence and 0.077293 for the original absolute model documented below. Original artifacts and scores here are retained for reproducible comparison.

All five models were trained from `data/prepared/expanded/manifest.json`. Details, feature ordering, source hashes, parameters, selected tree counts and metrics are in `report.json`. Each model folder contains `model.json` (refitted on every row), `evaluation_model.json`, `training.json`, learning curves, partitions and test predictions. Held-out metrics apply only to evaluation_model.json; the full-data refit has no independent evaluation.

Training uses approximately 60/20/20 chronological partitions by issue date, with all locations grouped on each date. Earlier target periods that reach the next partition's observation cutoff are purged. Validation MAE selects the tree count; the test data does not select parameters. Trees have maximum depth 3, learning rate 0.03, L2 regularization 10 and L1 regularization 0.1. There was no test-driven hyperparameter search.

| Model | Test rows | Test MAE | Persistence baseline MAE | Unit |
|---|---:|---:|---:|---|
| Mean temperature | 9,621 | 0.57591 | 0.63865 | C |
| Minimum temperature | 9,621 | 0.45764 | 0.52017 | C |
| Maximum temperature | 9,621 | 0.91688 | 1.00731 | C |
| Precipitation | 9,612 | 37.05469 | 46.31019 | mm/week |
| Soil moisture | 792 | 0.07729 | 0.03763 | m3/m3 |

The baseline predicts the preceding seven-day value using observations through t-2. Climate test periods span approximately October 2023–September 2026; moisture test data covers August 2021–January 2022. Exact dates are stored per model.

The same frozen evaluation models were also scored on a seven-day-spaced subset to avoid overlapping target weeks. These secondary MAEs are temperature mean 0.55753 vs baseline 0.63557; minimum 0.45080 vs 0.50274; maximum 0.90005 vs 1.00801; rain 36.85017 vs 45.47589; moisture 0.08012 vs 0.03940. Spatial dependence remains.

Interpretation: four climate models beat persistence on these holdouts. Precipitation still has low explained variance (test R2 approximately 0.064) and about 37 mm weekly MAE, limiting decision usefulness. Moisture is worse than persistence, with negative R2 and strong negative bias, and should not replace that baseline. More rows did not resolve the temporal generalization problem in the sparse moisture archive.

Limitations: source products are estimates rather than field measurements; publication delays are not independently backtested; Late Run rainfall targets lack gauge validation; missing SMAP uncertainty remains unquantified; moisture labels average variable numbers of valid days; daily targets and nearby cells are correlated; native SMAP sampling does not create finer independent resolution; no unseen-region validation, predictive intervals or agronomic recommendation validation were performed. High pooled temperature R2 also includes spatial temperature differences and is not by itself evidence of strong within-location forecast skill. These artifacts remain experimental and have not been promoted to production.

Consolidated current test results and historical context are in `ml/docs/model-results.md`.
