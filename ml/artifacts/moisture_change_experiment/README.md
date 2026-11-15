# Moisture-change experiment

See `ml/docs/moisture-change-model.md` for the model formula, results, limitations and inference usage. `training.json` contains the complete reproducible configuration and evaluation metrics.

The two model JSON files predict moisture CHANGE. Use `ml.inference.moisture_change.MoistureChangePredictor` to add the observed baseline and recover absolute weekly moisture. The evaluated artifact uses the original frozen holdout; the all-data refit has no independent test score.

Test MAE: correction model 0.035938 m3/m3; persistence 0.037633; previous absolute model 0.077293. The correction is better on this previously examined holdout, but the gain over persistence is modest and R2 remains negative. This artifact is experimental.
