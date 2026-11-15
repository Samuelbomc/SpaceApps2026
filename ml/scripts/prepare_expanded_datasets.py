"""Prepare recent training labels and separate label-free forecast inputs.

Use POWER LST and both native SMAP NetCDF and older TIFF observations.
Relax quality rejection while preserving fill values, causal feature times,
real observed targets, and explicit coverage/imputation audit columns.
"""

import argparse
import json
import re
from io import StringIO
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform

from ml.features.recipe import climate_features
from ml.scripts.dataset_sources import samples, select_static, smap_dates

ROOT = Path("data")
OUT = ROOT / "prepared/expanded"
INDEX = pd.DatetimeIndex([])
FORECAST_DATE = pd.Timestamp("2026-11-10")
MOISTURE_AUDIT = {}
STATIC_IMPUTED = None


def discover_index(forecast_date):
    """Use the actual POWER file extent, not a frozen preparation date."""
    global INDEX, FORECAST_DATE
    FORECAST_DATE = pd.Timestamp(forecast_date)
    dates = []
    for path in (ROOT / "POWER").rglob("*.csv"):
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        header = next(i for i, s in enumerate(lines) if s.startswith("YEAR,DOY,"))
        f = pd.read_csv(StringIO("\n".join(lines[header:])), usecols=["YEAR", "DOY"])
        dates.extend(
            pd.to_datetime(f.YEAR.astype(str), format="%Y") + pd.to_timedelta(f.DOY - 1, unit="D")
        )
    if not dates:
        raise ValueError("No POWER measurements found")
    INDEX = pd.date_range(min(dates), max(max(dates), FORECAST_DATE))


def load_power():
    if INDEX.empty:
        discover_index(FORECAST_DATE)
    frames, points, files = [], [], []
    for path in sorted((ROOT / "POWER").rglob("*.csv")):
        text = path.read_text(encoding="utf-8-sig")
        match = re.search(r"Location: latitude\s+([-\d.]+)\s+longitude\s+([-\d.]+)", text)
        if not match:
            continue
        lat, lon = map(float, match.groups())
        if (lon, lat) in points or "in LST" not in text:
            raise ValueError(f"Duplicate point/non-LST POWER: {path}; current recipe requires LST")
        lines = text.splitlines()
        header = next(i for i, s in enumerate(lines) if s.startswith("YEAR,DOY,"))
        frame = pd.read_csv(StringIO("\n".join(lines[header:])))
        frame.index = pd.to_datetime(frame.YEAR.astype(str), format="%Y") + pd.to_timedelta(
            frame.DOY - 1, unit="D"
        )
        if frame.index.has_duplicates:
            raise ValueError(f"Duplicate POWER date: {path}")
        frame = (
            frame[["T2M", "T2M_MIN", "T2M_MAX", "RH2M", "QV2M", "WS2M", "ALLSKY_SFC_SW_DWN"]]
            .replace([-999, np.inf, -np.inf], np.nan)
            .reindex(INDEX)
        )
        for col in ("T2M", "T2M_MIN", "T2M_MAX"):
            frame.loc[~frame[col].between(-100, 70), col] = np.nan
        bad = (frame.T2M_MIN > frame.T2M) | (frame.T2M > frame.T2M_MAX)
        frame.loc[bad, ["T2M", "T2M_MIN", "T2M_MAX"]] = np.nan
        frame.loc[~frame.RH2M.between(0, 100), "RH2M"] = np.nan
        for col in ("QV2M", "WS2M", "ALLSKY_SFC_SW_DWN"):
            frame.loc[frame[col] < 0, col] = np.nan
        points.append((lon, lat))
        frames.append(frame)
        files.append(str(path))
    return points, frames, files


