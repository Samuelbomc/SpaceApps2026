# Current model results

The default models use rolling-origin selection at 7, 15, 30 and 60 days. Canonical names are temperature_mean, temperature_min, temperature_max, precipitation and moisture. All 20 variants are stored under ml/artifacts/forecasts/<horizon>d/<model_name>/ and indexed in models.json. All validation checks passed.

## Test metrics

Scores apply to evaluation_model.json, which is fitted only on eligible pre-test rows. model.json is refitted on every prepared row and has no independent post-refit score. Lower MAE/RMSE are preferred; bias is prediction minus target. Temperature units are C, rainfall mm per complete forecast period, and moisture m3/m3.

| Horizon | Model | Test rows | MAE | Persistence MAE | RMSE | Bias | R2 |
|---|---|---:|---:|---:|---:|---:|---:|
| 7d | moisture | 792 | 0.03311 | 0.03763 | 0.04295 | -0.00921 | -0.37141 |
| 7d | precipitation | 9612 | 36.91130 | 46.31019 | 50.75572 | -6.10814 | 0.08412 |
| 7d | temperature_max | 9621 | 0.90807 | 1.00731 | 1.19851 | -0.00283 | 0.88213 |
| 7d | temperature_mean | 9621 | 0.56377 | 0.63865 | 0.74728 | -0.07729 | 0.94487 |
| 7d | temperature_min | 9621 | 0.44555 | 0.52017 | 0.56915 | -0.20356 | 0.96624 |
| 15d | moisture | 810 | 0.03117 | 0.03706 | 0.04031 | -0.00431 | -0.42113 |
| 15d | precipitation | 9594 | 62.72646 | 89.23447 | 83.47521 | -12.83214 | 0.13222 |
| 15d | temperature_max | 9621 | 0.82081 | 0.97030 | 1.09515 | 0.01119 | 0.89885 |
| 15d | temperature_mean | 9621 | 0.50635 | 0.61528 | 0.68048 | -0.09377 | 0.95367 |
| 15d | temperature_min | 9621 | 0.38851 | 0.48724 | 0.49455 | -0.21847 | 0.97426 |
| 30d | moisture | 828 | 0.02822 | 0.03519 | 0.03494 | 0.00041 | 0.27995 |
| 30d | precipitation | 9567 | 100.31199 | 172.66210 | 132.96157 | -27.97578 | 0.20387 |
| 30d | temperature_max | 9621 | 0.76660 | 0.97171 | 1.03898 | 0.02941 | 0.90714 |
| 30d | temperature_mean | 9621 | 0.46545 | 0.59741 | 0.63932 | -0.09762 | 0.95870 |
| 30d | temperature_min | 9621 | 0.33361 | 0.46510 | 0.42563 | -0.20585 | 0.98081 |
| 60d | moisture | 828 | 0.02952 | 0.03477 | 0.03686 | 0.00912 | 0.23401 |
| 60d | precipitation | 9513 | 171.73938 | 338.78133 | 222.64094 | -67.70821 | 0.20301 |
| 60d | temperature_max | 9621 | 0.79105 | 1.08206 | 1.05262 | 0.09734 | 0.90105 |
| 60d | temperature_mean | 9621 | 0.48302 | 0.63114 | 0.66411 | -0.10243 | 0.95478 |
| 60d | temperature_min | 9621 | 0.37054 | 0.47708 | 0.45824 | -0.30126 | 0.97761 |

## Development cross-validation

Each model uses four expanding-window validation folds and three candidate configurations. The table reports the selected candidate's pooled validation MAE; fold wins are against persistence. These folds select settings, so their scores are not independent test evidence.

