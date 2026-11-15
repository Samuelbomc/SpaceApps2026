# Dataset preparation history

The current training inputs are the direct-daily datasets documented in [daily-datasets.md](daily-datasets.md). The default rolling-origin command fits five daily models from data/prepared/daily; [model-results.md](model-results.md) records their verified scores.

For current model usage, start with [../README.md](../README.md) and the committed `ml/examples` snapshot. Full current and historical prepared datasets are excluded from Git and remain local. Current leads 1-60 select individual target days; the aggregate target meaning described below is historical.

## Previous iterations

Earlier preparations produced daily issue rows with targets aggregated over the following 7, 15, 30 or 60 days. Their data remain under data/prepared/expanded and data/prepared/horizons for development history, but their trained binaries have been replaced.

The first strict complete-case recipe yielded very few rows. Removing SMAP requirements from climate models restored most weather history; using native SMAP and retaining attempted non-recommended retrievals expanded moisture coverage to 175 cells. A POWER UTC radiation cutoff was resolved by using the downloaded LST collection with a seven-day radiation lag. Bounded causal input filling retained gaps while leaving targets observed.

The later aggregate recipe had approximately 48,000 rows per climate output and 407,000-415,000 moisture rows. Its November 10 inference examples and prior pending-training notes described that historical preparation only. Current daily inference examples are issued November 15 and predict individual days through January 14, 2027.

Missing daily targets now exclude only the selected target date's examples. In particular, the missing November 8 GPM file no longer removes November 9-12 labels merely because a multi-day target would cross the gap. No future label is filled or inferred.

The source-loading functions in prepare_expanded_datasets.py remain shared utilities for the daily pipeline. Its aggregate preparation/validation commands are historical tools and are not the default training workflow.