def load_rain(points):
    frame = pd.DataFrame(np.nan, index=INDEX, columns=range(len(points)))
    files = sorted((ROOT / "GPM").rglob("*3IMERGDL*.nc4"))
    seen = set()
    for number, path in enumerate(files):
        day = pd.Timestamp(re.search(r"3IMERG\.(\d{8})-", path.name)[1])
        if day not in INDEX:
            continue
        if day in seen:
            raise ValueError(f"Duplicate GPM date: {day}")
        seen.add(day)
        with h5py.File(path) as ds:
            var = ds["precipitation"]
            if var.attrs["units"].decode() != "mm/day" or var.attrs[
                "coordinates"
            ].decode().split() != ["time", "lon", "lat"]:
                raise ValueError(f"Unsupported precipitation units/dimensions: {path}")
            units = ds["time"].attrs["units"].decode()
            if not units.startswith("days since "):
                raise ValueError(f"Unsupported time units: {path}")
            stamp = pd.Timestamp(units[11:]) + pd.Timedelta(days=float(ds["time"][0]))
            if stamp.strftime("%Y%m%d") != day.strftime("%Y%m%d"):
                raise ValueError(f"Inconsistent measurement date: {path}")
            lon, lat = ds["lon"][:], ds["lat"][:]
            xs, ys = np.array(points).T
            i = np.abs(lon[:, None] - xs).argmin(axis=0)
            j = np.abs(lat[:, None] - ys).argmin(axis=0)
            values = var[0][i, j].astype(float)
            outside = (np.abs(lon[i] - xs) > abs(np.median(np.diff(lon))) / 2 + 1e-4) | (
                np.abs(lat[j] - ys) > abs(np.median(np.diff(lat))) / 2 + 1e-4
            )
            fill = np.asarray(var.attrs["_FillValue"]).ravel()[0]
            values[outside | ~np.isfinite(values) | (values == fill) | (values < 0)] = np.nan
            frame.loc[day] = values
        if number % 1000 == 0:
            print(f"GPM {number}/{len(files)}", flush=True)
    return frame, [str(p) for p in files]


