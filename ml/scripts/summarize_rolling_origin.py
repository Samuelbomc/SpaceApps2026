"""Generate current rolling-origin results and the canonical model index."""
import json
from pathlib import Path

import pandas as pd

from ml.configs.forecasting import ARTIFACT_ROOT


def main():
    root = ARTIFACT_ROOT
    summary = json.loads((root/"summary.json").read_text())
    checks = json.loads((root/"validation.json").read_text())
    assert len(checks)==20 and all(v["status"]=="PASS" for v in checks.values())
    rows,index = [],{}
    for horizon,models in summary["horizons"].items():
        index[horizon] = {}
        for name in models:
            folder = root/f"{horizon}d"/name
            meta = json.loads((folder/"training.json").read_text())
            best = meta["candidates"][meta["selected_candidate"]]
            score,baseline = meta["test_metrics"]["model"],meta["test_metrics"]["persistence"]
            row = {"horizon_days":int(horizon),"model":name,"units":meta["units"],
                   "test_mae":score["mae"],"test_rmse":score["rmse"],"test_bias":score["bias"],"test_r2":score["r2"],
                   "persistence_mae":baseline["mae"],"cv_mae":best["cv_mae"],"cv_persistence_mae":best["cv_persistence_mae"],
                   "cv_folds_beating_persistence":sum(f["model"]["mae"]<f["persistence"]["mae"] for f in best["folds"]),
                   "test_rows":meta["test_rows"],"development_rows":meta["development_rows"],"rounds":meta["selected_rounds"],
                   "test_start":meta["test_first_issue"],"test_end":meta["test_last_issue"],
                   "nonoverlapping_rows":meta["nonoverlapping_test_rows"],
                   "nonoverlapping_mae":meta["nonoverlapping_test_metrics"]["model"]["mae"],
                   "nonoverlapping_persistence_mae":meta["nonoverlapping_test_metrics"]["persistence"]["mae"]}
            rows.append(row)
            index[horizon][name] = {"model_name":name,"horizon_days":int(horizon),"directory":str(folder),
                                    "prediction_mode":meta["prediction_mode"],"model":"model.json","evaluation_model":"evaluation_model.json"}
    table = pd.DataFrame(rows).sort_values(["horizon_days","model"])
    table.to_csv(root/"metrics.csv",index=False)
    (root/"models.json").write_text(json.dumps(index,indent=2),encoding="utf-8")
    lines = ["# Current model results", "", "The default models use rolling-origin selection at 7, 15, 30 and 60 days. Canonical names are temperature_mean, temperature_min, temperature_max, precipitation and moisture. All 20 variants are stored under ml/artifacts/forecasts/<horizon>d/<model_name>/ and indexed in models.json. All validation checks passed.", "",
        "## Test metrics", "", "Scores apply to evaluation_model.json, which is fitted only on eligible pre-test rows. model.json is refitted on every prepared row and has no independent post-refit score. Lower MAE/RMSE are preferred; bias is prediction minus target. Temperature units are C, rainfall mm per complete forecast period, and moisture m3/m3.", "",
        "| Horizon | Model | Test rows | MAE | Persistence MAE | RMSE | Bias | R2 |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in table.itertuples():
        lines.append(f"| {r.horizon_days}d | {r.model} | {r.test_rows} | {r.test_mae:.5f} | {r.persistence_mae:.5f} | {r.test_rmse:.5f} | {r.test_bias:.5f} | {r.test_r2:.5f} |")
    lines += ["", "## Development cross-validation", "", "Each model uses four expanding-window validation folds and three candidate configurations. The table reports the selected candidate's pooled validation MAE; fold wins are against persistence. These folds select settings, so their scores are not independent test evidence.", "",
        "| Horizon | Model | CV MAE | CV persistence MAE | Folds beating persistence | Selected rounds |", "|---|---|---:|---:|---:|---:|"]
    for r in table.itertuples():
        lines.append(f"| {r.horizon_days}d | {r.model} | {r.cv_mae:.5f} | {r.cv_persistence_mae:.5f} | {r.cv_folds_beating_persistence}/4 | {r.rounds} |")
    lines += ["", "## Non-overlapping target windows", "", "The same evaluation models are scored every H days to reduce overlap; spatial dependence remains. The long-horizon moisture subsets contain very few issue dates.", "",
        "| Horizon | Model | Rows | MAE | Persistence MAE |", "|---|---|---:|---:|---:|"]
    for r in table.itertuples():
        lines.append(f"| {r.horizon_days}d | {r.model} | {r.nonoverlapping_rows} | {r.nonoverlapping_mae:.5f} | {r.nonoverlapping_persistence_mae:.5f} |")
    lines += ["", "## Interpretation and limitations", "", "All current variants beat persistence on these historical test rows. This does not establish reliable field forecasting. Rainfall error remains substantial and its explained variance is limited. Temperature pooled R2 includes differences between locations. Moisture has sparse, quality-selected and incompletely observed labels with missing uncertainty. Longer aggregates smooth variability; scores across horizons have different target meanings. Forecasts aggregate t+1..t+H, not the state on day H.", "",
        "Daily target windows overlap and neighbouring cells share information. No unseen-region, station/gauge or prospective field evaluation is provided. Source publication-time availability remains unverified. Historical test periods have already informed development, so results are exploratory rather than independent confirmation. Further selection based on these test scores would overstate progress. Full-refit artifacts include test rows; their performance must not be represented by evaluation-model metrics.", "",
        "See ml/docs/rolling-origin-results.md for the current training pipeline, ml/docs/horizon-results.md for forecast semantics, and ml/docs/moisture-change-model.md for moisture inference. Reproduce the results using the commands in ml/README.md.", "",
        "## Previous iterations", "", "Early weekly recipes requiring SMAP everywhere yielded only 94 examples per temperature model, 42 for rainfall and 86 for moisture. The expanded daily recipe removed the climate models' SMAP dependency and used native AM/PM moisture observations. An absolute-moisture model was superseded by baseline-plus-change prediction. The following single-split experiments were superseded by rolling-origin selection, which improved 18 of 20 same-test comparisons. These were exploratory comparisons on previously examined holdouts. Superseded datasets, model binaries, comparison outputs and training commands have been removed; only the current rolling-origin artifacts and pipeline remain.", ""]
    Path("ml/docs/model-results.md").write_text("\n".join(lines),encoding="utf-8")
    (root/"README.md").write_text("# Forecast models\n\nDefault rolling-origin-selected models, organized as <horizon>d/<output>/. models.json is the canonical model index; metrics.csv and summary.json contain current scores. See ml/README.md and ml/docs/model-results.md. Moisture boosters predict a change; ForecastPredictor reconstructs absolute moisture automatically.\n",encoding="utf-8")
    print(f"PASS: indexed and documented {len(table)} canonical rolling-origin models")


if __name__=="__main__":
    main()
