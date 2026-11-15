"""Default loader for canonical rolling-origin forecast artifacts."""

import json
from pathlib import Path

from ml.configs.forecasting import ARTIFACT_ROOT, BASELINES, HORIZONS


class ForecastPredictor:
    def __init__(
        self, model_name, horizon_days=7, *, artifact_root=ARTIFACT_ROOT, evaluation=False
    ):
        import xgboost as xgb

        if model_name not in BASELINES or horizon_days not in HORIZONS:
            raise ValueError("Unknown model output or unsupported forecast horizon")
        directory = Path(artifact_root) / f"{horizon_days}d" / model_name
        self.config = json.loads((directory / "training.json").read_text())
        if (
            self.config["model_name"] != model_name
            or self.config["horizon_days"] != horizon_days
            or self.config["training_pipeline"] != "rolling_origin"
        ):
            raise ValueError(
                "Artifact metadata does not match the requested rolling-origin forecast"
            )
        if (
            self.config["prediction_mode"]
            != ("baseline_plus_change" if model_name == "moisture" else "absolute")
            or self.config["baseline_feature"] != BASELINES[model_name]
            or (model_name == "moisture" and self.config.get("baseline_scale") != 1)
            or len(set(self.config["features"])) != len(self.config["features"])
        ):
            raise ValueError("Artifact semantics or feature columns do not match the model")
        self.booster = xgb.Booster(params={"nthread": 1})
        self.booster.load_model(
            directory / ("evaluation_model.json" if evaluation else "model.json")
        )
        if self.booster.feature_names != self.config["features"]:
            raise ValueError("Model feature order differs from the metadata")

    def predict_row(self, features):
        import numpy as np
        import xgboost as xgb

        names = self.config["features"]
        if set(features) != set(names):
            raise ValueError("Forecast inputs must match the declared feature columns exactly")
        values = np.array([[float(features[name]) for name in names]])
        if not np.isfinite(values).all():
            raise ValueError("Forecast features must all be finite")
        value = float(self.booster.predict(xgb.DMatrix(values, feature_names=names))[0])
        if self.config["prediction_mode"] == "baseline_plus_change":
            value += features[self.config["baseline_feature"]]
        if not np.isfinite(value):
            raise ValueError("Forecast output must be finite")
        return value

    def predict(self, frame):
        import numpy as np
        import xgboost as xgb

        features = self.config["features"]
        values = frame[features].to_numpy(float)
        if not np.isfinite(values).all():
            raise ValueError("Forecast features must all be finite")
        prediction = self.booster.predict(xgb.DMatrix(values, feature_names=features))
        if self.config["prediction_mode"] == "baseline_plus_change":
            prediction = prediction + frame[self.config["baseline_feature"]].to_numpy(float)
        if not np.isfinite(prediction).all():
            raise ValueError("Forecast outputs must all be finite")
        return prediction
