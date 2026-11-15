"""Run one sample prediction through each canonical forecast model.

Run from the repository root with:
    python -m ml.sample_forecasts

The script takes a real feature row from each model's prepared source dataset,
then uses ForecastPredictor so moisture predictions include their observed
baseline reconstruction.
"""

import argparse
import csv
import json
import math
from pathlib import Path

from ml.configs.forecasting import HORIZONS, UNITS, source_path
from ml.inference.forecast import ForecastPredictor

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_ROOT = REPO_ROOT / "ml" / "artifacts" / "forecasts"


def sample_for_model(horizon_days: int, model_name: str, sample_index: int):
    model_dir = ARTIFACT_ROOT / f"{horizon_days}d" / model_name
    metadata = json.loads((model_dir / "training.json").read_text(encoding="utf-8"))
    source = REPO_ROOT / source_path(metadata["source_file"])
    if not source.is_file():
        raise FileNotFoundError(f"Prepared feature data not found: {source}")

    if sample_index < 0:
        raise IndexError("Sample index must be non-negative")
    selected = None
    valid_count = 0
    with source.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = set(metadata["features"]) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{source} is missing columns: {sorted(missing)}")
        for row in reader:
            try:
                features = {key: float(row[key]) for key in metadata["features"]}
            except (ValueError, TypeError):
                continue
            if not all(math.isfinite(value) for value in features.values()):
                continue
            if valid_count == sample_index:
                selected = row, features
                break
            valid_count += 1
    if selected is None:
        raise IndexError(
            f"Sample index {sample_index} is outside the {valid_count} valid rows for {horizon_days}d/{model_name}"
        )
    row, features = selected
    predictor = ForecastPredictor(
        model_name, horizon_days=horizon_days, artifact_root=ARTIFACT_ROOT
    )
    prediction = predictor.predict_row(features)
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
        "--sample-index",
        type=int,
        default=0,
        help="zero-based row among complete prepared feature rows (default: 0)",
    )
    args = parser.parse_args()

    results = [
        sample_for_model(horizon, model, args.sample_index)
        for horizon in HORIZONS
        for model in (
            "temperature_mean",
            "temperature_min",
            "temperature_max",
            "precipitation",
            "moisture",
        )
    ]
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
