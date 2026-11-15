# Daily moisture forecast

The model name remains moisture. A single lead-conditioned XGBoost predicts the difference between target_date's mean accepted SMAP retrieval and the recent observed baseline, smap_mean_7d. The default loader adds the baseline to return absolute m3/m3. Target days with no observed retrieval are omitted; missing labels are never interpolated.

```python
import pandas as pd
from ml.inference.forecast import ForecastPredictor
frame = pd.read_csv("ml/examples/inputs/moisture.csv")
absolute_moisture = ForecastPredictor("moisture").predict(frame)
```

Current artifacts are ml/artifacts/forecasts/moisture/. model.json is the all-data refit; evaluation_model.json is the pre-test model used for reported scores. Both raw boosters return changes. The directory-based MoistureChangePredictor helper accepts the same complete feature frames.

The example above works from a fresh checkout. For all 175 locally prepared cells, use `data/prepared/daily/moisture/inference.csv`. Evaluation-only model files and full datasets stay local; they are unnecessary for default production inference. The tracked training.json lists all 75 required predictors and the baseline field. Quality counts from future target dates are not predictors.

A lead is a number of days after issue_date. The example contains all leads 1-60; filter `frame.lead_days <= 7` to predict the next seven individual days. The bundled issue date is November 15, 2026, and its SMAP point differs from the climate example point. Fresh dates require fresh source features, not a relabelled old row.

The relaxed source recipe retains attempted, finite 0.02-0.50 retrievals including non-recommended quality, records missing uncertainty and allows input observations up to fourteen days older than the t-2 cutoff, with explicit age/count features. This can mean sixteen days before the issue date. Past non-recommended counts are predictors; future retrieval quality counts remain label audit metadata.

There are 175 current inference cells and 266,283 observed daily labels. Most retained retrievals are non-recommended, so label noise and bias are substantial concerns. Older regridded TIFFs are sampled at native cell centres; newer files are native NetCDF. This does not create new spatial information. Shared meteorology and repeated labels across leads reduce effective independence.

Training uses the same purged four-fold rolling-origin selection as the other daily outputs. Selection/evaluation metrics use reconstructed absolute moisture. See [model-results.md](model-results.md), [daily-datasets.md](daily-datasets.md) and [rolling-origin-results.md](rolling-origin-results.md).

The current model uses depth 4 and 84 trees. Pooled daily holdout MAE is 0.04584 m3/m3 versus persistence at 0.04982, but leads 1-3 perform worse than persistence. Raw predictions have no clipping or calibrated uncertainty intervals; using retained non-recommended retrievals increases sample coverage without establishing field-level accuracy.

## Previous iterations

The former absolute-moisture and multi-day mean-moisture models have been replaced. Their binary artifacts are not current models.
