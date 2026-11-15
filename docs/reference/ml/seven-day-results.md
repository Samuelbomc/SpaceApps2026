# Current daily model results

Five output-named XGBoost models predict individual future days at leads 1-60. All saved holdout predictions, source hashes, temporal splits and current inference rows passed validation. The canonical collection is ml/artifacts/forecasts/<output>/.

## Pooled daily holdout metrics

Scores below evaluate evaluation_model.json, fitted on eligible pre-test pairs. The default model.json refits all observed pairs, including test labels, and has no independent post-refit score. Temperature units are C, rainfall mm/day, and moisture m3/m3. Lower MAE/RMSE are preferred; bias is prediction minus observation.

| Output | Test pairs | MAE | Persistence MAE | RMSE | Bias | R2 | Rounds |
|---|---:|---:|---:|---:|---:|---:|---:|
| temperature_mean | 572,130 | 0.82808 | 1.03658 | 1.09829 | -0.06361 | 0.8841 | 196 |
| temperature_min | 572,130 | 0.70039 | 0.91509 | 0.88736 | -0.25006 | 0.9202 | 163 |
| temperature_max | 572,130 | 1.47540 | 1.89116 | 1.90652 | 0.15425 | 0.7338 | 263 |
| precipitation | 571,590 | 9.52472 | 12.36221 | 16.05492 | -1.11187 | 0.0112 | 109 |
| moisture | 3,239,095 | 0.04584 | 0.04982 | 0.05848 | -0.00230 | 0.4935 | 84 |

## Selected daily leads

Each entry is model MAE / persistence MAE for that individual target day. Complete scores for all 60 leads are in ml/artifacts/forecasts/lead_metrics.csv.

| Output | Day 1 | Day 7 | Day 15 | Day 30 | Day 60 |
|---|---:|---:|---:|---:|---:|
| temperature_mean | 0.74859 / 0.77026 | 0.78317 / 0.91679 | 0.79897 / 1.00949 | 0.80960 / 1.06223 | 0.92038 / 1.20272 |
| temperature_min | 0.68325 / 0.78529 | 0.69868 / 0.87057 | 0.69570 / 0.91092 | 0.69727 / 0.91856 | 0.72710 / 0.99146 |
| temperature_max | 1.36138 / 1.44787 | 1.41073 / 1.64795 | 1.43184 / 1.80426 | 1.43797 / 1.92432 | 1.62898 / 2.21270 |
| precipitation | 9.44309 / 11.67151 | 9.46297 / 12.13116 | 9.47571 / 11.88630 | 9.49673 / 12.36485 | 9.67191 / 12.86106 |
| moisture | 0.04012 / 0.03888 | 0.04288 / 0.04392 | 0.04547 / 0.04821 | 0.04553 / 0.04918 | 0.05039 / 0.05739 |

## Training and dates

Four expanding-window validation blocks start at 40%, 55%, 70% and 85% of pre-test issue dates. Three depth/minimum-child-weight/L2 configurations are compared: (2,10,20), (3,5,10), (4,10,20), with learning rate 0.03, L1 0.1, seed 42, histogram trees, max_bin 256, up to 800 rounds and 30-round early stopping. Pooled validation MAE selects configuration; median best fold rounds selects tree count. Dates are grouped across locations and leads. Training target dates must precede the next observation cutoff; validation targets are also purged before the next block. The final 20% of issue dates form the holdout.

Daily persistence uses the last available daily temperature/rainfall input. Moisture retains the recent observed baseline plus a learned correction. Holdout metrics include all 60 leads; source labels recur at multiple leads, so pair counts are not independent sample counts.

| Output | Test issue dates | Latest observed training target |
|---|---|---|
| temperature_mean | 2023-11-19 to 2026-11-11 | 2026-11-12 |
| temperature_min | 2023-11-19 to 2026-11-11 | 2026-11-12 |
| temperature_max | 2023-11-19 to 2026-11-11 | 2026-11-12 |
| precipitation | 2023-11-19 to 2026-11-11 | 2026-11-12 |
| moisture | 2025-07-09 to 2026-11-10 | 2026-11-11 |

Current prepared inference inputs are issued November 15, 2026 and cover November 16, 2026 through January 14, 2027. Forecasting from a later date requires freshly prepared features with acceptable observation ages; the model can accept any valid issue date, not only the prepared example.

## Limitations

These are historical development holdouts, not prospective field validation. Nearby cells, shared meteorology and repeating labels across leads cause dependence; pooled temperature R2 includes spatial differences. Most accepted SMAP retrievals are non-recommended; sparse daily coverage, approximate static fills and missing uncertainty can bias moisture labels. Daily rainfall is harder than predicting smoothed multi-day totals, and beating persistence does not establish operational usefulness. A missing GPM file is excluded only on its target day, not filled into a label.

POWER uses LST daily intervals and GPM/SMAP use UTC intervals. Weather/rain/SMAP use a two-day observation lag; radiation uses seven days. Causal bounded input filling and observation-age predictors handle gaps, but actual historical publication times are not certified. There are no calibrated prediction intervals, no unseen-region or station/gauge validation, and no joint constraints guaranteeing minimum/mean/maximum temperature ordering. Raw regression outputs are not physically clipped.
