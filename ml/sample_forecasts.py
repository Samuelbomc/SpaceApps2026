"""Run one sample prediction through each canonical forecast model.

Run from the repository root with:
    python -m ml.sample_forecasts

The script takes a real feature row from each model's prepared source dataset,
then uses ForecastPredictor so moisture predictions include their observed
baseline reconstruction.
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from ml.configs.forecasting import HORIZONS, UNITS
from ml.inference.forecast import ForecastPredictor


REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_ROOT = REPO_ROOT / "ml" / "artifacts" / "forecasts"


def sample_for_model(horizon_days: int, model_name: str, sample_index: int):
    model_dir = ARTIFACT_ROOT / f"{horizon_days}d" / model_name
    metadata = json.loads((model_dir / "training.json").read_text(encoding="utf-8"))
    source = REPO_ROOT / Path(metadata["source_file"])
    if not source.is_file():
        raise FileNotFoundError(f"Prepared feature data not found: {source}")

    frame = pd.read_csv(source)
    needed = list(metadata["features"])
    if metadata["prediction_mode"] == "baseline_plus_change":
        needed.append(metadata["baseline_feature"])
    missing = [column for column in needed if column not in frame.columns]
    if missing:
        raise ValueError(f"{source} is missing required columns: {', '.join(missing)}")

    # Skip incomplete rows, preserving their original row positions for reporting.
    valid = frame.dropna(subset=needed)
    if sample_index < 0 or sample_index >= len(valid):
        raise IndexError(
            f"Sample index {sample_index} is outside the {len(valid)} valid rows "
            f"for {horizon_days}d/{model_name}"
        )
    row = valid.iloc[sample_index]
    predictor = ForecastPredictor(
        model_name,
        horizon_days=horizon_days,
        artifact_root=ARTIFACT_ROOT,
    )
    prediction = float(predictor.predict(row.to_frame().T)[0])
    return {
        "horizon_days": horizon_days,
        "model": model_name,
        "point_id": row.get("point_id"),
        "issue_date": row.get("issue_date"),
        "prediction": prediction,
        "units": UNITS[model_name],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sample-index", type=int, default=0,
        help="zero-based row among complete prepared feature rows (default: 0)",
    )
    args = parser.parse_args()

    results = [
        sample_for_model(horizon, model, args.sample_index)
        for horizon in HORIZONS
        for model in ("temperature_mean", "temperature_min", "temperature_max", "precipitation", "moisture")
    ]
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
