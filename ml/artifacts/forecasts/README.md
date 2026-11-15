# Forecast models

Canonical rolling-origin-selected models are organized as `<horizon>d/<output>/`.
`models.json` indexes twenty models; `metrics.csv` and `summary.json` contain scores.
The moisture Booster predicts a change; ForecastPredictor reconstructs absolute
moisture once. Only `evaluation_model.json` has the reported pre-refit holdout scores.

See [ML entry point](../../README.md),
[rolling-origin protocol](../../../docs/reference/ml/rolling-origin-results.md),
[results](../../../docs/reference/ml/horizon-results.md) and
[input contract](../../../docs/reference/model-inference.md).
