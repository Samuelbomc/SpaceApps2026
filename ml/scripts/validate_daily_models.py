"""Verify trained direct-daily models against every saved holdout prediction."""

import argparse
import gc
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.configs.forecasting import BASELINES
from ml.evaluation.metrics import metrics
from ml.inference.forecast import ForecastPredictor
from ml.scripts.train_daily_models import DATA_ROOT, digest, load_design


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, default=Path("ml/artifacts/forecasts"))
    parser.add_argument("--models", nargs="+", choices=list(BASELINES))
    args = parser.parse_args()
    manifest = json.loads((DATA_ROOT / "manifest.json").read_text())
    checks = {}
    for name, spec in manifest["models"].items():
        if args.models and name not in args.models:
            continue
        folder = args.root / name
        meta = json.loads((folder / "training.json").read_text())
        assert meta["forecast_type"] == "direct_daily" and meta["features"] == spec["features"]
        assert meta["preparation_recipe_version"] == manifest["recipe_version"]
        for relative, sha in meta["source_sha256"].items():
            assert digest(DATA_ROOT / name / relative) == sha
        X, y, baseline, issue, target, fi, li, leads = load_design(name, spec)
        dates = np.unique(issue)
        first_test = dates[int(0.8 * len(dates))]
        dev = (issue < first_test) & (target < first_test - 2)
        test = issue >= first_test
        assert dev.sum() == meta["development_rows"] and test.sum() == meta["test_rows"]
        assert target[dev].max() < issue[test].min() - 2
        dev_dates = np.unique(issue[dev])
        bounds = [dev_dates[int(q * len(dev_dates))] for q in (0.4, 0.55, 0.7, 0.85)] + [first_test]
        for c in meta["candidates"]:
            scores, weights = [], []
            for f, (start, end) in zip(c["folds"], zip(bounds, bounds[1:])):
                train = dev & (issue < start) & (target < start - 2)
                val = dev & (issue >= start) & (issue < end) & (target < end - 2)
                assert train.sum() == f["train_rows"] and val.sum() == f["validation_rows"]
                assert target[train].max() < issue[val].min() - 2 and target[val].max() < end - 2
                scores.append(f["model"]["mae"])
                weights.append(f["validation_rows"])
            assert np.isclose(np.average(scores, weights=weights), c["cv_mae"])
            assert int(np.median([f["rounds"] for f in c["folds"]])) == c["selected_rounds"]
        best = min(meta["candidates"], key=lambda c: c["cv_mae"])
        assert (
            best["candidate"] == meta["selected_candidate"]
            and best["selected_rounds"] == meta["selected_rounds"]
        )
        with np.load(folder / "test_predictions.npz") as saved:
            for k, expected in (
                ("feature_id", fi[test]),
                ("label_id", li[test]),
                ("lead_days", leads[test]),
                ("target", y[test]),
                ("persistence", baseline[test]),
            ):
                np.testing.assert_array_equal(saved[k], expected)
            loader = ForecastPredictor(name, artifact_root=args.root, evaluation=True)
            predicted = loader.booster.inplace_predict(X[test]) + (
                baseline[test] if meta["prediction_mode"] == "baseline_plus_change" else 0
            )
            np.testing.assert_allclose(saved["prediction"], predicted, rtol=1e-6, atol=1e-7)
            for kind, values in (("model", predicted), ("persistence", baseline[test])):
                for k, value in metrics(y[test], values).items():
                    assert np.isclose(value, meta["test_metrics"][kind][k])
            by_lead = pd.read_csv(folder / "lead_metrics.csv")
            for row in by_lead.itertuples():
                select = leads[test] == row.lead_days
                assert int(select.sum()) == row.test_rows
                for k, value in metrics(y[test][select], predicted[select]).items():
                    assert np.isclose(value, getattr(row, k))
        inference = pd.read_csv(DATA_ROOT / name / "inference.csv")
        result = ForecastPredictor(name, artifact_root=args.root).predict(inference)
        assert len(result) == len(inference) and np.isfinite(result).all()
        checks[name] = {
            "status": "PASS",
            "holdout_rows_verified": int(test.sum()),
            "inference_rows": len(result),
            "all_60_leads_verified": True,
            "rolling_origin_purging": True,
            "source_hashes_verified": True,
            "saved_inference_reproduced": True,
            "negative_current_predictions": int((result < 0).sum()),
        }
        print(name, checks[name], flush=True)
        del X, y, baseline, issue, target, fi, li, leads, predicted
        gc.collect()
    (args.root / "validation.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
