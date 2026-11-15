"""Check canonical rolling-origin splits, selection, labels and saved inference."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from ml.evaluation.metrics import metrics
from ml.configs.forecasting import ARTIFACT_ROOT


def main():
    root = ARTIFACT_ROOT
    summary = json.loads((root/"summary.json").read_text())
    checks = {}
    for horizon,models in summary["horizons"].items():
        for name in models:
            folder = root/f"{horizon}d"/name
            meta = json.loads((folder/"training.json").read_text())
            source = Path(meta["source_file"])
            assert hashlib.sha256(source.read_bytes()).hexdigest()==meta["source_sha256"]
            parts = pd.read_csv(folder/"cv_partitions.csv")
            prediction = pd.read_csv(folder/"test_predictions.csv")
            assert not prediction.duplicated(["point_id","issue_date"]).any()
            prepared = pd.read_csv(source)
            first_test = sorted(prepared.issue_date.unique())[int(prepared.issue_date.nunique()*0.8)]
            expected_test = prepared[prepared.issue_date>=first_test]
            pairs = prediction.merge(expected_test,on=["point_id","issue_date"],validate="one_to_one",suffixes=("_saved","_source"))
            assert len(pairs)==len(expected_test)==meta["test_rows"]
            np.testing.assert_allclose(pairs[meta["target"]+"_saved"],pairs[meta["target"]+"_source"])
            assert meta["model_name"]==name and meta["training_pipeline"]=="rolling_origin"
            assert np.isfinite(prediction[[meta["target"],"prediction","persistence"]]).all().all()
            cutoff = pd.to_datetime(prediction.observation_cutoff).min()
            for _,fold in parts.groupby("fold"):
                training = fold[fold.partition=="train"]
                validation = fold[fold.partition=="validation"]
                assert pd.to_datetime(training.target_end).max()<pd.to_datetime(validation.observation_cutoff).min()
                assert pd.to_datetime(validation.target_end).max()<cutoff
                assert not set(training.issue_date)&set(validation.issue_date)
                assert not set(fold.issue_date)&set(prediction.issue_date)
            assert parts.fold.nunique()==4
            for candidate in meta["candidates"]:
                cv = pd.read_csv(folder/f"cv_predictions_candidate_{candidate['candidate']}.csv")
                np.testing.assert_allclose(abs(cv.prediction-cv[meta["target"]]).mean(),candidate["cv_mae"])
                assert not cv.duplicated(["point_id","issue_date"]).any()
            best = min(meta["candidates"],key=lambda c:c["cv_mae"])
            assert best["candidate"]==meta["selected_candidate"]
            assert int(np.median([f["rounds"] for f in best["folds"]]))==meta["selected_rounds"]
            for label,column in (("model","prediction"),("persistence","persistence")):
                recomputed = metrics(prediction[meta["target"]].to_numpy(float),prediction[column].to_numpy(float))
                for key,value in recomputed.items():
                    if value is not None:
                        np.testing.assert_allclose(value,meta["test_metrics"][label][key],rtol=1e-6,atol=1e-7)
            data = pd.read_csv(source).merge(prediction[["point_id","issue_date"]],on=["point_id","issue_date"],validate="one_to_one")
            model = xgb.Booster();model.load_model(folder/"evaluation_model.json")
            pred = model.predict(xgb.DMatrix(data[meta["features"]].to_numpy(float),feature_names=meta["features"]))
            if meta["prediction_mode"]=="baseline_plus_change":
                pred = pred+data[meta["baseline_feature"]].to_numpy(float)
            aligned = data[["point_id","issue_date"]].assign(reproduced=pred).merge(prediction,on=["point_id","issue_date"],validate="one_to_one")
            np.testing.assert_allclose(aligned.reproduced,aligned.prediction,rtol=1e-6,atol=1e-7)
            checks[f"{horizon}d/{name}"] = {"status":"PASS","folds":4,"test_labels_verified_from_source":True,"no_test_labels_in_cv":True,"purging_verified":True,"selection_verified":True,"metrics_and_saved_inference_verified":True}
            print(f"PASS {horizon}d {name}",flush=True)
    assert len(checks)==20, "Expected all 20 model/horizon combinations"
    (root/"validation.json").write_text(json.dumps(checks,indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
