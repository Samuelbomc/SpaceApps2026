"""Expand usable examples without fabricating target observations.

Climate models use all available POWER points and daily issue dates without
requiring SMAP. Moisture uses native SMAP cell centres and recommended AM/PM
retrievals. Last-observation features are bounded to six days and carry age.
"""
from io import StringIO
import json
from pathlib import Path
import re

import h5py
import numpy as np
import pandas as pd
import rasterio

from ml.scripts.dataset_sources import select_static, smap_dates
from ml.scripts.prepare_temperature_datasets import samples


ROOT = Path("data")
OUT = ROOT / "prepared/expanded"
INDEX = pd.date_range("2011-11-12", "2026-11-12")


def load_power():
    frames, points, files = [], [], []
    for path in sorted((ROOT/"POWER").rglob("*.csv")):
        text = path.read_text(encoding="utf-8-sig")
        match = re.search(r"Location: latitude\s+([-\d.]+)\s+longitude\s+([-\d.]+)",text)
        if not match:
            continue
        lat,lon = map(float,match.groups())
        if (lon,lat) in points or "in UTC" not in text:
            raise ValueError(f"Duplicate point/non-UTC POWER: {path}")
        lines = text.splitlines()
        header = next(i for i,s in enumerate(lines) if s.startswith("YEAR,DOY,"))
        frame = pd.read_csv(StringIO("\n".join(lines[header:])))
        frame.index = pd.to_datetime(frame.YEAR.astype(str),format="%Y")+pd.to_timedelta(frame.DOY-1,unit="D")
        if frame.index.has_duplicates:
            raise ValueError(f"Duplicate POWER date: {path}")
        frame = frame[["T2M","T2M_MIN","T2M_MAX","RH2M","QV2M","WS2M","ALLSKY_SFC_SW_DWN"]].replace([-999,np.inf,-np.inf],np.nan).reindex(INDEX)
        for col in ("T2M","T2M_MIN","T2M_MAX"):
            frame.loc[~frame[col].between(-100,70),col] = np.nan
        bad = (frame.T2M_MIN>frame.T2M)|(frame.T2M>frame.T2M_MAX)
        frame.loc[bad,["T2M","T2M_MIN","T2M_MAX"]] = np.nan
        frame.loc[~frame.RH2M.between(0,100),"RH2M"] = np.nan
        for col in ("QV2M","WS2M","ALLSKY_SFC_SW_DWN"):
            frame.loc[frame[col]<0,col] = np.nan
        points.append((lon,lat)); frames.append(frame); files.append(str(path))
    return points,frames,files


def load_rain(points):
    frame = pd.DataFrame(np.nan,index=INDEX,columns=range(len(points)))
    files = sorted((ROOT/"GPM").rglob("*3IMERGDL*.nc4"))
    seen = set()
    for number,path in enumerate(files):
        day = pd.Timestamp(re.search(r"3IMERG\.(\d{8})-",path.name)[1])
        if day not in INDEX:
            continue
        if day in seen:
            raise ValueError(f"Duplicate GPM date: {day}")
        seen.add(day)
        with h5py.File(path) as ds:
            var = ds["precipitation"]
            if var.attrs["units"].decode()!="mm/day" or var.attrs["coordinates"].decode().split()!=["time","lon","lat"]:
                raise ValueError(f"Unsupported precipitation units/dimensions: {path}")
            units = ds["time"].attrs["units"].decode()
            if not units.startswith("days since "):
                raise ValueError(f"Unsupported time units: {path}")
            stamp = pd.Timestamp(units[11:])+pd.Timedelta(days=float(ds["time"][0]))
            if stamp.strftime("%Y%m%d")!=day.strftime("%Y%m%d"):
                raise ValueError(f"Inconsistent measurement date: {path}")
            lon,lat = ds["lon"][:],ds["lat"][:]
            xs,ys = np.array(points).T
            i = np.abs(lon[:,None]-xs).argmin(axis=0)
            j = np.abs(lat[:,None]-ys).argmin(axis=0)
            values = var[0][i,j].astype(float)
            outside = (np.abs(lon[i]-xs)>abs(np.median(np.diff(lon)))/2+1e-4)|(np.abs(lat[j]-ys)>abs(np.median(np.diff(lat)))/2+1e-4)
            fill = np.asarray(var.attrs["_FillValue"]).ravel()[0]
            values[outside|~np.isfinite(values)|(values==fill)|(values<0)] = np.nan
            frame.loc[day] = values
        if number%1000==0:
            print(f"GPM {number}/{len(files)}",flush=True)
    return frame,[str(p) for p in files]


