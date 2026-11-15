"""Default forecast training: rolling-origin selection and chronological test.

Run from repository root: python -m ml.scripts.train_rolling_origin
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from ml.configs.forecasting import ARTIFACT_ROOT, BASELINES, UNITS, HORIZONS
from ml.evaluation.metrics import metrics


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--horizons",type=int,nargs="+",default=list(HORIZONS))
    parser.add_argument("--output",type=Path,default=ARTIFACT_ROOT)
    args = parser.parse_args()
    fixed = {"objective":"reg:squarederror","eval_metric":"mae","tree_method":"hist",
             "eta":0.03,"alpha":0.1,"seed":42,"nthread":2}
    choices = [dict(max_depth=2,min_child_weight=10,reg_lambda=20),
               dict(max_depth=3,min_child_weight=5,reg_lambda=10),
               dict(max_depth=4,min_child_weight=10,reg_lambda=20)]
    summary = {"created_at_utc":datetime.now(timezone.utc).isoformat(),"xgboost_version":xgb.__version__,
               "protocol":"Four expanding-window folds in pre-test observations; dates grouped across cells; train and validation labels purged at subsequent observation cutoffs", "candidates":choices,"horizons":{}}
    for horizon in args.horizons:
        if horizon not in (7,15,30,60):
            raise ValueError("Supported horizons: 7,15,30,60")
        data_root = Path("data/prepared/expanded") if horizon==7 else Path(f"data/prepared/horizons/{horizon}d")
        manifest = json.loads((data_root/"manifest.json").read_text())
        summary["horizons"][str(horizon)] = {}
        for name,spec in manifest.items():
            folder = args.output/f"{horizon}d"/name
            folder.mkdir(parents=True,exist_ok=True)
            source = Path(spec["path"])
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            frame = pd.read_csv(source).sort_values(["issue_date","point_id"]).reset_index(drop=True)
            features,target = spec["features"],spec["target"]
            residual = name=="moisture"
            assert np.isfinite(frame[features+[target]].to_numpy(float)).all()
            assert not frame.duplicated(["point_id","issue_date"]).any()
            issue_dates = sorted(frame.issue_date.unique())
            first_test = pd.Timestamp(issue_dates[int(len(issue_dates)*0.8)])
            test_cutoff = first_test-pd.Timedelta(days=2)
            dev = frame[(pd.to_datetime(frame.issue_date)<first_test)&(pd.to_datetime(frame.target_end)<test_cutoff)].copy()
            test = frame[pd.to_datetime(frame.issue_date)>=first_test].copy()
            assert pd.to_datetime(dev.target_end).max()<pd.to_datetime(test.observation_cutoff).min()
            def baseline(part):
                return part[BASELINES[name]].to_numpy(float)*(horizon/7 if name=="precipitation" else 1)
            def matrix(part):
                labels = part[target].to_numpy(float)-(baseline(part) if residual else 0)
                return xgb.DMatrix(part[features].to_numpy(float),label=labels,feature_names=features)
            def predict(model,part):
                return model.predict(matrix(part))+(baseline(part) if residual else 0)
            dates = sorted(dev.issue_date.unique())
            boundaries = [dates[int(len(dates)*q)] for q in (0.40,0.55,0.70,0.85)]
            boundaries.append(first_test.strftime("%Y-%m-%d"))
            folds = []
            partition_records = []
            for number,(start,end) in enumerate(zip(boundaries,boundaries[1:]),1):
                train = dev[(dev.issue_date<start)&(pd.to_datetime(dev.target_end)<pd.Timestamp(start)-pd.Timedelta(days=2))]
                validation = dev[(dev.issue_date>=start)&(dev.issue_date<end)&(pd.to_datetime(dev.target_end)<pd.Timestamp(end)-pd.Timedelta(days=2))]
                if min(len(train),len(validation))<10:
                    raise ValueError(f"Insufficient fold rows: {horizon}/{name}/{number}")
                assert pd.to_datetime(train.target_end).max()<pd.to_datetime(validation.observation_cutoff).min()
                assert pd.to_datetime(validation.target_end).max()<test_cutoff
                folds.append((train,validation))
                for split,part in (("train",train),("validation",validation)):
                    record = part[["point_id","issue_date","observation_cutoff","target_start","target_end"]].copy()
                    record["fold"],record["partition"] = number,split
                    partition_records.append(record)
            pd.concat(partition_records).to_csv(folder/"cv_partitions.csv",index=False)
            candidate_scores = []
            for candidate,config in enumerate(choices):
                params = {**fixed,**config}
                fold_scores, errors, persistence_errors, cv_records = [],[],[],[]
                for number,(train,validation) in enumerate(folds,1):
                    dtrain,dval = matrix(train),matrix(validation)
                    model = xgb.train(params,dtrain,num_boost_round=800,evals=[(dval,"validation")],early_stopping_rounds=30,verbose_eval=False)
                    rounds = model.best_iteration+1
                    model = model[:rounds]
                    prediction = predict(model,validation)
                    actual = validation[target].to_numpy(float)
                    errors.extend(np.abs(prediction-actual))
                    persistence_errors.extend(np.abs(baseline(validation)-actual))
                    fold_scores.append({"fold":number,"train_rows":len(train),"validation_rows":len(validation),
                        "train_first":train.issue_date.min(),"train_last":train.issue_date.max(),
                        "validation_first":validation.issue_date.min(),"validation_last":validation.issue_date.max(),
                        "rounds":rounds,"model":metrics(actual,prediction),"persistence":metrics(actual,baseline(validation))})
                    records = validation[["point_id","issue_date",target]].copy()
                    records["fold"],records["prediction"],records["persistence"] = number,prediction,baseline(validation)
                    cv_records.append(records)
                score = {"candidate":candidate,"parameters":params,"cv_mae":float(np.mean(errors)),
                         "cv_persistence_mae":float(np.mean(persistence_errors)),"folds":fold_scores,
                         "selected_rounds":int(np.median([f["rounds"] for f in fold_scores]))}
                candidate_scores.append(score)
                pd.concat(cv_records).to_csv(folder/f"cv_predictions_candidate_{candidate}.csv",index=False)
            best = min(candidate_scores,key=lambda c:c["cv_mae"])
            params,rounds = best["parameters"],best["selected_rounds"]
            # Fit all eligible pre-test rows after selecting solely on CV folds.
            evaluated = xgb.train(params,matrix(dev),num_boost_round=rounds)
            evaluated.save_model(folder/"evaluation_model.json")
            prediction = predict(evaluated,test)
            actual = test[target].to_numpy(float)
            records = test[["point_id","issue_date","observation_cutoff","target_start","target_end",target]].copy()
            records["prediction"],records["persistence"] = prediction,baseline(test)
            assert np.isfinite(records[[target,"prediction","persistence"]].to_numpy(float)).all()
            records.to_csv(folder/"test_predictions.csv",index=False)
            truth = records[target].to_numpy(float)
            test_scores = {"model":metrics(truth,records.prediction.to_numpy(float)),
                           "persistence":metrics(truth,records.persistence.to_numpy(float))}
            spaced = ((pd.to_datetime(records.issue_date)-pd.to_datetime(records.issue_date).min()).dt.days % horizon == 0).to_numpy()
            disjoint = {key:metrics(truth[spaced],records[column].to_numpy(float)[spaced]) for key,column in (("model","prediction"),("persistence","persistence"))}
            final = xgb.train(params,matrix(frame),num_boost_round=rounds)
            final.save_model(folder/"model.json")
            reloaded = xgb.Booster();reloaded.load_model(folder/"evaluation_model.json")
            np.testing.assert_allclose(predict(reloaded,test),prediction,rtol=1e-6)
            reloaded.load_model(folder/"model.json")
            np.testing.assert_allclose(predict(reloaded,frame),predict(final,frame),rtol=1e-6)
            metadata = {"features":features,"target":target,"baseline_feature":BASELINES[name],"horizon_days":horizon,
                        "prediction_mode":"baseline_plus_change" if residual else "absolute",
                        "baseline_scale":horizon/7 if name=="precipitation" else 1,
                        "source_file":str(source),"source_sha256":digest,"parameters":params,"selected_rounds":rounds,
                        "model_name":name,"training_pipeline":"rolling_origin","units":UNITS[name],"development_rows":len(dev),"test_rows":len(test),
                        "test_first_issue":test.issue_date.min(),"test_last_issue":test.issue_date.max(),
                        "selected_candidate":best["candidate"],"candidates":candidate_scores,
                        "test_metrics":test_scores,"nonoverlapping_test_rows":int(spaced.sum()),"nonoverlapping_test_metrics":disjoint,
                        "artifact_note":"Evaluation model uses only pre-test rows; full model refit uses all rows and has no independent post-refit test score."}
            (folder/"training.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
            development_partitions = dev[["point_id","issue_date","observation_cutoff","target_start","target_end"]].copy()
            development_partitions["partition"] = "development"
            test_partitions = test[development_partitions.columns.drop("partition")].copy();test_partitions["partition"] = "test"
            pd.concat([development_partitions,test_partitions]).to_csv(folder/"partitions.csv",index=False)
            summary["horizons"][str(horizon)][name] = {key:metadata[key] for key in ("model_name","horizon_days","prediction_mode","development_rows","test_rows","selected_candidate","selected_rounds","test_metrics","nonoverlapping_test_rows","nonoverlapping_test_metrics")}
            (args.output/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
            print(f"{horizon}d {name}: CV={best['cv_mae']:.5f}; test MAE {test_scores['model']['mae']:.5f}; persistence {test_scores['persistence']['mae']:.5f}",flush=True)


if __name__=="__main__":
    main()
