"""Build strict precipitation and surface-moisture examples; never impute inputs.

Run with .venv-data/Scripts/python -m ml.scripts.prepare_water_datasets
"""
import argparse
from io import StringIO
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

from ml.scripts.prepare_temperature_datasets import samples, unique_paths
from ml.scripts.dataset_sources import netcdf_samples, select_static, smap_dates


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("data/prepared/water"))
    parser.add_argument("--max-smap-error", type=float, default=0.1,
                        help="Explicit conservative screening choice, m3/m3; not a NASA universal threshold")
    parser.add_argument("--allow-missing-smap-error", action="store_true")
    parser.add_argument("--provisional-late-targets", action="store_true")
    parser.add_argument("--available-data", action="store_true", help="Authorized available-data recipe; omit unavailable uncertainty predictors and exact SMAP lags")
    args = parser.parse_args()
    if args.available_data:
        args.allow_missing_smap_error = True
        args.provisional_late_targets = True
    args.output.mkdir(parents=True, exist_ok=True)
    index = pd.date_range("2011-11-12", "2026-11-12")
    points, powers, sources = [], [], []
    for path in sorted((args.data / "POWER").rglob("*.csv")):
        text = path.read_text(encoding="utf-8-sig")
        match = re.search(r"Location: latitude\s+([-\d.]+)\s+longitude\s+([-\d.]+)", text)
        if not match:
            continue
        lat, lon = map(float, match.groups())
        if (lon, lat) in points or "in UTC" not in text:
            raise ValueError(f"Duplicate point or non-UTC POWER: {path}")
        lines = text.splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith("YEAR,DOY,"))
        frame = pd.read_csv(StringIO("\n".join(lines[start:])))
        frame.index = pd.to_datetime(frame.YEAR.astype(str), format="%Y") + pd.to_timedelta(frame.DOY-1, unit="D")
        if frame.index.has_duplicates:
            raise ValueError(f"Duplicate date: {path}")
        frame = frame[["T2M", "RH2M", "QV2M", "WS2M", "ALLSKY_SFC_SW_DWN"]].replace([-999, np.inf, -np.inf], np.nan).reindex(index)
        frame.loc[~frame.T2M.between(-100, 70), "T2M"] = np.nan
        frame.loc[~frame.RH2M.between(0, 100), "RH2M"] = np.nan
        for col in ("QV2M", "WS2M", "ALLSKY_SFC_SW_DWN"):
            frame.loc[frame[col] < 0, col] = np.nan
        points.append((lon, lat)); powers.append(frame); sources.append(str(path))
    if not points:
        raise ValueError("No POWER files")

    def raster_series(paths, field="precipitation"):
        table = pd.DataFrame(np.nan, index=index, columns=range(len(points)))
        for day, path in paths.items():
            if day in index:
                table.loc[day] = netcdf_samples(path, points, field) if path.suffix == ".nc4" else samples(path, points)
                sources.append(str(path))
        return table

    # Product/quality fields must be explicitly present; never substitute Final for Late.
    gpm = list((args.data / "GPM").rglob("*.tif"))
    rain_paths = {}
    rain_tables = {}
    for run, code in (("late", "3IMERGDL"), ("final", "3IMERGDF")):
        for field in ("precipitation", "precipitationQualityIndex", "randomError"):
            paths = unique_paths([p for p in gpm if code in str(p) and p.name.endswith(f"_{field}_reformatted.tif")], r"3IMERG\.(\d{8})-")
            paths.update(unique_paths((args.data / "GPM").rglob(f"*{code}*.nc4"), r"3IMERG\.(\d{8})-"))
            table = raster_series(paths, field)
            table[table < 0] = np.nan
            rain_paths[f"{run}_{field}"] = {"candidate_files":len(paths), "dates_with_valid_samples":int(table.notna().any(axis=1).sum())}
            rain_tables[f"{run}_{field}"] = table
    # No numeric PQI acceptance cutoff is invented: valid nonnegative quality
    # and error must exist. Scientific cutoff still needs a documented policy.
    unscreened_late = rain_tables["late_precipitation"].copy()
    for run in ("late", "final"):
        rain_tables[f"{run}_precipitation"] = rain_tables[f"{run}_precipitation"].where(
            rain_tables[f"{run}_precipitationQualityIndex"].notna() & rain_tables[f"{run}_randomError"].notna())

    sm_paths = smap_dates(args.data / "SMAP", "*AM_soil_moisture_reformatted.tif")
    sm = raster_series(sm_paths)
    error, quality, surface = [], [], []
    for field, target in (("soil_moisture_error", error), ("retrieval_qual_flag", quality), ("surface_flag", surface)):
        paths = {day: path.with_name(path.name.replace("AM_soil_moisture_reformatted", f"AM_{field}_reformatted")) for day, path in sm_paths.items()}
        target.append(raster_series({d:p for d,p in paths.items() if p.exists()}))
    err, qual, surf = error[0], quality[0], surface[0]
    # Conservative explicit policy: recommended AM retrieval, no surface flags,
    # finite uncertainty <= configured maximum, published moisture valid range.
    bits = qual.fillna(3).astype(np.int64)
    smap_screen_counts = {"finite_moisture":int(sm.notna().sum().sum()), "recommended_quality_and_valid_range":int(((bits & 3).eq(0) & sm.ge(0.02) & sm.le(0.5)).sum().sum()), "zero_surface_flag":int(surf.eq(0).sum().sum()), "finite_error_within_threshold":int((err.ge(0) & err.le(args.max_smap_error)).sum().sum())}
    valid = (bits & 3).eq(0) & surf.eq(0) & err.ge(0) & err.le(args.max_smap_error) & sm.ge(0.02) & sm.le(0.5)
    if args.allow_missing_smap_error:
        # Recommended retrieval flags are the primary suitability criterion.
        # Missing unimplemented uncertainty is recorded, never fabricated.
        valid = (bits & 3).eq(0) & surf.notna() & (err.isna() | (err.ge(0) & err.le(args.max_smap_error))) & sm.ge(0.02) & sm.le(0.5)
    sm = sm.where(valid)

    static = {}
    for key, pattern, factor in [("elevation_m", "srtmgl1_dem_raw.tif", 1), ("slope_degrees", "srtmgl1_slope_degrees.tif", 1)]:
        paths = list(select_static(args.data / "SRTM").rglob(pattern))
        if len(paths) > 1:
            raise ValueError(f"Ambiguous static layer: {key}")
        static[key] = samples(paths[0], points) if paths else [np.nan]*len(points)
        sources.extend(map(str, paths))
    for prop, factor in {"sand":1, "silt":1, "clay":1, "soc":0.1, "bdod":0.01, "wv0010":0.001, "wv0033":0.001, "wv1500":0.001}.items():
        for statistic in ("mean", "uncertainty"):
            paths = list(select_static(args.data / "SOILGRIDS").rglob(f"*_{prop}_0-5cm_{statistic}.tif"))
            if len(paths) > 1:
                raise ValueError(f"Ambiguous SoilGrids layer: {prop}")
            values = np.array(samples(paths[0], points)) if paths else np.full(len(points), np.nan)
            values[values < 0] = np.nan
            static[f"soil_{prop}_{statistic}"] = values * (factor if statistic == "mean" else 1)
            sources.extend(map(str, paths))

    results = {"precipitation": [], "moisture": []}
    if args.provisional_late_targets:
        rain_tables["late_precipitation"] = unscreened_late
        rain_tables["final_precipitation"] = unscreened_late
    feature_sets = {}
    for point, power in enumerate(powers):
        moisture = sm[point]
        recent = moisture.ffill()
        observations = pd.Series(pd.NaT, index=index, dtype="datetime64[ns]")
        observations.loc[moisture.notna()] = index[moisture.notna()]
        latest = observations.ffill()
        for issue in pd.date_range(index.min(), index.max()-pd.Timedelta(days=7), freq="W-MON"):
            cutoff = issue-pd.Timedelta(days=2)
            if cutoff not in index:
                continue
            def window(series, days):
                return series.loc[cutoff-pd.Timedelta(days=days-1):cutoff].reindex(pd.date_range(cutoff-pd.Timedelta(days=days-1), cutoff))
            def aggregate(series, days, method):
                values = window(series, days)
                return float(getattr(values, method)()) if values.notna().all() else np.nan
            common = {f"{col.lower()}_mean_7d": aggregate(power[col], 7, "mean") for col in ("T2M", "RH2M", "WS2M")}
            common.update(radiation_sum_7d=aggregate(power.ALLSKY_SFC_SW_DWN, 7, "sum"), elevation_m=static["elevation_m"][point], week_of_year=float(issue.isocalendar().week), day_of_year_sin=float(np.sin(2*np.pi*(issue.day_of_year-1)/365.2425)), day_of_year_cos=float(np.cos(2*np.pi*(issue.day_of_year-1)/365.2425)), smap_last_valid_m3_m3=recent.loc[cutoff])
            for days in (1,3,7,14,30):
                common[f"gpm_late_sum_{days}d_mm"] = aggregate(rain_tables["late_precipitation"][point], days, "sum")
            target_days = pd.date_range(issue+pd.Timedelta(days=1), issue+pd.Timedelta(days=7))
            meta = {"point_id":f"power_{points[point][1]}_{points[point][0]}", "longitude":points[point][0], "latitude":points[point][1], "issue_date":str(issue.date()), "observation_cutoff":str(cutoff.date()), "target_start":str(target_days[0].date()), "target_end":str(target_days[-1].date()), "smap_latest_observation_date":str(latest.loc[cutoff].date()) if pd.notna(latest.loc[cutoff]) else ""}
            for model in results:
                features = common.copy()
                if model == "precipitation":
                    features["qv2m_mean_7d"] = aggregate(power.QV2M, 7, "mean")
                    features["gpm_late_max_daily_7d_mm"] = aggregate(rain_tables["late_precipitation"][point], 7, "max")
                    rain_window = window(rain_tables["late_precipitation"][point], 7)
                    features["rainy_days_7d"] = float((rain_window > 0).sum()) if rain_window.notna().all() else np.nan
                    features["gpm_random_error_mean_7d"] = aggregate(rain_tables["late_randomError"][point], 7, "mean")
                    # Baseline uses only earlier YEARS in the same ISO week;
                    # never learns climatology from future observations.
                    past = moisture.loc[:cutoff]
                    base = past[(past.index.year < cutoff.year) & (past.index.isocalendar().week.to_numpy() == issue.isocalendar().week)]
                    features["smap_weekly_anomaly_m3_m3"] = recent.loc[cutoff]-base.mean()
                    target_values = rain_tables["final_precipitation"].loc[target_days, point]
                    target = float(target_values.sum()) if target_values.notna().all() else np.nan
                else:
                    # Section 2.4 requires rain values, but does not require the
                    # precipitation model's extra PQI/randomError input fields.
                    for days in (1,3,7,14,30):
                        features[f"gpm_late_sum_{days}d_mm"] = aggregate(unscreened_late[point], days, "sum")
                    for lag in (1,3,7,14):
                        features[f"smap_lag_{lag}d"] = moisture.get(cutoff-pd.Timedelta(days=lag), np.nan)
                    features["smap_mean_7d"] = window(moisture, 7).mean()
                    for key, values in static.items():
                        features[key] = values[point]
                    target_values = moisture.reindex(target_days)
                    target = float(target_values.mean()) if target_values.notna().any() else np.nan
                if args.available_data:
                    if model == "precipitation":
                        features.pop("gpm_random_error_mean_7d", None)
                    else:
                        # Exact daily lags are not supportable by sparse L3
                        # retrievals. Retain the observed last value and 7-day
                        # mean; do not invent values for the missing lag dates.
                        for lag in (1,3,7,14):
                            features.pop(f"smap_lag_{lag}d", None)
                    # Keep the last observed moisture temporally representative
                    # by requiring a valid observation in the antecedent week.
                    if window(moisture, 7).notna().sum() == 0:
                        features["smap_last_valid_m3_m3"] = np.nan
                feature_sets[model] = list(features)
                results[model].append({**meta, **features, "target":target, "target_valid_days":int(target_values.count()), "smap_uncertainty_available_at_latest":bool(pd.notna(latest.loc[cutoff]) and pd.notna(err.loc[latest.loc[cutoff],point])), "smap_uncertainty_missing_in_target":int((moisture.reindex(target_days).notna() & err[point].reindex(target_days).isna()).sum())})
    summary = {}
    for model, records in results.items():
        frame = pd.DataFrame(records)
        required = feature_sets[model]+["target"]
        valid_rows = np.isfinite(frame[required].to_numpy(dtype=float)).all(axis=1)
        frame.to_csv(args.output/f"{model}_candidates_NOT_FOR_TRAINING.csv", index=False)
        frame.loc[valid_rows].to_csv(args.output/f"{model}.csv", index=False)
        excluded = frame.loc[~valid_rows, ["point_id","issue_date"]].copy()
        excluded["missing_or_invalid_fields"] = frame.loc[~valid_rows,required].apply(lambda r:";".join(r.index[~np.isfinite(r.to_numpy(dtype=float))]), axis=1)
        excluded.to_csv(args.output/f"{model}_excluded.csv", index=False)
        summary[model] = {"accepted":int(valid_rows.sum()), "excluded":int((~valid_rows).sum()), "valid_targets":int(frame.target.notna().sum()), "invalid_fields":{c:int(frame[c].isna().sum()) for c in required if frame[c].isna().any()}}
    report = {"models":summary, "gpm_files":rain_paths, "smap_dates":len(sm_paths), "smap_screen_counts":smap_screen_counts, "smap_valid_point_days":int(valid.sum().sum()), "required_features":feature_sets, "source_files":sources, "policy": {"smap":"AM only; retrieval bits 0/1 unset, surface_flag=0, error <= max_smap_error", "max_smap_error":args.max_smap_error, "surface_screen":"Conservative; may reject otherwise usable flagged terrain. Requires regional policy review.", "pqi_screen":"Finite nonnegative values only; no product-specific acceptance threshold specified in PDF", "anomaly":"Same ISO week in earlier calendar years, available by cutoff", "lags":"Exact calendar offsets from t-2, no interpolation", "rainy_day":"daily precipitation > 0 mm", "soil_units":"sand/silt/clay g/kg; soc g/kg; bdod kg/dm3; water m3/m3; uncertainty retained in source scaled units", "latency":"Measurement dates align, but publication times are not certified by these files"}}
    if args.available_data:
        report["recipe"] = "available_data_authorized"
        report["policy"].update(smap="AM recommended retrieval bits 0/1 unset; surface metadata present; missing error permitted and recorded", surface_screen="Nonzero surface flags retained when retrieval is recommended", pqi_screen="Absent GPM quality/error fields omitted with user authorization", rainfall_target="Late Run seven-day accumulated precipitation", lags="Exact SMAP 1/3/7/14-day lags omitted; last valid and seven-day observed mean retained", recency="At least one valid SMAP observation in antecedent seven calendar days")
    (args.output/"validation_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({"models":summary,"gpm_files":rain_paths,"smap_valid_point_days":int(valid.sum().sum())},indent=2))


if __name__ == "__main__":
    main()
