"""Inference contract for a baseline plus XGBoost moisture-change artifact."""
import json
from pathlib import Path


class MoistureChangePredictor:
    def __init__(self, directory, *, evaluation=False):
        import xgboost as xgb
        directory = Path(directory)
        self.config = json.loads((directory / "training.json").read_text())
        self.booster = xgb.Booster()
        self.booster.load_model(directory / ("evaluation_model.json" if evaluation else "model.json"))

    def predict(self, frame):
        import numpy as np
        import xgboost as xgb
        features = self.config["features"]
        values = frame[features].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError("Moisture-change prediction requires finite feature values")
        baseline = frame[self.config["baseline_feature"]].to_numpy(dtype=float)
        change = self.booster.predict(xgb.DMatrix(values, feature_names=features))
        return baseline + change
