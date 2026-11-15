"""Train a residual correction to persistence using frozen expanded-data splits."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from ml.inference.moisture_change import MoistureChangePredictor
from ml.scripts.train_prepared_models import metrics


def main():
    previous = Path("ml/artifacts/environmental_conditions/moisture")
    output = Path("ml/artifacts/soil_moisture")
    output.mkdir(parents=True, exist_ok=True)
    spec = json.loads((previous / "training.json").read_text())
    source = Path(spec["source_file"])
    if hashlib.sha256(source.read_bytes()).hexdigest() != spec["source_sha256"]:
        raise ValueError("Prepared source changed; frozen comparison would be invalid")
    frame = pd.read_csv(source).sort_values(["issue_date", "point_id"]).reset_index(drop=True)
    partitions = pd.read_csv(previous / "partitions.csv")
    frame = frame.merge(
        partitions[["point_id", "issue_date", "partition"]],
        on=["point_id", "issue_date"],
        validate="one_to_one",
    )
    features, target, baseline = spec["features"], spec["target"], "smap_mean_7d"
    assert np.isfinite(frame[features + [target]].to_numpy(float)).all()
    train, validation, test = (
        frame[frame.partition == label].copy() for label in ("train", "validation", "test")
    )
    for left, right in ((train, validation), (validation, test)):
        assert (
            pd.to_datetime(left.target_end).max() < pd.to_datetime(right.observation_cutoff).min()
        )

    def matrix(part):
        # The learned target is next-week moisture minus the recent-week mean.
        return xgb.DMatrix(
            part[features].to_numpy(float),
            label=(part[target] - part[baseline]).to_numpy(float),
            feature_names=features,
        )

    original_report = json.loads((previous.parent / "report.json").read_text())
    params = dict(original_report["parameters"])
    history = {}
    model = xgb.train(
        params,
        matrix(train),
        num_boost_round=800,
        evals=[(matrix(train), "train_change"), (matrix(validation), "validation_change")],
        early_stopping_rounds=30,
        evals_result=history,
        verbose_eval=False,
    )
    rounds = model.best_iteration + 1
    model = model[:rounds]
    model.save_model(output / "evaluation_model.json")
    # Keep all previous features, source records, split dates and parameters.
    # Only the learned target changes; no blend or test-based search is added.
    absolute = xgb.Booster()
    absolute.load_model(previous / "evaluation_model.json")
    stats = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "features": features,
        "target": target,
        "baseline_feature": baseline,
        "formula": "predicted_weekly_moisture = smap_mean_7d + predicted_change",
        "learned_target": "target - smap_mean_7d",
        "units": "m3/m3",
        "source_file": str(source),
        "source_sha256": spec["source_sha256"],
        "parameters": params,
        "xgboost_version": xgb.__version__,
        "selected_rounds": rounds,
        "split_source": str(previous / "partitions.csv"),
        "partitions": {},
        "limitations": [
            "Existing holdout was previously inspected and motivated this experiment; comparison is exploratory, not independent confirmation.",
            "Daily targets overlap, spatial cells are correlated, and SMAP coverage is sparse.",
            "Moisture targets average variable numbers of valid days; uncertainty is often missing.",
            "Final refit includes all rows; test metrics apply only to evaluation_model.json.",
            "model.json predicts a CHANGE, not absolute moisture. Use MoistureChangePredictor to add the baseline.",
            "No post-prediction clipping or validation-selected blend was applied.",
        ],
    }
    for label, part in (("train", train), ("validation", validation), ("test", test)):
        dm = matrix(part)
        recent = part[baseline].to_numpy(float)
        actual = part[target].to_numpy(float)
        change = model.predict(dm)
        predicted = recent + change
        old = absolute.predict(dm)
        stats["partitions"][label] = {
            "rows": len(part),
            "first_issue": part.issue_date.min(),
            "last_issue": part.issue_date.max(),
            "change_model": metrics(actual, predicted),
            "absolute_model": metrics(actual, old),
            "persistence": metrics(actual, recent),
        }
        records = part[
            ["point_id", "issue_date", "observation_cutoff", "target_start", "target_end", target]
        ].copy()
        records["baseline"] = recent
        records["predicted_change"] = change
        records["prediction"] = predicted
        records["previous_absolute_prediction"] = old
        records.to_csv(output / f"{label}_predictions.csv", index=False)
        if label == "test":
            previous_predictions = pd.read_csv(previous / "test_predictions.csv")
            aligned = records.merge(
                previous_predictions,
                on=["point_id", "issue_date"],
                suffixes=("_new", "_old"),
                validate="one_to_one",
            )
            assert len(aligned) == len(part)
            np.testing.assert_allclose(
                aligned.previous_absolute_prediction, aligned.prediction_old, rtol=1e-6
            )
            nonoverlap = (
                (pd.to_datetime(part.issue_date) - pd.to_datetime(part.issue_date).min()).dt.days
                % 7
                == 0
            ).to_numpy()
            stats["test_nonoverlapping_targets"] = {
                "rows": int(nonoverlap.sum()),
                "change_model": metrics(actual[nonoverlap], predicted[nonoverlap]),
                "absolute_model": metrics(actual[nonoverlap], old[nonoverlap]),
                "persistence": metrics(actual[nonoverlap], recent[nonoverlap]),
            }
    final = xgb.train(params, matrix(frame), num_boost_round=rounds)
    final.save_model(output / "model.json")
    (output / "training.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    (output / "learning_curves.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    # Verify the actual saved inference contract reconstructs absolute moisture.
    loaded = MoistureChangePredictor(output, evaluation=True)
    np.testing.assert_allclose(
        loaded.predict(test),
        test[baseline].to_numpy(float) + model.predict(matrix(test)),
        rtol=1e-6,
    )
    loaded_final = MoistureChangePredictor(output)
    np.testing.assert_allclose(
        loaded_final.predict(frame),
        frame[baseline].to_numpy(float) + final.predict(matrix(frame)),
        rtol=1e-6,
    )
    print(
        json.dumps(
            {
                "selected_rounds": rounds,
                "partitions": stats["partitions"],
                "test_nonoverlapping_targets": stats["test_nonoverlapping_targets"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