def load_moisture():
    """Combine native EASE-grid NetCDF with older regridded TIFF observations.

    Non-recommended but attempted retrievals are accepted; fill values and
    physically invalid moisture are never promoted into measurements.
    """
    global MOISTURE_AUDIT
    if INDEX.empty:
        discover_index(FORECAST_DATE)
    nc_paths = smap_dates(ROOT / "SMAP", "*.nc4")
    tif_paths = smap_dates(ROOT / "SMAP", "*AM_soil_moisture_reformatted.tif")
    if not nc_paths:
        raise ValueError("Expected the newly downloaded native SMAP NetCDF files")
    with h5py.File(next(iter(nc_paths.values()))) as ds:
        x, y = np.meshgrid(ds["x_global"][:], ds["y_global"][:])
        lons, lats = transform("EPSG:6933", "EPSG:4326", x.ravel(), y.ravel())
        lons, lats = np.array(lons), np.array(lats)
        inside = (lons >= -75.583) & (lons <= -74.6167) & (lats >= 5.411) & (lats <= 6.5866)
        positions = np.flatnonzero(inside)
        points = list(zip(lons[inside], lats[inside]))
        native_x, native_y = ds["x_global"][:], ds["y_global"][:]
    moisture = pd.DataFrame(np.nan, index=INDEX, columns=range(len(points)))
    counts = pd.DataFrame(0.0, index=INDEX, columns=moisture.columns)
    uncertainty_counts = counts.copy()
    recommended_counts = counts.copy()
    sources = []
    raw_accepted, recommended_accepted = 0, 0

    def decoded(var):
        a = np.asarray(var[:], dtype=float)
        fill = var.attrs.get("_FillValue", np.nan)
        a[(a == fill) | ~np.isfinite(a)] = np.nan
        return a.ravel()[positions]

    days = sorted(set(nc_paths) | set(tif_paths))
    for number, day in enumerate(days):
        if day not in INDEX:
            continue
        daily, uncertainty, recommended = [], [], []
        nc = nc_paths.get(day)
        if nc is not None:
            sources.append(str(nc))
            with h5py.File(nc) as ds:
                if not (
                    np.array_equal(ds["x_global"][:], native_x)
                    and np.array_equal(ds["y_global"][:], native_y)
                ):
                    raise ValueError(f"Native SMAP grids disagree: {nc}")
                for period, suffix in (("AM", ""), ("PM", "_pm")):
                    group = ds["Soil_Moisture_Retrieval_Data_" + period]
                    values, quality, error = (
                        decoded(group[field + suffix])
                        for field in ("soil_moisture", "retrieval_qual_flag", "soil_moisture_error")
                    )
                    flags = np.where(np.isfinite(quality), quality, 65534).astype(np.int64)
                    # Bit 1 set means retrieval was not attempted. Bit 0 only
                    # marks not-recommended quality; retain and count it.
                    good = (
                        np.isfinite(values)
                        & (values >= 0.02)
                        & (values <= 0.5)
                        & np.isfinite(quality)
                        & ((flags & 2) == 0)
                    )
                    daily.append(np.where(good, values, np.nan))
                    uncertainty.append(good & np.isfinite(error) & (error >= 0) & (error <= 0.2))
                    recommended.append(good & ((flags & 1) == 0))
        else:
            am_path = tif_paths[day]
            for period, suffix in (("AM", ""), ("PM", "_pm")):

                def read(field):
                    path = am_path.with_name(
                        am_path.name.replace(
                            "AM_soil_moisture_reformatted", f"{period}_{field}{suffix}_reformatted"
                        )
                    )
                    if not path.exists():
                        return np.full(len(points), np.nan)
                    sources.append(str(path))
                    with rasterio.open(path) as ds:
                        xx, yy = transform(
                            "EPSG:4326", ds.crs, [p[0] for p in points], [p[1] for p in points]
                        )
                        rr, cc = rasterio.transform.rowcol(ds.transform, xx, yy)
                        rr, cc = np.array(rr), np.array(cc)
                        covered = (rr >= 0) & (cc >= 0) & (rr < ds.height) & (cc < ds.width)
                        a = ds.read(1, masked=True).astype(float).filled(np.nan)
                        result = np.full(len(points), np.nan)
                        result[covered] = a[rr[covered], cc[covered]]
                        return result

                values, quality, error = (
                    read(field)
                    for field in ("soil_moisture", "retrieval_qual_flag", "soil_moisture_error")
                )
                flags = np.where(np.isfinite(quality), quality, 65534).astype(np.int64)
                good = (
                    np.isfinite(values)
                    & (values >= 0.02)
                    & (values <= 0.5)
                    & np.isfinite(quality)
                    & ((flags & 2) == 0)
                )
                daily.append(np.where(good, values, np.nan))
                uncertainty.append(good & np.isfinite(error) & (error >= 0) & (error <= 0.2))
                recommended.append(good & ((flags & 1) == 0))
        a = np.stack(daily)
        count = np.isfinite(a).sum(axis=0)
        moisture.loc[day] = np.divide(
            np.nansum(a, axis=0), count, out=np.full(len(points), np.nan), where=count > 0
        )
        counts.loc[day] = count
        uncertainty_counts.loc[day] = np.stack(uncertainty).sum(axis=0)
        recommended_counts.loc[day] = np.stack(recommended).sum(axis=0)
        raw_accepted += int(count.sum())
        recommended_accepted += int(np.stack(recommended).sum())
        if number % 500 == 0:
            print(f"SMAP {number}/{len(days)}", flush=True)
    MOISTURE_AUDIT = {
        "native_cells": len(points),
        "source_date_count": len(days),
        "first_source_date": str(min(days).date()),
        "last_source_date": str(max(days).date()),
        "first_accepted_date": str(moisture.dropna(how="all").index.min().date()),
        "last_accepted_date": str(moisture.dropna(how="all").index.max().date()),
        "accepted_retrievals": raw_accepted,
        "recommended_retrievals": recommended_accepted,
        "nonrecommended_retrievals_retained": raw_accepted - recommended_accepted,
        "native_grid": "EPSG:6933; old TIFFs sampled at native cell centres with nearest-cell sampling",
    }
    # Keep the historical return contract; quality counts are also available
    # to preparation without becoming target-derived predictors.
    moisture.attrs["recommended_counts"] = recommended_counts
    return points, moisture, counts, uncertainty_counts, sources


