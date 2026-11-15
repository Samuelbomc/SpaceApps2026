# Bundled model inputs

This small public-source snapshot contains one location per output and all 60 leads, issued November 15, 2026. The five CSVs contain finite input features and dates, not training labels. Climate and moisture examples use different native grid locations; their coordinates are explicit in each CSV.

Run from the repository root:

```powershell
python -m pip install '.[ml]'
python -m ml.sample_forecasts --example
```

Without --example the sample command uses local data/prepared/daily inference inputs when present, otherwise this snapshot. It does not turn these historical observations into current-day data. Prepare new inputs from recent sources to issue a new forecast.

The default display covers every lead from 1 through 7: November 16-22 for this snapshot. A lead is the number of days after the November 15 issue date. Use `--example --days 14` for every day through November 29, or `--example --leads 1 7 15 30 60` for those five individual target dates. Add `--format json` for structured output.

Each output has only one bundled location, so use the default `--sample-index 0`. Other sample indexes require the larger local inference files. Climate examples use the same POWER point; moisture uses a different native SMAP cell. The command reports their coordinates and the input source explicitly.

The CSV columns match the current models' ordered feature contracts in `ml/artifacts/forecasts/<output>/training.json`: 53 predictors for climate and 75 for moisture. `manifest.json` records the preparation recipe, issue date, paths and point IDs. These are input rows, not measured future outcomes. Nearby leads may produce identical values from the tree models; prediction intervals are not provided.

Full training tables, raw satellite files, evaluation-only boosters and holdout arrays are excluded from Git. They are not needed for production model inference.

See [usage](../README.md), [daily target and lead definitions](../docs/horizon-results.md), and [verified scores and limitations](../docs/model-results.md).
