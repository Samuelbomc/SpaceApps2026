"""Train experimental XGBoost regressors using available prepared datasets."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb


BASELINES = {"temperature_mean":"t2m_mean_7d", "temperature_min":"t2m_min_mean_7d",
             "temperature_max":"t2m_max_mean_7d", "precipitation":"gpm_late_sum_7d_mm",
             "moisture":"smap_mean_7d"}
UNITS = {"temperature_mean":"C", "temperature_min":"C", "temperature_max":"C",
         "precipitation":"mm", "moisture":"m3/m3"}


def metrics(actual, prediction):
    error = prediction-actual
    denom = np.sum((actual-actual.mean())**2)
    return {"mae":float(np.abs(error).mean()), "rmse":float(np.sqrt((error**2).mean())),
            "bias":float(error.mean()), "r2":float(1-(error**2).sum()/denom) if denom>0 else None}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/prepared/expanded/manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("ml/artifacts/environmental_conditions"))
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--max-rounds", type=int, default=800)
    parser.add_argument("--residual-moisture", action="store_true", help="Predict moisture change from the preceding observed seven-day baseline")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    params = {"objective":"reg:squarederror", "eval_metric":"mae", "tree_method":"hist",
              "max_depth":args.max_depth, "min_child_weight":5, "eta":0.03, "lambda":10,
              "alpha":0.1, "seed":42, "nthread":2}
    report = {"created_at_utc":datetime.now(timezone.utc).isoformat(), "xgboost_version":xgb.__version__,
              "parameters":params, "split_policy":"Chronological approximately 60/20/20 by issue date; purge earlier targets reaching the next partition's observation cutoff", "models":{}}
    for name, spec in manifest.items():
        folder = args.output/name
        folder.mkdir(parents=True, exist_ok=True)
        source = Path(spec["path"])
        frame = pd.read_csv(source).sort_values(["issue_date","point_id"]).reset_index(drop=True)
        features, target = spec["features"], spec["target"]
        horizon = spec.get("horizon_days",7)
        residual = args.residual_moisture and name=="moisture"
        def baseline_values(part):
            factor = horizon/7 if name=="precipitation" else 1
            return part[BASELINES[name]].to_numpy(float)*factor
        assert np.isfinite(frame[features+[target]].to_numpy(float)).all()
        assert not frame.duplicated(["point_id","issue_date"]).any()
        dates = sorted(frame.issue_date.unique())
        validation_start, test_start = dates[int(len(dates)*0.6)], dates[int(len(dates)*0.8)]
        train = frame[(frame.issue_date<validation_start) & (pd.to_datetime(frame.target_end)<pd.Timestamp(validation_start)-pd.Timedelta(days=2))]
        validation = frame[(frame.issue_date>=validation_start) & (frame.issue_date<test_start) & (pd.to_datetime(frame.target_end)<pd.Timestamp(test_start)-pd.Timedelta(days=2))]
        test = frame[frame.issue_date>=test_start]
        if min(len(train),len(validation),len(test))<3:
            raise ValueError(f"Insufficient chronological partitions for {name}")
        def matrix(part):
            labels = part[target].to_numpy(float)
            if residual:
                labels = labels-baseline_values(part)
            return xgb.DMatrix(part[features].to_numpy(float),label=labels,feature_names=features)
        dtrain,dval,dtest = matrix(train),matrix(validation),matrix(test)
        history = {}
        evaluated = xgb.train(params,dtrain,num_boost_round=args.max_rounds,evals=[(dtrain,"train"),(dval,"validation")],early_stopping_rounds=30,evals_result=history,verbose_eval=False)
        rounds = evaluated.best_iteration+1
        # Save only the selected trees, rather than the stopping patience trees.
        evaluated = evaluated[:rounds]
        evaluated.save_model(folder/"evaluation_model.json")
        prediction = evaluated.predict(dtest)
        baseline = baseline_values(test)
        predicted_change = prediction.copy() if residual else None
        if residual:
            prediction = baseline+prediction
        actual = test[target].to_numpy(float)
        constant = np.full(len(test),train[target].mean())
        split_map = {}
        for label,part in (("train",train),("validation",validation),("test",test)):
            split_map.update({int(i):label for i in part.index})
        split_frame = frame[["point_id","issue_date","observation_cutoff","target_start","target_end"]].copy()
        split_frame["partition"] = [split_map.get(i,"purged") for i in frame.index]
        split_frame.to_csv(folder/"partitions.csv",index=False)
        predictions = test[["point_id","issue_date","target_start","target_end",target]].copy()
        predictions["prediction"] = prediction
        if residual:
            predictions["predicted_change"] = predicted_change
        predictions["persistence_baseline"] = baseline
        predictions["training_mean_baseline"] = constant
        predictions.to_csv(folder/"test_predictions.csv",index=False)
        # Final artifact uses all available data at a fixed round count selected
        # without test labels. Test scores belong ONLY to evaluation_model.json.
        final = xgb.train(params,matrix(frame),num_boost_round=rounds)
        final.save_model(folder/"model.json")
        reload = xgb.Booster()
        reload.load_model(folder/"model.json")
        np.testing.assert_allclose(reload.predict(matrix(frame)),final.predict(matrix(frame)),rtol=1e-6)
        stats = {"rows":len(frame),"train_rows":len(train),"validation_rows":len(validation),"test_rows":len(test),"purged_rows":len(frame)-len(split_map),
                 "features":features,"target":target,"units":UNITS[name],"selected_rounds":rounds,
                 "horizon_days":horizon,"prediction_mode":"baseline_plus_change" if residual else "absolute",
                 "baseline_feature":BASELINES[name],"baseline_scale":horizon/7 if name=="precipitation" else 1,
                 "constant_features_in_training":[f for f in features if train[f].nunique()<=1],
                 "test_xgboost":metrics(actual,prediction), "test_persistence":metrics(actual,baseline),
                 "test_training_mean":metrics(actual,constant),"source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
                 "source_file":str(source), "locations":int(frame.point_id.nunique()),
                 "first_issue":frame.issue_date.min(),"last_issue":frame.issue_date.max(),
                 "test_first_issue":test.issue_date.min(),"test_last_issue":test.issue_date.max(),
                 "artifact_note":"evaluation_model.json has held-out metrics; model.json is refitted on all rows and has no independent evaluation after refitting"}
        if args.manifest.parent.name == "expanded" or horizon!=7:
            # Secondary view: disjoint seven-day target windows, same frozen
            # evaluated model; no tuning or retraining on these test scores.
            selected = ((pd.to_datetime(test.issue_date)-pd.to_datetime(test.issue_date).min()).dt.days % horizon == 0).to_numpy()
            if selected.sum()>1:
                stats["test_nonoverlapping_targets"] = {"rows":int(selected.sum()),"xgboost":metrics(actual[selected],prediction[selected]),"persistence":metrics(actual[selected],baseline[selected])}
        (folder/"training.json").write_text(json.dumps(stats,indent=2),encoding="utf-8")
        (folder/"learning_curves.json").write_text(json.dumps(history,indent=2),encoding="utf-8")
        report["models"][name] = stats
        print(f"{name}: train={len(train)}, val={len(validation)}, test={len(test)}, rounds={rounds}; test MAE={stats['test_xgboost']['mae']:.5f}; persistence MAE={stats['test_persistence']['mae']:.5f}",flush=True)
    report["limitations"] = ["Training-set coverage is limited to this AOI; performance on unseen regions is untested. See per-model location/sample counts.",
        "Sparse, irregular SMAP-selected weeks introduce selection bias; these are not continuous weekly records.",
        "One chronological holdout has high statistical uncertainty; no claim of reliable forecast skill.",
        "Rainfall targets use Late Run; no independent gauge validation or Final Run labels.",
        "Moisture targets average valid retrievals, potentially only one observation in a week; uncertainty may be missing.",
        "Temperature min/max targets are means of daily extrema, not absolute weekly extrema.",
        "Source estimates and actual product publication delays are not independently validated.",
        "Some predictors are constant or shared across coarse source cells. See per-model constant feature lists; sample count does not equal independent information.",
        "Final refitted artifacts include holdout rows; reported holdout metrics apply only to evaluation artifacts.",
        "Experimental artifacts only; no production registry promotion or agronomic recommendation validation."]
    if args.manifest.parent.name == "expanded":
        report["limitations"][1] = "Daily seven-day targets overlap and nearby cells are correlated. Date-grouped partitioning and purging prevent cross-boundary label leakage, but effective sample size is lower than row count."
        report["limitations"].extend(["SMAP observations remain sparse and quality-selected, including variable AM/PM availability; missing targets are not interpolated.", "Moisture uses nearest downloaded POWER query values as coarse meteorological context, not parcel-scale weather."])
    if any(m["horizon_days"]!=7 for m in report["models"].values()):
        report["limitations"][1] = "Forecasts aggregate days t+1..t+H, not a point forecast on day H. Daily target windows overlap and spatial cells are correlated."
        report["limitations"][4] = "Moisture labels average available observations in the H-day window; they can have very low coverage and do not necessarily represent the whole window."
        report["limitations"][5] = "Temperature min/max labels average daily extrema over H days; they do not predict absolute H-day extrema."
        report["limitations"].extend(["Long-horizon variants are independently trained using only antecedent data, not recursively extending a seven-day forecast.","Rainfall persistence scales the preceding seven-day total by H/7; uncertainty intervals and independent spatial validation are absent."])
    (args.output/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")


if __name__ == "__main__":
    main()
