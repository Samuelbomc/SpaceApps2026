"""Extract strict weekly temperature datasets from local raw products.

Run: .venv-data/Scripts/python scripts/prepare_temperature_datasets.py
Requires numpy, pandas and rasterio. Raw files are never modified.
"""
from __future__ import annotations

import argparse
from io import StringIO
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform


POWER = ("T2M", "T2M_MIN", "T2M_MAX", "RH2M", "ALLSKY_SFC_SW_DWN", "WS2M")


def samples(path, points):
    """Use containing native cell, including south-up rasters; reject outside cells."""
    result = []
    with rasterio.open(path) as ds:
        xs, ys = transform("EPSG:4326", ds.crs, [p[0] for p in points], [p[1] for p in points])
        for x, y in zip(xs, ys):
            row, col = ds.index(x, y)
            if not (0 <= row < ds.height and 0 <= col < ds.width):
                result.append(np.nan)
                continue
            value = ds.read(1, window=((row, row + 1), (col, col + 1)), masked=True)[0, 0]
            result.append(float(value) if not np.ma.is_masked(value) and np.isfinite(value) else np.nan)
    return result


def unique_paths(paths, date_pattern):
    result = {}
    for path in sorted(paths):
        match = re.search(date_pattern, path.name)
        if match:
            date = pd.Timestamp(match[1])
            if date in result:
                raise ValueError(f"Ambiguous duplicate measurement: {date}: {path} and {result[date]}")
            result[date] = path
    return result


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("data/prepared/temperature"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    inventory = []
    powers = []
    coords = []
    for path in sorted((args.data / "POWER").rglob("*.csv")):
        text = path.read_text(encoding="utf-8-sig")
        match = re.search(r"Location: latitude\s+([-\d.]+)\s+longitude\s+([-\d.]+)", text)
        if not match:
            continue
        lat, lon = map(float, match.groups())
        if (lon, lat) in coords:
            raise ValueError(f"Duplicate POWER point: {path}")
        header = next(i for i, line in enumerate(text.splitlines()) if line.startswith("YEAR,DOY,"))
        frame = pd.read_csv(StringIO("\n".join(text.splitlines()[header:])))
        frame.index = pd.to_datetime(frame.YEAR.astype(str), format="%Y") + pd.to_timedelta(frame.DOY - 1, unit="D")
        if frame.index.duplicated().any():
            raise ValueError(f"Duplicate POWER date: {path}")
        if "in UTC" not in text:
            raise ValueError(f"POWER is not explicitly UTC: {path}")
        frame = frame[list(POWER)].apply(pd.to_numeric, errors="coerce").replace([-999, np.inf, -np.inf], np.nan)
        for column in ("T2M", "T2M_MIN", "T2M_MAX"):
            frame.loc[~frame[column].between(-100, 70), column] = np.nan
        frame.loc[~frame.RH2M.between(0, 100), "RH2M"] = np.nan
        for column in ("WS2M", "ALLSKY_SFC_SW_DWN"):
            frame.loc[frame[column] < 0, column] = np.nan
        bad = (frame.T2M_MIN > frame.T2M) | (frame.T2M > frame.T2M_MAX)
        frame.loc[bad, ["T2M_MIN", "T2M", "T2M_MAX"]] = np.nan
        coords.append((lon, lat))
        powers.append(frame)
        inventory.append(str(path))
    if not powers:
        raise ValueError("No POWER point CSVs found")
    index = pd.date_range("2011-11-12", "2026-11-12", freq="D")
    powers = [p.reindex(index) for p in powers]

    # GPM daily V07 renamed precipitationCal to precipitation; use mm/day only.
    late = unique_paths((args.data / "GPM").rglob("*3IMERGDL*precipitation_reformatted.tif"), r"3IMERG\.(\d{8})-")
    final = unique_paths((args.data / "GPM").rglob("*3IMERGDF*precipitation_reformatted.tif"), r"3IMERG\.(\d{8})-")
    rain = pd.DataFrame(np.nan, index=index, columns=range(len(coords)))
    for date, path in late.items():
        if date not in index:
            continue
        with rasterio.open(path) as ds:
            if ds.tags().get("units") != "mm/day":
                raise ValueError(f"Unrecognized daily precipitation units: {path}")
        values = np.array(samples(path, coords))
        values[values < 0] = np.nan
        rain.loc[date] = values
        inventory.append(str(path))

    smap_files = unique_paths((args.data / "SMAP").rglob("*AM_soil_moisture_reformatted.tif"), r"_E_(\d{8})_")
    moisture = pd.DataFrame(np.nan, index=index, columns=range(len(coords)))
    for date, path in smap_files.items():
        quality = path.with_name(path.name.replace("AM_soil_moisture_reformatted", "AM_retrieval_qual_flag_reformatted"))
        if date not in index or not quality.exists():
            continue
        values = np.array(samples(path, coords))
        flags = np.array(samples(quality, coords))
        # SPL3SMP_E recommended retrieval: bits 0 and 1 unset.
        valid_flags = np.isfinite(flags) & (flags >= 0)
        bits = np.where(valid_flags, flags, 3).astype(np.int64)
        values[~valid_flags | ((bits & 3) != 0) | (values < 0.02) | (values > 0.5)] = np.nan
        moisture.loc[date] = values
        inventory.extend((str(path), str(quality)))

    dems = list((args.data / "SRTM").rglob("srtmgl1_dem_raw.tif"))
    if len(dems) != 1:
        raise ValueError("Expected exactly one raw SRTM DEM")
    elevations = samples(dems[0], coords)
    inventory.append(str(dems[0]))
    rows = []
    features = []
    for point, ((lon, lat), power) in enumerate(zip(coords, powers)):
        daily = power.copy()
        daily["rain"] = rain[point]
        daily["sm"] = moisture[point]
        last_sm = daily.sm.ffill()
        last_sm_date = pd.Series(pd.NaT, index=index, dtype="datetime64[ns]")
        last_sm_date.loc[daily.sm.notna()] = index[daily.sm.notna()]
        last_sm_date = last_sm_date.ffill()
        derived = pd.DataFrame(index=index)
        for col, windows in {"T2M": (7, 14, 30), "T2M_MIN": (7, 14), "T2M_MAX": (7, 14), "RH2M": (7, 14), "WS2M": (7,)}.items():
            for days in windows:
                derived[f"{col.lower()}_mean_{days}d"] = daily[col].rolling(days, min_periods=days).mean()
        derived["t2m_last"] = daily.T2M
        derived["radiation_sum_7d"] = daily.ALLSKY_SFC_SW_DWN.rolling(7, min_periods=7).sum()
        for days in (7, 14, 30):
            derived[f"gpm_late_sum_{days}d_mm"] = daily.rain.rolling(days, min_periods=days).sum()
        derived["smap_last_valid_m3_m3"] = last_sm
        derived["smap_mean_7d_m3_m3"] = daily.sm.rolling(7, min_periods=1).mean()
        derived["elevation_m"] = elevations[point]
        derived["week_of_year"] = 0.0
        derived["day_of_year_sin"] = 0.0
        derived["day_of_year_cos"] = 0.0
        features = list(derived.columns)
        # Weekly emissions anchored to Mondays. Windows retain calendar days,
        # rather than compressing missing measurements into adjacent rows.
        for issue in pd.date_range(index.min(), index.max() - pd.Timedelta(days=7), freq="W-MON"):
            cutoff = issue - pd.Timedelta(days=2)
            if cutoff not in derived.index:
                continue
            row = derived.loc[cutoff].to_dict()
            row.update(week_of_year=float(issue.isocalendar().week), day_of_year_sin=float(np.sin(2*np.pi*(issue.day_of_year-1)/365.2425)), day_of_year_cos=float(np.cos(2*np.pi*(issue.day_of_year-1)/365.2425)))
            target_start, target_end = issue + pd.Timedelta(days=1), issue + pd.Timedelta(days=7)
            for source, target in (("T2M", "target_mean_c"), ("T2M_MIN", "target_min_c"), ("T2M_MAX", "target_max_c")):
                values = daily.loc[target_start:target_end, source]
                row[target] = float(values.mean()) if len(values) == 7 and values.notna().all() else np.nan
            row.update(point_id=f"power_{lat}_{lon}", latitude=lat, longitude=lon, issue_date=issue.date().isoformat(), observation_cutoff=cutoff.date().isoformat(), target_start=target_start.date().isoformat(), target_end=target_end.date().isoformat(), smap_latest_observation_date=last_sm_date.loc[cutoff].date().isoformat() if pd.notna(last_sm_date.loc[cutoff]) else "", smap_valid_count_7d=int(daily.loc[cutoff-pd.Timedelta(days=6):cutoff, "sm"].count()))
            rows.append(row)
    candidates = pd.DataFrame(rows)
    candidates.to_csv(args.output / "candidate_inputs_and_targets_NOT_FOR_TRAINING.csv", index=False)
    summaries = {}
    for name, target in (("temperature_mean", "target_mean_c"), ("temperature_min", "target_min_c"), ("temperature_max", "target_max_c")):
        required = features + [target]
        valid = np.isfinite(candidates[required].to_numpy(dtype=float)).all(axis=1)
        metadata = ["point_id", "latitude", "longitude", "issue_date", "observation_cutoff", "target_start", "target_end", "smap_latest_observation_date", "smap_valid_count_7d"]
        output = candidates.loc[valid, metadata + required].copy()
        assert output[required].notna().all().all()
        output.to_csv(args.output / f"{name}.csv", index=False)
        rejected = candidates.loc[~valid, metadata].copy()
        rejected["missing_or_invalid_fields"] = candidates.loc[~valid, required].apply(lambda row: ";".join(row.index[~np.isfinite(row.to_numpy(dtype=float))]), axis=1)
        rejected.to_csv(args.output / f"{name}_excluded.csv", index=False)
        summaries[name] = {"accepted": int(valid.sum()), "excluded": int((~valid).sum()), "invalid_field_counts": {c: int((~np.isfinite(candidates[c])).sum()) for c in required if not np.isfinite(candidates[c]).all()}}
    report = {"models": summaries, "required_features": features, "period": [str(index.min().date()), str(index.max().date())], "power_points": coords, "gpm_late_files": len(late), "gpm_final_files_not_substituted": len(final), "smap_am_dates": len(smap_files), "smap_date_range": [str(min(smap_files).date()), str(max(smap_files).date())] if smap_files else [], "rules": ["UTC calendar windows ending t-2; labels only t+1 through t+7", "Weekly Monday emissions; daily POWER min/max targets are weekly MEANS of daily extrema", "All POWER and rain window days must be present; no imputation", "SMAP AM only, valid observations within preceding seven calendar days for weekly mean", "Containing native raster pixel; no spatial extrapolation", "GPM Final cannot satisfy the required Late predictor contract", "Observation cutoff does not certify actual archive publication time; latency metadata still required for operational backtesting"], "source_files": inventory}
    (args.output / "validation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"models": summaries, "gpm_late_files": len(late), "gpm_final_files": len(final), "smap_dates": len(smap_files)}, indent=2))


if __name__ == "__main__":
    main()
