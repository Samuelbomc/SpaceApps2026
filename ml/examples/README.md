# Bundled model inputs

This small public-source snapshot contains one location per output and all 60 leads, issued November 15, 2026. The five CSVs contain finite input features and dates, not training labels. Climate and moisture examples use different native grid locations; their coordinates are explicit in each CSV.

Run from the repository root:

```powershell
python -m pip install '.[ml]'
python -m ml.sample_forecasts --example
```

Without --example the sample command uses local data/prepared/daily inference inputs when present, otherwise this snapshot. It does not turn these historical observations into current-day data. Prepare new inputs from recent sources to issue a new forecast.

Full training tables, raw satellite files, evaluation-only boosters and holdout arrays are excluded from Git. They are not needed for production model inference.
