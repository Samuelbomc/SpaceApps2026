# Rolling-origin daily training

The canonical command is `python -m ml.scripts.train_rolling_origin`. It delegates to train_daily_models.py and consumes data/prepared/daily. Five models share information across lead_days 1-60. Temperature and rainfall predict absolute daily targets; moisture retains baseline-plus-change prediction.

## Chronological protocol

Eligible issue dates are derived from valid daily feature/label pairs. The last 20% of distinct issue dates form the holdout, shared across cells and leads. Development pairs require issue_date before the test period and target_date strictly before its first observation cutoff (first test issue minus two days). Unobserved future targets are never training labels.

Four expanding-window validation blocks begin at 40%, 55%, 70% and 85% of eligible development dates. Training targets must precede the validation observation cutoff. Validation targets must precede the next block's observation cutoff. These target-date conditions apply separately to every lead and prevent repeated target labels leaking across temporal partitions.

Three depth/minimum-child-weight/L2 candidates are (2,10,20), (3,5,10) and (4,10,20). All use squared-error regression, MAE validation, eta 0.03, alpha 0.1, seed 42, histogram trees, max_bin 256, eight threads, at most 800 rounds and early stopping after 30 rounds. Weighted pooled validation MAE selects the candidate. The median best fold tree count determines the evaluation and final fits. Neither configuration nor tree count is selected on test scores.

Quantile matrices reduce training memory; all accepted pairs at all 60 leads are used. There is no row subsampling or lead subsampling. Label repetitions across leads do not increase independent observational information.

## Evaluation and deployment fits

Each output folder contains evaluation_model.json fitted on all eligible development pairs, model.json refitted on every observed pair, training.json with source hashes and fold metadata, test_predictions.npz and lead_metrics.csv. The default all-data model includes holdout labels and has no independent post-refit score.

Only production weights, metadata and small reports are committed. Evaluation boosters and holdout arrays remain local. An inference-only checkout can run `python -m ml.sample_forecasts --example`; full evaluation commands require the source datasets, pair indexes and local evaluation artifacts. The historical training run used XGBoost 3.4.1. Fold membership is reconstructed from saved source hashes and the issue/target date rules; training.json stores fold summaries rather than every fold row.

`python -m ml.scripts.validate_rolling_origin` verifies source identity, pair membership, purging, selection, every saved holdout prediction, per-lead scores and current inputs for all 60 leads. `python -m ml.scripts.summarize_rolling_origin` produces the model index and [current results](seven-day-results.md).

Daily persistence uses the latest daily temperature or rainfall feature; moisture persistence uses its recent observed mean. Scores apply to individual days, not period aggregates.

Pooled holdout MAE is lower than persistence for all five outputs. Checking by lead changes the picture: moisture is worse at leads 1-3. Rainfall R2 is about 0.01. These are reported outcomes, not promotion guarantees; the local trainer does not automatically reject a model for a weak individual lead or publish it into the separate application registry.

The current best candidate/depth/tree counts are mean temperature 1/3/196, minimum temperature 2/4/163, maximum temperature 1/3/263, precipitation 0/2/109, and moisture 2/4/84. Candidate IDs are zero-based. Exact parameters and scores are saved in each output's training.json.

## Limitations

Historical holdouts have been inspected during development; they are not prospective confirmation. Spatial dependence, repeated labels across leads, noisy SMAP retrievals, differing LST/UTC day intervals and unverified publication times remain. See [daily-datasets.md](daily-datasets.md) and [model-results.md](seven-day-results.md). Local training does not publish into the API registry.
