"""Index current daily models and generate their verified evaluation report."""

import argparse
import json
from pathlib import Path

import pandas as pd

from ml.configs.forecasting import ARTIFACT_ROOT, UNITS
from ml.inference.forecast import ForecastPredictor
from ml.scripts.train_daily_models import BASELINES, DATA_ROOT, digest


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, default=ARTIFACT_ROOT)
    args = parser.parse_args()
    root = args.root
    validation = json.loads((root / "validation.json").read_text())
    assert len(validation) == 5 and all(c["status"] == "PASS" for c in validation.values())
    index, rows, lead_tables, current_predictions = {}, [], [], []
    for name in BASELINES:
        meta = json.loads((root / name / "training.json").read_text())
        for relative, sha in meta["source_sha256"].items():
            assert digest(DATA_ROOT / name / relative) == sha, (
                "Prepared data changed after training"
            )
        index[name] = {
            "model_name": name,
            "directory": name,
            "model": "model.json",
            "evaluation_model": "evaluation_model.json",
            "forecast_type": "direct_daily",
            "supported_leads": list(range(1, 61)),
            "units": UNITS[name],
            "prediction_mode": meta["prediction_mode"],
        }
        rows.append(
            {
                "model": name,
                "units": UNITS[name],
                "cv_mae": meta["candidates"][meta["selected_candidate"]]["cv_mae"],
                "test_rows": meta["test_rows"],
                **meta["test_metrics"]["model"],
                "persistence_mae": meta["test_metrics"]["persistence"]["mae"],
                "rounds": meta["selected_rounds"],
                "test_first_issue": meta["test_first_issue"],
                "test_last_issue": meta["test_last_issue"],
                "last_training_target": meta["last_training_target"],
            }
        )
        lead_tables.append(pd.read_csv(root / name / "lead_metrics.csv").assign(model=name))
        inputs = pd.read_csv(DATA_ROOT / name / "inference.csv")
        current = inputs[
            ["point_id", "longitude", "latitude", "issue_date", "target_date", "lead_days"]
        ].copy()
        current["model"], current["units"] = name, UNITS[name]
        current["prediction"] = ForecastPredictor(name, artifact_root=root).predict(inputs)
        current_predictions.append(current)
    table = pd.DataFrame(rows)
    table.to_csv(root / "metrics.csv", index=False)
    lead_table = pd.concat(lead_tables, ignore_index=True)
    lead_table.to_csv(root / "lead_metrics.csv", index=False)
    pd.concat(current_predictions, ignore_index=True).to_csv(
        root / "current_predictions.csv", index=False
    )
    (root / "models.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    (root / "summary.json").write_text(
        json.dumps(
            {
                "forecast_type": "direct_daily",
                "training_pipeline": "rolling_origin",
                "models": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    lines = [
        "# Current daily model results",
        "",
        "Five output-named XGBoost models predict individual future days at leads 1-60. All saved holdout predictions, source hashes, temporal splits and current inference rows passed validation. The canonical collection is ml/artifacts/forecasts/<output>/.",
        "",
        "## Pooled daily holdout metrics",
        "",
        "Scores below evaluate evaluation_model.json, fitted on eligible pre-test pairs. The default model.json refits all observed pairs, including test labels, and has no independent post-refit score. Temperature units are C, rainfall mm/day, and moisture m3/m3. Lower MAE/RMSE are preferred; bias is prediction minus observation.",
        "",
        "| Output | Test pairs | MAE | Persistence MAE | RMSE | Bias | R2 | Rounds |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['model']} | {row['test_rows']:,} | {row['mae']:.5f} | {row['persistence_mae']:.5f} | {row['rmse']:.5f} | {row['bias']:.5f} | {row['r2']:.4f} | {row['rounds']} |"
        )
    lines += [
        "",
        "## Selected daily leads",
        "",
        "Each entry is model MAE / persistence MAE for that individual target day. Complete scores for all 60 leads are in ml/artifacts/forecasts/lead_metrics.csv.",
        "",
        "| Output | Day 1 | Day 7 | Day 15 | Day 30 | Day 60 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in BASELINES:
        selected = lead_table[lead_table.model == name].set_index("lead_days")
        scores = [
            f"{selected.loc[h, 'mae']:.5f} / {selected.loc[h, 'persistence_mae']:.5f}"
            for h in (1, 7, 15, 30, 60)
        ]
        lines.append("| " + name + " | " + " | ".join(scores) + " |")
    lines += [
        "",
        "## Training and dates",
        "",
        "Four expanding-window validation blocks start at 40%, 55%, 70% and 85% of pre-test issue dates. Three depth/minimum-child-weight/L2 configurations are compared: (2,10,20), (3,5,10), (4,10,20), with learning rate 0.03, L1 0.1, seed 42, histogram trees, max_bin 256, up to 800 rounds and 30-round early stopping. Pooled validation MAE selects configuration; median best fold rounds selects tree count. Dates are grouped across locations and leads. Training target dates must precede the next observation cutoff; validation targets are also purged before the next block. The final 20% of issue dates form the holdout.",
        "",
        "Daily persistence uses the last available daily temperature/rainfall input. Moisture retains the recent observed baseline plus a learned correction. Holdout metrics include all 60 leads; source labels recur at multiple leads, so pair counts are not independent sample counts.",
        "",
        "| Output | Test issue dates | Latest observed training target |",
        "|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['model']} | {row['test_first_issue']} to {row['test_last_issue']} | {row['last_training_target']} |"
        )
    lines += [
        "",
        "Current prepared inference inputs are issued November 15, 2026 and cover November 16, 2026 through January 14, 2027. Forecasting from a later date requires freshly prepared features with acceptable observation ages; the model can accept any valid issue date, not only the prepared example.",
        "",
        "## Limitations",
        "",
        "These are historical development holdouts, not prospective field validation. Nearby cells, shared meteorology and repeating labels across leads cause dependence; pooled temperature R2 includes spatial differences. Most accepted SMAP retrievals are non-recommended; sparse daily coverage, approximate static fills and missing uncertainty can bias moisture labels. Daily rainfall is harder than predicting smoothed multi-day totals, and beating persistence does not establish operational usefulness. A missing GPM file is excluded only on its target day, not filled into a label.",
        "",
        "POWER uses LST daily intervals and GPM/SMAP use UTC intervals. Weather/rain/SMAP use a two-day observation lag; radiation uses seven days. Causal bounded input filling and observation-age predictors handle gaps, but actual historical publication times are not certified. There are no calibrated prediction intervals, no unseen-region or station/gauge validation, and no joint constraints guaranteeing minimum/mean/maximum temperature ordering. Raw regression outputs are not physically clipped.",
        "",
        "## Previous iterations",
        "",
        "Short complete-case datasets, aggregate 7/15/30/60-day targets, single-split selection and earlier rolling-origin aggregate models preceded this daily design. Their old trained collections were replaced. Their scores are not directly comparable with individual-day target scores. Data preparation documentation retains the earlier recipe for context; only the direct-daily output-named binaries are current.",
    ]
    Path("ml/docs/model-results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "README.md").write_text(
        "# Current daily forecast models\n\nFive output-named models, each supporting lead_days 1-60. models.json indexes the defaults. model.json is the all-data refit; evaluation_model.json reproduces holdout scores. See ml/README.md and ml/docs/model-results.md. There are no multi-day aggregate output models in this collection.\n",
        encoding="utf-8",
    )
    print(table[["model", "mae", "persistence_mae", "rounds"]].to_string(index=False))


if __name__ == "__main__":
    main()