def load_moisture():
    paths = smap_dates(ROOT/"SMAP","*AM_soil_moisture_reformatted.tif")
    first = next(iter(paths.values()))
    with rasterio.open(first) as ds:
        grid = ds.shape,ds.transform,ds.crs
        rr,cc = np.indices(ds.shape)
        xs,ys = rasterio.transform.xy(ds.transform,rr.ravel(),cc.ravel())
        xs,ys = np.array(xs),np.array(ys)
        inside = (xs>=-75.583)&(xs<=-74.6167)&(ys>=5.411)&(ys<=6.5866)
        positions = np.flatnonzero(inside)
        points = list(zip(xs[inside],ys[inside]))
    moisture = pd.DataFrame(np.nan,index=INDEX,columns=range(len(points)))
    counts = moisture.copy()
    uncertainty_counts = moisture.copy()
    sources = []
    for day,am_path in paths.items():
        daily,uncertainty = [],[]
        for period,suffix in (("AM",""),("PM","_pm")):
            def path_for(field):
                return am_path.with_name(am_path.name.replace("AM_soil_moisture_reformatted",f"{period}_{field}{suffix}_reformatted"))
            def read(field):
                path = path_for(field)
                if not path.exists():
                    return np.full(len(points),np.nan)
                with rasterio.open(path) as ds:
                    if (ds.shape,ds.transform,ds.crs)!=grid:
                        raise ValueError(f"SMAP grids disagree: {path}")
                    a = ds.read(1,masked=True).astype(float).filled(np.nan).ravel()[positions]
                sources.append(str(path))
                return a
            values,quality,surface,error = (read(field) for field in ("soil_moisture","retrieval_qual_flag","surface_flag","soil_moisture_error"))
            flags = np.where(np.isfinite(quality),quality,3).astype(np.int64)
            good = ((flags&3)==0)&np.isfinite(surface)&(values>=0.02)&(values<=0.5)
            # Error calculation is unpopulated in these files. Retain missing
            # error, while enforcing published 0..0.2 limits where supplied.
            good &= np.isnan(error)|((error>=0)&(error<=0.2))
            daily.append(np.where(good,values,np.nan))
            uncertainty.append(good&np.isfinite(error))
        a = np.stack(daily)
        count = np.isfinite(a).sum(axis=0)
        moisture.loc[day] = np.divide(np.nansum(a,axis=0),count,out=np.full(len(points),np.nan),where=count>0)
        counts.loc[day] = count
        uncertainty_counts.loc[day] = np.stack(uncertainty).sum(axis=0)
    return points,moisture,counts,uncertainty_counts,sources


def static(points):
    values, sources = {},[]
    for name,filename in (("elevation_m","srtmgl1_dem_raw.tif"),("slope_degrees","srtmgl1_slope_degrees.tif")):
        path = select_static(ROOT/"SRTM")/filename
        values[name] = samples(path,points); sources.append(str(path))
    for prop,factor in {"sand":1,"silt":1,"clay":1,"soc":0.1,"bdod":0.01,"wv0010":0.001,"wv0033":0.001,"wv1500":0.001}.items():
        for statistic in ("mean","uncertainty"):
            path = select_static(ROOT/"SOILGRIDS")/f"soilgrids_v2_0_{prop}_0-5cm_{statistic}.tif"
            a = np.array(samples(path,points)); a[a<0] = np.nan
            values[f"soil_{prop}_{statistic}"] = a*(factor if statistic=="mean" else 1)
            sources.append(str(path))
    return values,sources


