# Rolling-origin training pipeline

Rolling-origin validation is the default for every output at 7, 15, 30 and 60 days. Run `python -m ml.scripts.train_rolling_origin` from the repository root after preparing the datasets.

## Splits and selection

The last 20% of distinct issue dates form the chronological test period, shared across locations. Development rows must precede the first test date and their target end must precede that date minus the two-day observation lag. Splits are derived directly from prepared data.

Four expanding-window folds use validation blocks beginning at 40%, 55%, 70% and 85% of eligible development dates. Each training partition is purged so its targets precede the validation observation cutoff. Three configurations are evaluated: depth/minimum child weight/L2 of (2,10,20), (3,5,10), and (4,10,20). All use learning rate 0.03, L1 0.1, seed 42, two threads, up to 800 rounds and 30-round early stopping.

The lowest pooled validation MAE selects the configuration. The median best round count across its four folds determines the final tree count. This produces 240 fold fits, 20 evaluation fits on development data and 20 deployment fits on all prepared data. No test labels select configuration or rounds.

## Artifacts and validation

Canonical artifacts are `ml/artifacts/forecasts/<horizon>d/<model_name>/`. Output names are temperature_mean, temperature_min, temperature_max, precipitation and moisture. Each directory contains the all-data `model.json`, pre-test `evaluation_model.json`, metadata, fold results and test predictions.

Run `python -m ml.scripts.validate_rolling_origin`, then `python -m ml.scripts.summarize_rolling_origin`. Validation checks source identity, temporal purging, candidate selection, test membership, metrics and reloaded predictions. The summary writes the current model index and results. See [seven-day-results.md](seven-day-results.md).

Moisture predicts a change from recent observed moisture; the loader adds that baseline. Other outputs predict absolute aggregates. Persistence is the recent seven-day observed value (rainfall scaled to the forecast duration).

## Limitations

Overlapping targets and shared source grids create correlated rows. Validation does not test unseen regions. The historical test period has already been inspected during development, so future independent data are needed for a fresh assessment. The all-data refit has no independent score. This workflow saves local forecast artifacts; application registry publication remains a separate lifecycle step.
