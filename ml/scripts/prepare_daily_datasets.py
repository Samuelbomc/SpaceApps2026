"""Build daily labels and direct lead-1..60 datasets; never train a model."""
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.scripts import prepare_expanded_datasets as source
from ml.datasets.calendar import target_calendar


OUTPUTS = ("temperature_mean","temperature_min","temperature_max","precipitation","moisture")
RECIPE = "daily-direct-1-60-v1"


def features_for_point(power,rain,elevation):
    f = source.climate_features(power,rain,elevation)
    audit = f.attrs.pop("audit")
    for col in power:
        lag = 7 if col=="ALLSKY_SFC_SW_DWN" else 2
        f[col.lower()+"_last_daily"] = power[col].ffill(limit=7).shift(lag)
        dates = pd.Series(pd.NaT,index=source.INDEX,dtype="datetime64[ns]")
        dates.loc[power[col].notna()] = power.index[power[col].notna()]
        latest = dates.ffill(limit=7).shift(lag)
        f[col.lower()+"_age_days"] = ((pd.Series(source.INDEX,index=source.INDEX)-pd.Timedelta(days=lag))-latest).dt.days
    dates = pd.Series(pd.NaT,index=source.INDEX,dtype="datetime64[ns]")
    dates.loc[rain.notna()] = rain.index[rain.notna()]
    f["gpm_age_days"] = ((pd.Series(source.INDEX,index=source.INDEX)-pd.Timedelta(days=2))-dates.ffill(limit=3).shift(2)).dt.days
    for name in ("input_power_filled_values_30d","input_rain_filled_days_30d"):
        f[name] = audit[name]
    return f


