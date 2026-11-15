"""Collect validated 15/30/60-day backtest scores and moisture label coverage."""

import json
from pathlib import Path

import pandas as pd


def main():
    root = Path("ml/artifacts/forecasts")
    summary = {
        "target_definition": "Aggregate observations over t+1 through t+H; not an endpoint forecast",
        "horizons": {},
    }
    for horizon in (15, 30, 60):
        folder = root / f"{horizon}d"
        report = json.loads((folder / "report.json").read_text())
        validation = json.loads(
            Path(f"data/prepared/horizons/{horizon}d/validation.json").read_text()
        )
        models = {}
        for name, metadata in report["models"].items():
            assert validation[name]["status"] == "PASS"
            assert metadata["horizon_days"] == horizon
            item = {
                key: metadata[key]
                for key in (
                    "rows",
                    "train_rows",
                    "validation_rows",
                    "test_rows",
                    "test_first_issue",
                    "test_last_issue",
                    "selected_rounds",
                    "prediction_mode",
                    "test_xgboost",
                    "test_persistence",
                    "test_training_mean",
                    "test_nonoverlapping_targets",
                )
            }
            item["mae_improvement_vs_persistence_percent"] = 100 * (
                1 - metadata["test_xgboost"]["mae"] / metadata["test_persistence"]["mae"]
            )
            if name == "moisture":
                data = pd.read_csv(metadata["source_file"])
                keys = pd.read_csv(folder / name / "test_predictions.csv")[
                    ["point_id", "issue_date"]
                ]
                test = data.merge(keys, on=["point_id", "issue_date"], validate="one_to_one")
                item["test_label_observed_days"] = {
                    "minimum": float(test.target_observed_days.min()),
                    "median": float(test.target_observed_days.median()),
                    "maximum": float(test.target_observed_days.max()),
                    "horizon": horizon,
                }
            models[name] = item
        summary["horizons"][str(horizon)] = models
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("PASS: summarized 15 validated model/horizon backtests")


if __name__ == "__main__":
    main()