def climate_features(power,rain,elevation):
    f = pd.DataFrame(index=INDEX)
    for col in ("T2M","T2M_MIN","T2M_MAX","RH2M","QV2M","WS2M"):
        for days in (7,14,30):
            f[f"{col.lower()}_mean_{days}d"] = power[col].rolling(days,min_periods=days).mean().shift(2)
    f["t2m_last"] = power.T2M.shift(2)
    f["radiation_sum_7d"] = power.ALLSKY_SFC_SW_DWN.rolling(7,min_periods=7).sum().shift(2)
    for days in (1,3,7,14,30):
        f[f"gpm_late_sum_{days}d_mm"] = rain.rolling(days,min_periods=days).sum().shift(2)
    f["gpm_late_max_daily_7d_mm"] = rain.rolling(7,min_periods=7).max().shift(2)
    f["rainy_days_7d"] = (rain>0).where(rain.notna()).rolling(7,min_periods=7).sum().shift(2)
    f["elevation_m"] = elevation
    f["week_of_year"] = INDEX.isocalendar().week.to_numpy(dtype=float)
    f["day_of_year_sin"] = np.sin(2*np.pi*(INDEX.day_of_year-1)/365.2425)
    f["day_of_year_cos"] = np.cos(2*np.pi*(INDEX.day_of_year-1)/365.2425)
    return f


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    pp,powers,power_files = load_power()
    sp,sm,sm_counts,sm_error,sm_files = load_moisture()
    all_points = pp+sp
    rain,gpm_files = load_rain(all_points)
    terrain,static_files = static(all_points)
    manifest, tables, rejected = {},{name:[] for name in ("temperature_mean","temperature_min","temperature_max","precipitation","moisture")},{}
    features = {}
    target_map = {"temperature_mean":"T2M","temperature_min":"T2M_MIN","temperature_max":"T2M_MAX"}
    def add(name, f, label, point, extra=None):
        names = list(f.columns)
        features[name] = names
        frame = f.copy()
        frame["target"] = label
        valid = np.isfinite(frame.to_numpy(float)).all(axis=1)
        valid &= INDEX<=INDEX.max()-pd.Timedelta(days=7)
        rejected[name] = rejected.get(name,0)+int((~valid).sum())
        frame = frame.loc[valid].copy()
        frame["point_id"] = f"{name}_{point}"
        lon,lat = all_points[point]
        frame["longitude"],frame["latitude"] = lon,lat
        frame["issue_date"] = frame.index.strftime("%Y-%m-%d")
        for field,days in (("observation_cutoff",-2),("target_start",1),("target_end",7)):
            frame[field] = (frame.index+pd.Timedelta(days=days)).strftime("%Y-%m-%d")
        if extra is not None:
            for col,series in extra.items():
                frame[col] = series.reindex(frame.index)
        tables[name].append(frame)
    for i,power in enumerate(powers):
        f = climate_features(power,rain[i],terrain["elevation_m"][i])
        for name,col in target_map.items():
            add(name,f,power[col].rolling(7,min_periods=7).mean().shift(-7),i)
        add("precipitation",f,rain[i].rolling(7,min_periods=7).sum().shift(-7),i)
    for j,point in enumerate(sp):
        i = len(pp)+j
        nearest = int(np.argmin(np.sum((np.array(pp)-point)**2,axis=1)))
        f = climate_features(powers[nearest],rain[i],terrain["elevation_m"][i])
        s = sm[j]
        f["smap_mean_7d"] = s.rolling(7,min_periods=1).mean().shift(2)
        f["smap_last_valid_m3_m3"] = s.ffill(limit=6).shift(2)
        observed_date = pd.Series(pd.NaT,index=INDEX,dtype="datetime64[ns]")
        observed_date.loc[s.notna()] = INDEX[s.notna()]
        last_date = observed_date.ffill(limit=6).shift(2)
        f["smap_age_days"] = ((pd.Series(INDEX,index=INDEX)-pd.Timedelta(days=2))-last_date).dt.days
        f["smap_observed_days_7d"] = s.rolling(7,min_periods=1).count().shift(2)
        for key,values in terrain.items():
            f[key] = values[i]
        label = s.rolling(7,min_periods=1).mean().shift(-7)
        target_count = s.rolling(7,min_periods=1).count().shift(-7)
        extra = {"target_observed_days":target_count,
                 "target_retrieval_count":sm_counts[j].rolling(7,min_periods=1).sum().shift(-7),
                 "target_uncertainty_available_count":sm_error[j].rolling(7,min_periods=1).sum().shift(-7),
                 "smap_latest_observation_date":last_date.dt.strftime("%Y-%m-%d")}
        add("moisture",f,label,i,extra)
    for name,parts in tables.items():
        frame = pd.concat(parts,ignore_index=True).sort_values(["issue_date","point_id"])
        if frame.empty:
            raise ValueError(f"No complete examples: {name}")
        frame.to_csv(OUT/f"{name}.csv",index=False)
        dates = pd.to_datetime(frame.issue_date)
        # Reject duplicate target records at same cell/date, retain genuine
        # overlapping forecast horizons but record that they are correlated.
        assert not frame.duplicated(["point_id","issue_date"]).any()
        assert np.isfinite(frame[features[name]+["target"]].to_numpy(float)).all()
        manifest[name] = {"path":str(OUT/f"{name}.csv"),"features":features[name],"target":"target","rows":len(frame),"locations":int(frame.point_id.nunique()),"distinct_issue_dates":int(dates.nunique()),"first_issue":str(dates.min().date()),"last_issue":str(dates.max().date()),"excluded":rejected[name]}
        print(name,manifest[name]["rows"],"rows",manifest[name]["locations"],"locations",flush=True)
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    policy = {"power_files":power_files,"gpm_files":gpm_files,"smap_files":sm_files,"static_files":static_files,"rules":["Daily issue dates with inputs ending t-2 and targets t+1..t+7","No SMAP dependency in climate models","SMAP native cell centres inside original AOI; quality-screened AM/PM mean per day","Moisture meteorology from nearest downloaded POWER query location; no new climate resolution claimed","No linear interpolation, synthetic target labels or spatial upsampling","Latest SMAP feature carried forward at most six days with explicit observation age","Late Run rainfall targets; missing SMAP error recorded","Daily overlapping horizons and nearby cells are correlated; evaluate chronologically with purging","Strict complete finite predictor rows; no model-based imputation"]}
    (OUT/"preparation.json").write_text(json.dumps(policy,indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
