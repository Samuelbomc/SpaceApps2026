"""Validate finite features, time windows, split purging and sampled raw labels."""
import json
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ml.scripts.dataset_sources import netcdf_samples
from ml.scripts.prepare_expanded_datasets import load_power, load_moisture


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--dataset-root",type=Path,default=Path("data/prepared/expanded"))
    parser.add_argument("--artifact-root",type=Path,default=Path("ml/artifacts/forecasts/7d"))
    args = parser.parse_args()
    root = args.dataset_root
    manifest = json.loads((root/"manifest.json").read_text())
    pp,powers,_ = load_power()
    sp,moisture,_,_,_ = load_moisture()
    checks = {}
    for name,spec in manifest.items():
        frame = pd.read_csv(spec["path"])
        horizon = spec.get("horizon_days",7)
        assert len(frame)==spec["rows"]
        assert np.isfinite(frame[spec["features"]+["target"]].to_numpy(float)).all()
        assert not frame.duplicated(["point_id","issue_date"]).any()
        issue,cutoff = pd.to_datetime(frame.issue_date),pd.to_datetime(frame.observation_cutoff)
        assert ((issue-cutoff).dt.days==2).all()
        assert ((pd.to_datetime(frame.target_start)-issue).dt.days==1).all()
        assert ((pd.to_datetime(frame.target_end)-issue).dt.days==horizon).all()
        if name=="moisture":
            assert frame.smap_age_days.between(0,6).all()
            assert frame.target_observed_days.between(1,horizon).all()
            assert (pd.to_datetime(frame.smap_latest_observation_date)<=cutoff).all()
        verified = 0
        for row in frame.iloc[[0,len(frame)//2,len(frame)-1]].itertuples():
            start,end = pd.Timestamp(row.target_start),pd.Timestamp(row.target_end)
            p = int(row.point_id.rsplit('_',1)[-1])
            if name.startswith("temperature"):
                column = {"temperature_mean":"T2M","temperature_min":"T2M_MIN","temperature_max":"T2M_MAX"}[name]
                expected = powers[p].loc[start:end,column].mean()
                input_mean = powers[p].loc[pd.Timestamp(row.observation_cutoff)-pd.Timedelta(days=6):row.observation_cutoff,"T2M"].mean()
                assert np.isclose(input_mean,row.t2m_mean_7d)
            elif name=="precipitation":
                observations = []
                for day in pd.date_range(start,end):
                    path = next(Path('data/GPM').rglob(f'*3IMERG.{day.strftime("%Y%m%d")}-*.nc4'))
                    observations.append(netcdf_samples(path,[pp[p]])[0])
                expected = np.sum(observations)
            else:
                s = moisture[p-len(pp)].loc[start:end]
                expected = s.mean()
                assert s.count()==row.target_observed_days
            assert np.isclose(expected,row.target), (name,expected,row.target)
            verified+=1
        folder = args.artifact_root/name
        metadata = json.loads((folder/"training.json").read_text())
        partitions = pd.read_csv(folder/"partitions.csv")
        left,right = partitions[partitions.partition=="development"],partitions[partitions.partition=="test"]
        assert len(left) and len(right)
        assert pd.to_datetime(left.target_end).max()<pd.to_datetime(right.observation_cutoff).min()
        folds = pd.read_csv(folder/"cv_partitions.csv")
        for _,fold in folds.groupby("fold"):
            left,right = fold[fold.partition=="train"],fold[fold.partition=="validation"]
            assert len(left) and len(right)
            assert pd.to_datetime(left.target_end).max()<pd.to_datetime(right.observation_cutoff).min()
        predictions = pd.read_csv(folder/"test_predictions.csv")
        assert np.isfinite(predictions.prediction).all()
        assert np.isclose(np.abs(predictions.prediction-predictions.target).mean(),metadata["test_metrics"]["model"]["mae"])
        import xgboost as xgb
        test = frame.merge(predictions[["point_id","issue_date"]],on=["point_id","issue_date"],validate="one_to_one")
        booster = xgb.Booster()
        booster.load_model(folder/"evaluation_model.json")
        reconstructed = booster.predict(xgb.DMatrix(test[spec["features"]].to_numpy(float),feature_names=spec["features"]))
        if metadata.get("prediction_mode")=="baseline_plus_change":
            reconstructed += test[metadata["baseline_feature"]].to_numpy(float)
        paired = test[["point_id","issue_date"]].assign(reconstructed=reconstructed).merge(predictions,on=["point_id","issue_date"],validate="one_to_one")
        np.testing.assert_allclose(paired.reconstructed,paired.prediction,rtol=1e-6,atol=1e-7)
        checks[name] = {"status":"PASS","horizon_days":horizon,"rows":len(frame),"raw_labels_recomputed":verified,"finite_values":True,"aligned_times":True,"purged_temporal_partitions":True,"saved_metrics_verified":True,"saved_inference_verified":True}
        print(name,checks[name],flush=True)
    (root/"validation.json").write_text(json.dumps(checks,indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