def static(points):
    global STATIC_IMPUTED
    values, sources = {}, []
    for name, filename in (
        ("elevation_m", "srtmgl1_dem_raw.tif"),
        ("slope_degrees", "srtmgl1_slope_degrees.tif"),
    ):
        path = select_static(ROOT / "SRTM") / filename
        values[name] = samples(path, points)
        sources.append(str(path))
    for prop, factor in {
        "sand": 1,
        "silt": 1,
        "clay": 1,
        "soc": 0.1,
        "bdod": 0.01,
        "wv0010": 0.001,
        "wv0033": 0.001,
        "wv1500": 0.001,
    }.items():
        for statistic in ("mean", "uncertainty"):
            path = (
                select_static(ROOT / "SOILGRIDS") / f"soilgrids_v2_0_{prop}_0-5cm_{statistic}.tif"
            )
            a = np.array(samples(path, points))
            a[a < 0] = np.nan
            values[f"soil_{prop}_{statistic}"] = a * (factor if statistic == "mean" else 1)
            sources.append(str(path))
    STATIC_IMPUTED = np.zeros(len(points), dtype=int)
    for key, array in values.items():
        array = np.array(array, dtype=float)
        valid = np.flatnonzero(np.isfinite(array))
        if not len(valid):
            raise ValueError(f"Entire static layer is missing: {key}")
        for i in np.flatnonzero(~np.isfinite(array)):
            closest = valid[np.argmin(np.sum((np.array(points)[valid] - points[i]) ** 2, axis=1))]
            array[i] = array[closest]
            STATIC_IMPUTED[i] += 1
        values[key] = array
    return values, sources


