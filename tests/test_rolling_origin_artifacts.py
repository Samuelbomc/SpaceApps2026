"""Pesos diarios y reportes incluidos; los holdouts completos se conservan localmente."""

import csv
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from ml.configs.forecasting import BASELINES, source_path
from ml.datasets.calendar import target_calendar
from ml.inference.forecast import ForecastPredictor

ROOT = Path(__file__).resolve().parents[1]


class RollingOriginArtifactTests(unittest.TestCase):
    def test_five_daily_boosters_match_direct_prediction_and_reconstruct_soil_once(self):
        for name in BASELINES:
            with self.subTest(output=name):
                frame = pd.read_csv(ROOT / f"ml/examples/inputs/{name}.csv")
                directory = ROOT / f"ml/artifacts/forecasts/{name}"
                config = json.loads((directory / "training.json").read_text())
                predictor = ForecastPredictor(name, artifact_root=ROOT / "ml/artifacts/forecasts")
                values = predictor.predict(frame)
                dates = pd.to_datetime(frame.issue_date) + pd.to_timedelta(
                    frame.lead_days, unit="D"
                )
                for key, column in target_calendar(dates).items():
                    frame[key] = column
                booster = xgb.Booster(params={"nthread": 1})
                booster.load_model(directory / "model.json")
                raw = booster.predict(
                    xgb.DMatrix(frame[config["features"]], feature_names=config["features"])
                )
                expected = (
                    raw + frame[BASELINES[name]].to_numpy(float) if name == "moisture" else raw
                )
                np.testing.assert_allclose(values, expected, rtol=1e-6, atol=1e-7)
                self.assertEqual(len(values), 60)
                self.assertTrue(np.isfinite(values).all())
                self.assertEqual(len(config["features"]), 75 if name == "moisture" else 53)
                with (directory / "lead_metrics.csv").open() as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(len(rows), 60)
                total = sum(int(row["test_rows"]) for row in rows)
                weighted = sum(float(row["mae"]) * int(row["test_rows"]) for row in rows) / total
                self.assertAlmostEqual(weighted, config["test_metrics"]["model"]["mae"], places=6)

    def test_windows_source_paths_are_portable_and_cannot_escape_the_repository(self):
        self.assertEqual(
            source_path(r"data\prepared\daily\moisture"), Path("data/prepared/daily/moisture")
        )
        for path in ("../private.csv", r"C:\private\data.csv", "/tmp/private.csv"):
            with self.assertRaises(ValueError):
                source_path(path)
