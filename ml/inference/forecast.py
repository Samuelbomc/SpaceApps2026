"""Default loader for direct daily rolling-origin forecast artifacts."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from ml.configs.forecasting import ARTIFACT_ROOT, BASELINES, HORIZONS
from ml.datasets.calendar import target_calendar


class ForecastPredictor:
    def __init__(self,model_name,horizon_days=7,*,artifact_root=ARTIFACT_ROOT,evaluation=False):
        if model_name not in BASELINES or horizon_days not in HORIZONS:
            raise ValueError("Unknown model output or unsupported lead: expected 1..60")
        directory = Path(artifact_root)/model_name
        self.config = json.loads((directory/"training.json").read_text())
        if self.config["model_name"]!=model_name or self.config["forecast_type"]!="direct_daily":
            raise ValueError("Artifact is not the requested direct-daily forecast")
        self.horizon_days = horizon_days
        self.booster = xgb.Booster()
        self.booster.load_model(directory/("evaluation_model.json" if evaluation else "model.json"))

    def predict(self,frame):
        frame = frame.copy()
        if "lead_days" not in frame:
            frame["lead_days"] = self.horizon_days
        leads = pd.to_numeric(frame.lead_days).to_numpy(float)
        if not (np.isfinite(leads).all() and ((leads>=1)&(leads<=60)&(leads==np.floor(leads))).all()):
            raise ValueError("lead_days must contain integers from 1 through 60")
        if "issue_date" in frame:
            dates = pd.to_datetime(frame.issue_date)+pd.to_timedelta(leads,unit="D")
            if "target_date" in frame and not (pd.to_datetime(frame.target_date).to_numpy()==dates.to_numpy()).all():
                raise ValueError("target_date must equal issue_date plus lead_days")
            for name,values in target_calendar(dates).items():
                frame[name] = values
        features = self.config["features"]
        values = frame[features].to_numpy(dtype=np.float32)
        if not np.isfinite(values).all():
            raise ValueError("Forecast features must all be finite")
        prediction = self.booster.inplace_predict(values)
        if self.config["prediction_mode"]=="baseline_plus_change":
            prediction = prediction+frame[self.config["baseline_feature"]].to_numpy(float)
        return prediction
