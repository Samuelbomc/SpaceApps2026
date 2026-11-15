# Horizon experiments

This directory contains independently trained 15-, 30- and 60-day variants of all five targets. Results and definitions are in `ml/docs/horizon-results.md`; `summary.json` consolidates validated report metrics and moisture-label coverage.

Each horizon folder has a `report.json` and five model subfolders. Each model has evaluation and all-data-refit JSON artifacts, ordered feature metadata, source hashes, partitions, curves and test predictions. For moisture, the booster output is a change; use `MoistureChangePredictor` to add the saved baseline. For climate models, booster outputs are absolute horizon aggregates. Scores apply only to evaluation artifacts.