| Horizon | Model | CV MAE | CV persistence MAE | Folds beating persistence | Selected rounds |
|---|---|---:|---:|---:|---:|
| 7d | moisture | 0.03193 | 0.03625 | 4/4 | 114 |
| 7d | precipitation | 32.03227 | 41.98890 | 4/4 | 166 |
| 7d | temperature_max | 0.88860 | 0.95345 | 3/4 | 163 |
| 7d | temperature_mean | 0.52955 | 0.58782 | 4/4 | 265 |
| 7d | temperature_min | 0.40946 | 0.50388 | 4/4 | 192 |
| 15d | moisture | 0.03312 | 0.03728 | 3/4 | 53 |
| 15d | precipitation | 52.81350 | 81.34795 | 4/4 | 195 |
| 15d | temperature_max | 0.80409 | 0.94381 | 4/4 | 199 |
| 15d | temperature_mean | 0.48456 | 0.57673 | 4/4 | 224 |
| 15d | temperature_min | 0.34455 | 0.47550 | 4/4 | 223 |
| 30d | moisture | 0.03403 | 0.04015 | 3/4 | 67 |
| 30d | precipitation | 83.59361 | 158.95307 | 4/4 | 218 |
| 30d | temperature_max | 0.73062 | 0.95866 | 4/4 | 214 |
| 30d | temperature_mean | 0.43069 | 0.56548 | 4/4 | 178 |
| 30d | temperature_min | 0.29173 | 0.45294 | 4/4 | 451 |
| 60d | moisture | 0.02932 | 0.03501 | 3/4 | 20 |
| 60d | precipitation | 138.52182 | 319.51389 | 4/4 | 140 |
| 60d | temperature_max | 0.72951 | 0.99332 | 4/4 | 197 |
| 60d | temperature_mean | 0.42212 | 0.55685 | 4/4 | 260 |
| 60d | temperature_min | 0.26321 | 0.46176 | 4/4 | 193 |

## Non-overlapping target windows

The same evaluation models are scored every H days to reduce overlap; spatial dependence remains. The long-horizon moisture subsets contain very few issue dates.

| Horizon | Model | Rows | MAE | Persistence MAE |
|---|---|---:|---:|---:|
| 7d | moisture | 114 | 0.03719 | 0.03940 |
| 7d | precipitation | 1377 | 36.69010 | 45.47589 |
| 7d | temperature_max | 1377 | 0.89138 | 1.00801 |
| 7d | temperature_mean | 1377 | 0.55156 | 0.63557 |
| 7d | temperature_min | 1377 | 0.44000 | 0.50274 |
| 15d | moisture | 66 | 0.04110 | 0.04704 |
| 15d | precipitation | 648 | 64.01289 | 88.65604 |
| 15d | temperature_max | 648 | 0.85403 | 0.98105 |
| 15d | temperature_mean | 648 | 0.51979 | 0.61788 |
| 15d | temperature_min | 648 | 0.38583 | 0.48726 |
| 30d | moisture | 36 | 0.01426 | 0.01990 |
| 30d | precipitation | 324 | 101.41772 | 178.95345 |
| 30d | temperature_max | 324 | 0.77247 | 1.03260 |
| 30d | temperature_mean | 324 | 0.46419 | 0.65675 |
| 30d | temperature_min | 324 | 0.35131 | 0.53117 |
| 60d | moisture | 18 | 0.01525 | 0.02431 |
| 60d | precipitation | 162 | 177.96045 | 302.86222 |
| 60d | temperature_max | 162 | 0.78804 | 1.33616 |
| 60d | temperature_mean | 162 | 0.47087 | 0.81610 |
| 60d | temperature_min | 162 | 0.37892 | 0.59892 |

## Interpretation and limitations

All current variants beat persistence on these historical test rows. This does not establish reliable field forecasting. Rainfall error remains substantial and its explained variance is limited. Temperature pooled R2 includes differences between locations. Moisture has sparse, quality-selected and incompletely observed labels with missing uncertainty. Longer aggregates smooth variability; scores across horizons have different target meanings. Forecasts aggregate t+1..t+H, not the state on day H.

Daily target windows overlap and neighbouring cells share information. No unseen-region, station/gauge or prospective field evaluation is provided. Source publication-time availability remains unverified. Historical test periods have already informed development, so results are exploratory rather than independent confirmation. Further selection based on these test scores would overstate progress. Full-refit artifacts include test rows; their performance must not be represented by evaluation-model metrics.

See rolling-origin-results.md for the current training pipeline, horizon-results.md for forecast semantics, and moisture-model.md for moisture inference. Reproduce the results using the commands in ml/README.md.
