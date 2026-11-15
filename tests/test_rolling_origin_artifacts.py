"""Golden checks contra predicciones guardadas del equipo, sin volver a entrenar."""

import csv
import importlib.util
import json
import unittest
from itertools import islice
from pathlib import Path

from ml.configs.forecasting import BASELINES, HORIZONS, source_path
from ml.inference.forecast import ForecastPredictor

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("xgboost"), "Requiere el extra ml")
class RollingOriginArtifactTests(unittest.TestCase):
    def test_all_twenty_evaluation_models_reproduce_saved_holdout_predictions(self):
        for horizon in HORIZONS:
            for name in BASELINES:
                with self.subTest(horizon=horizon, output=name):
                    directory = ROOT / "ml/artifacts/forecasts" / f"{horizon}d" / name
                    meta = json.loads((directory / "training.json").read_text())
                    with (directory / "test_predictions.csv").open(newline="") as handle:
                        expected = {
                            (r["point_id"], r["issue_date"]): float(r["prediction"])
                            for r in islice(csv.DictReader(handle), 2)
                        }
                    model = ForecastPredictor(
                        name,
                        horizon,
                        artifact_root=ROOT / "ml/artifacts/forecasts",
                        evaluation=True,
                    )
                    checked = set()
                    with (ROOT / source_path(meta["source_file"])).open(newline="") as handle:
                        for row in csv.DictReader(handle):
                            key = (row["point_id"], row["issue_date"])
                            if key in expected:
                                value = model.predict_row(
                                    {k: float(row[k]) for k in meta["features"]}
                                )
                                self.assertAlmostEqual(
                                    value, expected[key], delta=max(1e-7, abs(expected[key]) * 1e-6)
                                )
                                checked.add(key)
                                if checked == expected.keys():
                                    break
                    self.assertEqual(checked, expected.keys())

    def test_windows_source_paths_are_portable_and_cannot_escape_the_repository(self):
        self.assertEqual(
            source_path(r"data\prepared\expanded\moisture.csv"),
            Path("data/prepared/expanded/moisture.csv"),
        )
        for path in ("../private.csv", r"C:\private\data.csv", "/tmp/private.csv"):
            with self.assertRaises(ValueError):
                source_path(path)
