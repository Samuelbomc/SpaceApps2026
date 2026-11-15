# 15-, 30- and 60-day backtests

Fifteen model variants were trained and historically backtested: five targets for each of three horizons. Each predicts an aggregate over days t+1 through t+H. Temperature outputs are means over that interval, including means of daily minima/maxima; rainfall is the accumulated total; moisture is the mean of valid observed daily estimates. These are not predictions for conditions specifically on day 15, 30 or 60 and do not provide daily future trajectories.

## Test MAE

Each entry is **model MAE / persistence MAE**. Lower is better. Temperature units are C; precipitation is mm accumulated over the stated horizon; moisture is m3/m3.

| Model | 15 days | 30 days | 60 days |
|---|---:|---:|---:|
| Mean temperature | 0.52063 / 0.61528 | 0.47258 / 0.59741 | 0.47693 / 0.63114 |
| Minimum temperature | 0.39904 / 0.48724 | 0.35704 / 0.46510 | 0.37333 / 0.47708 |
| Maximum temperature | 0.82259 / 0.97030 | 0.76682 / 0.97171 | 0.79593 / 1.08206 |
| Precipitation | 62.50322 / 89.23447 | 102.81465 / 172.66210 | 176.05374 / 338.78133 |
| Moisture, baseline plus change | 0.03293 / 0.03706 | 0.03602 / 0.03519 | 0.03232 / 0.03477 |

The four climate models beat persistence at every horizon. Moisture beats it at 15 and 60 days but is slightly worse at 30 days on the full test set. Rainfall MAE grows with accumulation length; it cannot be compared directly across horizons without accounting for differing target totals. Lower temperature MAE over longer intervals partly reflects smoother averaged targets, not necessarily stronger long-range forecast skill.

The temperature test periods are September 30, 2023–September 2, 2026 at all horizons, with 9,621 rows each. Rainfall test periods start October 3, 6 and 12, 2023 for 15, 30 and 60 days respectively and end September 2, 2026, with 9,594, 9,567 and 9,513 rows. Moisture has 810, 828 and 828 test rows respectively, spanning approximately August 2021–January 2022. All training counts, exact dates, metrics and source hashes are saved in the per-horizon reports.

## Evaluation method

Each horizon has separately constructed observed targets and independently trained XGBoost models. No recursive reuse of seven-day predictions is involved. Inputs remain the existing historical feature recipe ending at t-2. Moisture uses the baseline-plus-change formulation. Persistence keeps the latest observed seven-day temperature/moisture mean; rainfall persistence extends the latest seven-day average rainfall rate over H days (`recent_7d_total * H / 7`). This is a simple baseline, not a seasonal meteorological forecast.

Chronological approximately 60/20/20 partitions group all locations from a date together. Every earlier target window reaching the next partition's observation cutoff is purged, using the actual horizon. Validation MAE selects tree count; the test set does not select hyperparameters. Default fixed settings are depth 3, learning rate 0.03, L2 10 and L1 0.1, with at most 800 rounds and early stopping. Moisture selected 36, 5 and 1 rounds for 15, 30 and 60 days. The 60-day model therefore provides only a minimal learned correction to its baseline.

All 15 validations passed: finite predictors and labels, correct horizon/date alignment, split purging, three source-label recomputations per variant, reproduced saved model predictions and verified metrics. No future targets were interpolated. `evaluation_model.json` is the evaluated artifact; `model.json` is refitted on all rows and has no independent post-refit test score. Moisture boosters predict change and require `MoistureChangePredictor` to add their baseline.

## Non-overlapping target-window check

The frozen evaluation models were also scored every H days, reducing overlapping target periods. Each entry remains model MAE / persistence MAE.

| Model | 15 days | 30 days | 60 days |
|---|---:|---:|---:|
| Mean temperature | 0.53465 / 0.61788 | 0.47305 / 0.65675 | 0.47156 / 0.81610 |
| Minimum temperature | 0.39347 / 0.48726 | 0.37281 / 0.53117 | 0.39986 / 0.59892 |
| Maximum temperature | 0.84687 / 0.98105 | 0.74141 / 1.03260 | 0.76283 / 1.33616 |
| Precipitation | 63.85438 / 88.65604 | 103.39741 / 178.95345 | 178.11965 / 302.86222 |
| Moisture | 0.04414 / 0.04704 | 0.01917 / 0.01990 | 0.01949 / 0.02431 |

Climate subsets contain 648, 324 and 162 rows respectively; moisture subsets contain 66, 36 and 18. Moisture's 60-day subset spans only three issue dates with six cells, so its apparent advantage is highly uncertain. Spatial correlation remains in all these subsets.

## Limits on interpretation

Moisture labels can contain as little as one observed day within the entire horizon. Test median coverage is 11/15, 20/30 and 34/60 days. These are incomplete observation averages, not independently verified whole-period soil-water means. The same sparse record and missing uncertainty limit evaluation. Moisture test R2 is approximately -0.561, -0.096 and 0.059 respectively.

Rainfall test R2 is approximately 0.115, 0.156 and 0.147; beating persistence does not establish operationally useful rain prediction. Temperature pooled R2 includes between-location differences. No unseen-region, station/gauge or independent prospective evaluation is provided. Publication-time availability remains unverified. These historical model-development holdouts are not a real-time forecast issued today. Prediction intervals, extreme-event timing and the exact state on the endpoint day are not estimated.

## Artifacts and reproduction

Datasets: `data/prepared/horizons/{15d,30d,60d}/`. Models, reports, partitions, curves and test predictions: `ml/artifacts/forecasts/{15d,30d,60d}/`. Consolidated metrics and label coverage: `ml/artifacts/forecasts/summary.json`. Seven-day artifacts are documented separately.

Run from the repository root:

```powershell
.\.venv-data\Scripts\python.exe -m ml.scripts.prepare_expanded_datasets --horizons 15 30 60
foreach ($horizon in 15,30,60) {
    .\.venv-data\Scripts\python.exe -m ml.scripts.train_prepared_models --manifest "data/prepared/horizons/${horizon}d/manifest.json" --output "ml/artifacts/forecasts/${horizon}d" --residual-moisture
    .\.venv-data\Scripts\python.exe -m ml.scripts.validate_expanded_datasets --dataset-root "data/prepared/horizons/${horizon}d" --artifact-root "ml/artifacts/forecasts/${horizon}d"
}
.\.venv-data\Scripts\python.exe -m ml.scripts.summarize_horizons
```
