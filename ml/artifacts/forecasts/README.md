# Current daily forecast models

The five output folders are temperature_mean, temperature_min, temperature_max, precipitation and moisture. Each model supports integer lead_days 1-60; a lead predicts only its individual target day. models.json indexes the defaults. See [usage](../../README.md), [verified results](../../docs/model-results.md) and [lead definitions](../../docs/horizon-results.md).

## Artifact contents

| File | Purpose | Git |
|---|---|---|
| `<output>/model.json` | Default all-data refit | Included |
| `<output>/training.json` | Input contract, baseline, source hashes and fold metadata | Included |
| `<output>/lead_metrics.csv` | Individual-day holdout metrics for all 60 leads | Included |
| models.json, metrics.csv, lead_metrics.csv, summary.json, validation.json | Index, pooled/per-lead scores and validation record | Included |
| `<output>/evaluation_model.json` | Pre-test fit used for reported scores | Local only |
| `<output>/test_predictions.npz` | Saved holdout pairs and predictions | Local only |
| current_predictions.csv | Full prediction export from local inputs | Local only |

The evaluation score does not independently measure the all-data refit, which includes holdout labels. Moisture's raw booster predicts a correction; ForecastPredictor reconstructs absolute moisture. These local artifacts are separate from the application model registry.

## Run the bundled snapshot

From the repository root: python -m ml.sample_forecasts --example. The committed input snapshot in ml/examples is issued November 15, 2026 and defaults to seven individual days. Use --days 14 or --leads 1 7 15 30 60. It does not refresh observations.

The report command regenerates this README from the validated local collection.

## Previous iterations

The old 7/15/30/60-day aggregate model directories have been replaced; their scores are not directly comparable with daily targets.