def prepare(horizon, output, loaded):
    output.mkdir(parents=True, exist_ok=True)
    (
        (pp, powers, power_files),
        (sp, sm, sm_counts, sm_error, sm_files),
        rain,
        gpm_files,
        terrain,
        static_files,
    ) = loaded
    all_points = pp + sp
    manifest, tables, rejected = (
        {},
        {
            name: []
            for name in (
                "temperature_mean",
                "temperature_min",
                "temperature_max",
                "precipitation",
                "moisture",
            )
        },
        {},
    )
    features, inference = {}, {name: [] for name in tables}
    target_map = {
        "temperature_mean": "T2M",
        "temperature_min": "T2M_MIN",
        "temperature_max": "T2M_MAX",
    }

    def add(name, f, label, point, extra=None):
        names = list(f.columns)
        features[name] = names
        frame = f.copy()
        frame["target"] = label
        feature_valid = np.isfinite(f.to_numpy(float)).all(axis=1)
        valid = feature_valid & np.isfinite(label.to_numpy(float))
        rejected[name] = rejected.get(name, 0) + int((~valid).sum())
        frame["point_id"] = f"{name}_{point}"
        lon, lat = all_points[point]
        frame["longitude"], frame["latitude"] = lon, lat
        frame["issue_date"] = frame.index.strftime("%Y-%m-%d")
        for field, days in (
            ("observation_cutoff", -2),
            ("target_start", 1),
            ("target_end", horizon),
        ):
            frame[field] = (frame.index + pd.Timedelta(days=days)).strftime("%Y-%m-%d")
        if extra is not None:
            for col, series in extra.items():
                frame[col] = series.reindex(frame.index)
        for col, series in f.attrs.get("audit", {}).items():
            frame[col] = series.reindex(frame.index)
        frame.attrs = {}
        frame["static_imputed_fields"] = int(STATIC_IMPUTED[point])
        tables[name].append(frame.loc[valid].copy())
        # Prediction inputs must never require future target observations.
        selected = feature_valid & (INDEX == FORECAST_DATE)
        forecast = (
            frame.loc[selected]
            .drop(
                columns=[
                    c
                    for c in frame
                    if c == "target"
                    or c.startswith("target_observed")
                    or c.startswith("target_retrieval")
                    or c.startswith("target_uncertainty")
                    or c.startswith("target_recommended")
                ]
            )
            .copy()
        )
        inference[name].append(forecast)

    for i, power in enumerate(powers):
        f = climate_features(power, rain[i], terrain["elevation_m"][i])
        for name, col in target_map.items():
            count = power[col].rolling(horizon, min_periods=1).count().shift(-horizon)
            label = (
                power[col]
                .rolling(horizon, min_periods=max(1, int(np.ceil(0.8 * horizon))))
                .mean()
                .shift(-horizon)
            )
            label = label.where(INDEX <= power[col].last_valid_index() - pd.Timedelta(days=horizon))
            add(name, f, label, i, {"target_observed_days": count})
        label = rain[i].rolling(horizon, min_periods=horizon).sum().shift(-horizon)
        add(
            "precipitation",
            f,
            label,
            i,
            {
                "target_observed_days": rain[i]
                .rolling(horizon, min_periods=1)
                .count()
                .shift(-horizon)
            },
        )
    for j, point in enumerate(sp):
        i = len(pp) + j
        nearest = int(np.argmin(np.sum((np.array(pp) - point) ** 2, axis=1)))
        f = climate_features(powers[nearest], rain[i], terrain["elevation_m"][i])
        s = sm[j]
        f["smap_mean_7d"] = (
            s.rolling(7, min_periods=1).mean().shift(2).fillna(s.ffill(limit=14).shift(2))
        )
        f["smap_last_valid_m3_m3"] = s.ffill(limit=14).shift(2)
        observed_date = pd.Series(pd.NaT, index=INDEX, dtype="datetime64[ns]")
        observed_date.loc[s.notna()] = INDEX[s.notna()]
        last_date = observed_date.ffill(limit=14).shift(2)
        f["smap_age_days"] = (
            (pd.Series(INDEX, index=INDEX) - pd.Timedelta(days=2)) - last_date
        ).dt.days
        f["smap_observed_days_7d"] = s.rolling(7, min_periods=1).count().shift(2)
        for key, values in terrain.items():
            f[key] = values[i]
        label = s.rolling(horizon, min_periods=1).mean().shift(-horizon)
        last_valid = s.last_valid_index()
        label = label.where(
            INDEX
            <= (
                last_valid - pd.Timedelta(days=horizon)
                if last_valid is not None
                else INDEX.min() - pd.Timedelta(days=1)
            )
        )
        target_count = s.rolling(horizon, min_periods=1).count().shift(-horizon)
        extra = {
            "target_observed_days": target_count,
            "target_retrieval_count": sm_counts[j]
            .rolling(horizon, min_periods=1)
            .sum()
            .shift(-horizon),
            "target_uncertainty_available_count": sm_error[j]
            .rolling(horizon, min_periods=1)
            .sum()
            .shift(-horizon),
            "target_recommended_retrieval_count": sm.attrs["recommended_counts"][j]
            .rolling(horizon, min_periods=1)
            .sum()
            .shift(-horizon),
            "input_smap_nonrecommended_retrievals_7d": (
                sm_counts[j] - sm.attrs["recommended_counts"][j]
            )
            .rolling(7, min_periods=1)
            .sum()
            .shift(2),
            "smap_latest_observation_date": last_date.dt.strftime("%Y-%m-%d"),
        }
        add("moisture", f, label, i, extra)
    for name, parts in tables.items():
        frame = pd.concat(parts, ignore_index=True).sort_values(["issue_date", "point_id"])
        if frame.empty:
            raise ValueError(f"No complete examples: {name}")
        frame.to_csv(output / f"{name}.csv", index=False)
        dates = pd.to_datetime(frame.issue_date)
        # Reject duplicate target records at same cell/date, retain genuine
        # overlapping forecast horizons but record that they are correlated.
        assert not frame.duplicated(["point_id", "issue_date"]).any()
        assert np.isfinite(frame[features[name] + ["target"]].to_numpy(float)).all()
        manifest[name] = {
            "path": str(output / f"{name}.csv"),
            "horizon_days": horizon,
            "features": features[name],
            "target": "target",
            "rows": len(frame),
            "locations": int(frame.point_id.nunique()),
            "distinct_issue_dates": int(dates.nunique()),
            "first_issue": str(dates.min().date()),
            "last_issue": str(dates.max().date()),
            "excluded": rejected[name],
        }
        forecast = pd.concat(inference[name], ignore_index=True).sort_values(
            ["issue_date", "point_id"]
        )
        if forecast.empty:
            raise ValueError(f"No finite prediction inputs at {FORECAST_DATE.date()} for {name}")
        forecast.to_csv(output / f"{name}_inference.csv", index=False)
        manifest[name].update(
            inference_path=str(output / f"{name}_inference.csv"),
            inference_rows=len(forecast),
            inference_issue_date=str(FORECAST_DATE.date()),
            recipe_version="recent-lst-native-smap-v2",
        )
        print(
            horizon,
            "days:",
            name,
            manifest[name]["rows"],
            "rows",
            manifest[name]["locations"],
            "locations",
            flush=True,
        )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    policy = {
        "power_files": power_files,
        "gpm_files": gpm_files,
        "smap_files": sm_files,
        "static_files": static_files,
    }
    policy["horizon_days"] = horizon
    policy["recipe_version"] = "recent-lst-native-smap-v2"
    policy["power_time_standard"] = "LST"
    policy["daily_alignment"] = (
        "POWER uses local-solar calendar days; GPM and SMAP retain UTC calendar dates. Same-date bins are covariates, not identical 24-hour intervals. Weather/rain/SMAP inputs end t-2; radiation ends t-7. No UTC-to-LST rainfall reconstruction is claimed. Publication-time archives are unavailable; historical as-issued availability is not certified."
    )
    policy["smap_audit"] = MOISTURE_AUDIT
    policy["forecast_issue_date"] = str(FORECAST_DATE.date())
    policy["training_status"] = (
        "Prepared only; existing trained artifacts belong to the previous source recipe and were not retrained."
    )
    policy["rules"] = [
        "POWER LST; GPM Late and SMAP UTC; two-calendar-day observation lag",
        "Radiation uses a seven-day publication allowance in both training and inference",
        "Native EPSG:6933 SMAP NetCDF after 2022 combined with older nearest-sampled TIFFs",
        "Retain finite SMAP 0.02..0.50 with retrieval attempted; not-recommended flags retained and counted; missing uncertainty/surface metadata do not discard observations",
        "Causal feature-only forward fill: POWER at most 7 days; rainfall at most 3 days; SMAP at most 14 days with age/count metadata; no backward fill or future interpolation",
        "Static missing samples use nearest available sampled location; imputed-field counts retained",
        "Temperature targets require at least 80% observed days and a fully elapsed horizon; rainfall targets require every day; moisture targets average at least one real observation in a fully elapsed horizon",
        "Targets are never filled; target coverage and quality are audit metadata, never predictors",
        "Inference files contain finite features and no target; they do not require future observations",
    ]
    policy["rules"][0] = (
        f"Daily issue dates; inputs end t-2 except radiation t-7; targets t+1..t+{horizon}"
    )
    (output / "preparation.json").write_text(json.dumps(policy, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--horizons", type=int, nargs="+", default=[7, 15, 30, 60])
    parser.add_argument("--forecast-date", default="2026-11-10")
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    if any(h < 1 or h > 60 for h in args.horizons):
        parser.error("Horizons must be between 1 and 60 days")
    discover_index(args.forecast_date)
    power, moisture = load_power(), load_moisture()
    points = power[0] + moisture[0]
    rain, gpm_files = load_rain(points)
    terrain, static_files = static(points)
    loaded = power, moisture, rain, gpm_files, terrain, static_files
    for horizon in dict.fromkeys(args.horizons):
        output = (
            (args.output_root / f"{horizon}d")
            if args.output_root
            else (OUT if horizon == 7 else ROOT / f"prepared/horizons/{horizon}d")
        )
        prepare(horizon, output, loaded)


if __name__ == "__main__":
    main()
