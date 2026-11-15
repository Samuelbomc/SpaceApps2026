"""Default loader for canonical rolling-origin forecast artifacts."""
import json
from pathlib import Path

import numpy as np
import xgboost as xgb

from ml.configs.forecasting import ARTIFACT_ROOT, BASELINES, HORIZONS


class ForecastPredictor:
    def __init__(self,model_name,horizon_days=7,*,artifact_root=ARTIFACT_ROOT,evaluation=False):
        if model_name not in BASELINES or horizon_days not in HORIZONS:
            raise ValueError("Unknown model output or unsupported forecast horizon")
        directory = Path(artifact_root)/f"{horizon_days}d"/model_name
        self.config = json.loads((directory/"training.json").read_text())
        if self.config["model_name"]!=model_name or self.config["horizon_days"]!=horizon_days or self.config["training_pipeline"]!="rolling_origin":
            raise ValueError("Artifact metadata does not match the requested rolling-origin forecast")
        self.booster = xgb.Booster()
        self.booster.load_model(directory/("evaluation_model.json" if evaluation else "model.json"))

    def predict(self,frame):
        features = self.config["features"]
        values = frame[features].to_numpy(float)
        if not np.isfinite(values).all():
            raise ValueError("Forecast features must all be finite")
        prediction = self.booster.predict(xgb.DMatrix(values,feature_names=features))
        if self.config["prediction_mode"]=="baseline_plus_change":
            prediction = prediction+frame[self.config["baseline_feature"]].to_numpy(float)
        return prediction
