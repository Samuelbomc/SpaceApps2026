"""Train direct daily XGBoost forecasts with purged rolling-origin selection."""
import argparse
import gc
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from ml.evaluation.metrics import metrics
from ml.configs.forecasting import BASELINES,ARTIFACT_ROOT,UNITS
from ml.datasets.calendar import target_calendar


DATA_ROOT = Path("data/prepared/daily")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(4*1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def load_design(name,spec,root=DATA_ROOT):
    folder = root/name
    f,labels = pd.read_csv(folder/"features.csv"),pd.read_csv(folder/"labels.csv")
    pairs=[]
    for lead in range(1,61):
        with np.load(folder/"pairs"/f"lead_{lead:02d}.npz") as p:
            pairs.append((p["feature_id"],p["label_id"],lead))
    n=sum(len(p[0]) for p in pairs)
    X=np.empty((n,len(spec["features"])),dtype=np.float32)
    fi=np.empty(n,dtype=np.int32);li=fi.copy();leads=np.empty(n,dtype=np.int8)
    base=f[spec["base_features"]].to_numpy(dtype=np.float32)
    dates=pd.to_datetime(labels.target_date)
    calendar=np.column_stack(list(target_calendar(dates).values())).astype(np.float32)
    start=0
    for ids,lids,lead in pairs:
        stop=start+len(ids)
        X[start:stop,:base.shape[1]]=base[ids]
        X[start:stop,base.shape[1]]=lead
        X[start:stop,base.shape[1]+1:]=calendar[lids]
        fi[start:stop],li[start:stop],leads[start:stop]=ids,lids,lead
        start=stop
    y=labels.target.to_numpy(np.float32)[li]
    baseline=f[BASELINES[name]].to_numpy(np.float32)[fi]
    issue=f.issue_date.to_numpy(dtype="datetime64[D]").astype(np.int32)[fi]
    target=labels.target_date.to_numpy(dtype="datetime64[D]").astype(np.int32)[li]
    return X,y,baseline,issue,target,fi,li,leads


def day(value):
    return str(np.datetime64(int(value),'D'))


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument("--output",type=Path,default=ARTIFACT_ROOT)
    parser.add_argument("--models",nargs="+",choices=list(BASELINES),default=list(BASELINES))
    args=parser.parse_args()
    manifest=json.loads((DATA_ROOT/"manifest.json").read_text())
    validation=json.loads((DATA_ROOT/"validation.json").read_text())
    assert validation["status"]=="PASS"
    args.output.mkdir(parents=True,exist_ok=True)
    fixed={"objective":"reg:squarederror","eval_metric":"mae","tree_method":"hist","eta":.03,"alpha":.1,"seed":42,"nthread":8,"max_bin":256}
    choices=[dict(max_depth=2,min_child_weight=10,reg_lambda=20),dict(max_depth=3,min_child_weight=5,reg_lambda=10),dict(max_depth=4,min_child_weight=10,reg_lambda=20)]
    for name in args.models:
        folder=args.output/name;folder.mkdir(exist_ok=True)
        spec=manifest["models"][name]
        print(f"Loading {name}",flush=True)
        X,y,baseline,issue,target,fi,li,leads=load_design(name,spec)
        residual=name=="moisture"
        response=y-baseline if residual else y
        dates=np.unique(issue)
        first_test=dates[int(.8*len(dates))]
        dev=(issue<first_test)&(target<first_test-2)
        test=issue>=first_test
        dev_dates=np.unique(issue[dev])
        boundaries=[dev_dates[int(q*len(dev_dates))] for q in (.4,.55,.7,.85)]+[first_test]
        candidates=[{"candidate":i,"parameters":{**fixed,**config},"folds":[]} for i,config in enumerate(choices)]
        for fold,(start,end) in enumerate(zip(boundaries,boundaries[1:]),1):
            train=dev&(issue<start)&(target<start-2)
            val=dev&(issue>=start)&(issue<end)&(target<end-2)
            assert train.any() and val.any() and target[train].max()<issue[val].min()-2
            print(f"{name} fold {fold}: {train.sum()} train / {val.sum()} validation",flush=True)
            dtrain=xgb.QuantileDMatrix(X[train],label=response[train],feature_names=spec["features"],nthread=8,max_bin=256)
            dval=xgb.QuantileDMatrix(X[val],label=response[val],feature_names=spec["features"],nthread=8,max_bin=256,ref=dtrain)
            for c in candidates:
                model=xgb.train(c["parameters"],dtrain,num_boost_round=800,evals=[(dval,"validation")],early_stopping_rounds=30,verbose_eval=False)
                rounds=model.best_iteration+1
                prediction=model.predict(dval,iteration_range=(0,rounds))+(baseline[val] if residual else 0)
                score=metrics(y[val],prediction)
                c["folds"].append({"fold":fold,"train_rows":int(train.sum()),"validation_rows":int(val.sum()),"train_last_issue":day(issue[train].max()),"train_last_target":day(target[train].max()),"validation_first_issue":day(issue[val].min()),"validation_first_cutoff":day(issue[val].min()-2),"validation_last_issue":day(issue[val].max()),"validation_last_target":day(target[val].max()),"next_partition_cutoff":day(end-2),"rounds":rounds,"model":score,"persistence":metrics(y[val],baseline[val])})
                print(f"{name} fold {fold} candidate {c['candidate']}: MAE={score['mae']:.5f}, rounds={rounds}",flush=True)
                del model
            del dtrain,dval;gc.collect()
        for c in candidates:
            c["cv_mae"]=float(np.average([f["model"]["mae"] for f in c["folds"]],weights=[f["validation_rows"] for f in c["folds"]]))
            c["selected_rounds"]=int(np.median([f["rounds"] for f in c["folds"]]))
        best=min(candidates,key=lambda c:c["cv_mae"])
        print(f"{name}: selected candidate {best['candidate']}, {best['selected_rounds']} rounds; fitting evaluation",flush=True)
        dtrain=xgb.QuantileDMatrix(X[dev],label=response[dev],feature_names=spec["features"],nthread=8,max_bin=256)
        model=xgb.train(best["parameters"],dtrain,num_boost_round=best["selected_rounds"])
        model.save_model(folder/"evaluation_model.json")
        prediction=model.inplace_predict(X[test])+(baseline[test] if residual else 0)
        scores={"model":metrics(y[test],prediction),"persistence":metrics(y[test],baseline[test])}
        np.savez_compressed(folder/"test_predictions.npz",feature_id=fi[test],label_id=li[test],lead_days=leads[test],target=y[test],prediction=prediction,persistence=baseline[test])
        lead_scores=[]
        for lead in range(1,61):
            mask=leads[test]==lead
            lead_scores.append({"lead_days":lead,"test_rows":int(mask.sum()),**metrics(y[test][mask],prediction[mask]),"persistence_mae":metrics(y[test][mask],baseline[test][mask])["mae"]})
        pd.DataFrame(lead_scores).to_csv(folder/"lead_metrics.csv",index=False)
        del model,dtrain;gc.collect()
        print(f"{name}: test MAE {scores['model']['mae']:.5f}; persistence {scores['persistence']['mae']:.5f}; refitting all {len(y)} pairs",flush=True)
        full=xgb.QuantileDMatrix(X,label=response,feature_names=spec["features"],nthread=8,max_bin=256)
        model=xgb.train(best["parameters"],full,num_boost_round=best["selected_rounds"])
        model.save_model(folder/"model.json")
        reloaded=xgb.Booster();reloaded.load_model(folder/"model.json")
        np.testing.assert_allclose(reloaded.inplace_predict(X[-100:]),model.inplace_predict(X[-100:]))
        source_folder=DATA_ROOT/name
        hashes={p.name if p.parent==source_folder else "pairs/"+p.name:digest(p) for p in [source_folder/"features.csv",source_folder/"labels.csv",*sorted((source_folder/"pairs").glob("*.npz"))]}
        metadata={"model_name":name,"training_pipeline":"rolling_origin","forecast_type":"direct_daily","preparation_recipe_version":manifest["recipe_version"],"supported_leads":list(range(1,61)),"features":spec["features"],"target":"target","prediction_mode":"baseline_plus_change" if residual else "absolute","baseline_feature":BASELINES[name],"source_directory":str(source_folder),"source_sha256":hashes,"created_at_utc":datetime.now(timezone.utc).isoformat(),"total_training_pairs":len(y),"development_rows":int(dev.sum()),"test_rows":int(test.sum()),"purged_rows":int((~dev&~test).sum()),"test_first_issue":day(first_test),"test_last_issue":day(issue[test].max()),"development_last_target":day(target[dev].max()),"last_training_target":day(target.max()),"selected_candidate":best["candidate"],"selected_rounds":best["selected_rounds"],"parameters":best["parameters"],"candidates":candidates,"test_metrics":scores,"artifact_note":"Evaluation uses eligible pre-test pairs. model.json refits all pairs, including test labels, and has no independent post-refit score."}
        metadata["units"]=UNITS[name]
        (folder/"training.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
        print(f"COMPLETE {name}",flush=True)
        del X,y,baseline,issue,target,fi,li,leads,response,full,model,reloaded,prediction;gc.collect()


if __name__=="__main__":
    main()