def build(root,issue):
    source.discover_index(issue)
    pp,powers,power_files = source.load_power()
    sp,sm,sm_counts,sm_errors,sm_files = source.load_moisture()
    points = pp+sp
    rain,gpm_files = source.load_rain(points)
    terrain,static_files = source.static(points)
    feature_parts = {name:[] for name in OUTPUTS}
    label_parts = {name:[] for name in OUTPUTS}
    feature_names = {}

    def add(name,f,target,p,quality=None):
        f["static_imputed_fields"] = float(source.STATIC_IMPUTED[p])
        feature_names[name] = list(f.columns)
        valid = np.isfinite(f.to_numpy(float)).all(axis=1)
        frame = f.loc[valid].copy()
        frame.attrs = {}
        frame["point_id"] = f"power_{p}" if p<len(pp) else f"smap_{p-len(pp)}"
        frame["longitude"],frame["latitude"] = points[p]
        frame["issue_date"] = frame.index.strftime("%Y-%m-%d")
        frame["observation_cutoff"] = (frame.index-pd.Timedelta(days=2)).strftime("%Y-%m-%d")
        frame["radiation_observation_cutoff"] = (frame.index-pd.Timedelta(days=7)).strftime("%Y-%m-%d")
        feature_parts[name].append(frame)
        labels = pd.DataFrame({"target":target}).dropna()
        labels = labels[np.isfinite(labels.target)]
        labels["point_id"] = frame.point_id.iloc[0] if len(frame) else (f"power_{p}" if p<len(pp) else f"smap_{p-len(pp)}")
        labels["target_date"] = labels.index.strftime("%Y-%m-%d")
        if quality:
            for key,values in quality.items():
                labels[key] = values.reindex(labels.index)
        label_parts[name].append(labels)

    for i,power in enumerate(powers):
        f = features_for_point(power,rain[i],terrain["elevation_m"][i])
        for name,col in zip(OUTPUTS[:3],("T2M","T2M_MIN","T2M_MAX")):
            add(name,f.copy(),power[col],i)
        add("precipitation",f.copy(),rain[i],i)
    for j,point in enumerate(sp):
        p = len(pp)+j
        nearest = int(np.argmin(np.sum((np.array(pp)-point)**2,axis=1)))
        f = features_for_point(powers[nearest],rain[p],terrain["elevation_m"][p])
        s = sm[j]
        f["smap_mean_7d"] = s.rolling(7,min_periods=1).mean().shift(2).fillna(s.ffill(limit=14).shift(2))
        f["smap_last_valid_m3_m3"] = s.ffill(limit=14).shift(2)
        dates = pd.Series(pd.NaT,index=source.INDEX,dtype="datetime64[ns]")
        dates.loc[s.notna()] = s.index[s.notna()]
        f["smap_age_days"] = ((pd.Series(source.INDEX,index=source.INDEX)-pd.Timedelta(days=2))-dates.ffill(limit=14).shift(2)).dt.days
        f["smap_observed_days_7d"] = s.rolling(7,min_periods=1).count().shift(2)
        recommended = sm.attrs["recommended_counts"][j]
        f["smap_nonrecommended_retrievals_7d"] = (sm_counts[j]-recommended).rolling(7,min_periods=1).sum().shift(2)
        for key,values in terrain.items():
            f[key] = values[p]
        add("moisture",f,s,p,{"retrieval_count":sm_counts[j],"recommended_retrieval_count":recommended,"uncertainty_available_count":sm_errors[j]})

    manifest = {"recipe_version":RECIPE,"issue_date":str(issue.date()),"leads":list(range(1,61)),"models":{}}
    for name in OUTPUTS:
        folder = root/name
        (folder/"pairs").mkdir(parents=True,exist_ok=True)
        features = pd.concat(feature_parts[name],ignore_index=True).sort_values(["issue_date","point_id"]).reset_index(drop=True)
        labels = pd.concat(label_parts[name],ignore_index=True).sort_values(["target_date","point_id"]).reset_index(drop=True)
        features.insert(0,"feature_id",np.arange(len(features)))
        labels.insert(0,"label_id",np.arange(len(labels)))
        assert not features.duplicated(["point_id","issue_date"]).any()
        assert not labels.duplicated(["point_id","target_date"]).any()
        features.to_csv(folder/"features.csv",index=False)
        labels.to_csv(folder/"labels.csv",index=False)
        key = pd.MultiIndex.from_frame(features[["point_id","issue_date"]])
        label_dates = pd.to_datetime(labels.target_date)
        counts,last_issue = {},{}
        for lead in range(1,61):
            requested = pd.MultiIndex.from_arrays([labels.point_id,(label_dates-pd.Timedelta(days=lead)).dt.strftime("%Y-%m-%d")])
            ids = key.get_indexer(requested)
            ok = ids>=0
            feature_ids,label_ids = ids[ok].astype(np.int32),np.flatnonzero(ok).astype(np.int32)
            np.savez_compressed(folder/"pairs"/f"lead_{lead:02d}.npz",feature_id=feature_ids,label_id=label_ids)
            counts[str(lead)] = len(feature_ids)
            last_issue[str(lead)] = features.iloc[feature_ids].issue_date.max() if len(feature_ids) else None
        selected = features[features.issue_date==str(issue.date())]
        if selected.empty:
            raise ValueError(f"No prediction rows for {name} at {issue.date()}")
        inference = []
        for lead in range(1,61):
            frame = selected.copy()
            frame["lead_days"] = lead
            target_date = issue+pd.Timedelta(days=lead)
            frame["target_date"] = str(target_date.date())
            for field,value in target_calendar(pd.DatetimeIndex([target_date]*len(frame))).items():
                frame[field] = value
            inference.append(frame)
        pd.concat(inference,ignore_index=True).to_csv(folder/"inference.csv",index=False)
        manifest["models"][name] = {"directory":str(folder),"base_features":feature_names[name],"features":feature_names[name]+["lead_days"]+list(target_calendar([issue])),"target":"target","daily_label_rows":len(labels),"feature_rows":len(features),"training_pairs_by_lead":counts,"last_training_issue_by_lead":last_issue,"last_observed_target":labels.target_date.max(),"inference_locations":len(selected),"inference_rows":len(selected)*60,"first_prediction_date":str((issue+pd.Timedelta(days=1)).date()),"last_prediction_date":str((issue+pd.Timedelta(days=60)).date())}
        print(name,"daily labels",len(labels),"training pairs",sum(counts.values()),"inference locations",len(selected),flush=True)
    root.mkdir(parents=True,exist_ok=True)
    (root/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    policy = {"recipe_version":RECIPE,"models_trained":False,"smap_audit":source.MOISTURE_AUDIT,"power_files":power_files,"gpm_files":gpm_files,"smap_files":sm_files,"static_files":static_files,"rules":["Five daily outputs; direct lead_days 1..60; no recursive predictions","Only the selected target day must be observed; missing intermediate target days do not invalidate a pair","No target filling, interpolation or horizon averaging; SMAP daily mean of accepted AM/PM retrievals","Relaxed source quality and bounded causal feature filling inherited from recent LST/native-SMAP recipe","Weather/rain/SMAP use t-2; radiation uses t-7; future target calendar features are known at issue time","POWER uses LST daily bins; GPM and SMAP use UTC daily bins; publication-time archives are unverified","Normalized features/labels and NPZ pair indexes; loader joins in batches without copying features sixty times","Future validation must group by issue date across locations AND leads, and purge on target_date < next partition observation cutoff"]}
    (root/"preparation.json").write_text(json.dumps(policy,indent=2),encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--issue-date",default=datetime.now(ZoneInfo("America/Bogota")).date().isoformat())
    parser.add_argument("--output",type=Path,default=Path("data/prepared/daily"))
    args = parser.parse_args()
    build(args.output,pd.Timestamp(args.issue_date))


if __name__=="__main__":
    main()
