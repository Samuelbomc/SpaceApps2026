"""Explicit source selection and native NetCDF sampling for model preparation."""
from pathlib import Path
import re

import h5py
import numpy as np


def select_static(root):
    import json
    verified = []
    for folder in root.iterdir():
        report = folder / "coverage_validation.json"
        if report.exists() and json.loads(report.read_text())["passed"]:
            verified.append(folder)
    return max(verified, key=lambda p:p.name) if verified else root


def smap_dates(root, pattern):
    # Most recent collection takes precedence on overlapping measurement dates.
    result = {}
    for path in sorted(root.rglob(pattern)):
        match = re.search(r"_E_(\d{8})_", path.name)
        if match:
            import pandas as pd
            result[pd.Timestamp(match[1])] = path
    return result


def netcdf_samples(path, points, field="precipitation"):
    import pandas as pd
    with h5py.File(path) as ds:
        variables = {}
        ds.visititems(lambda name, obj: variables.update({name.rsplit('/',1)[-1]:name}) if isinstance(obj,h5py.Dataset) else None)
        if field not in variables:
            return [np.nan]*len(points)
        values = ds[variables[field]]
        lat = ds[variables["lat"]][:]
        lon = ds[variables["lon"]][:]
        if field == "precipitation" and values.attrs.get("units",b"").decode() != "mm/day":
            raise ValueError(f"Unexpected precipitation units: {path}")
        time_var = ds[variables["time"]]
        units = time_var.attrs["units"].decode()
        if not units.startswith("days since "):
            raise ValueError(f"Unsupported time units: {path}")
        measured = pd.Timestamp(units[len('days since '):]) + pd.Timedelta(days=float(time_var[0]))
        filename_day = re.search(r"3IMERG\.(\d{8})-",path.name)[1]
        if measured.strftime("%Y%m%d") != filename_day:
            raise ValueError(f"NetCDF time disagrees with file date: {path}")
        dims = values.attrs.get("coordinates",b"").decode().split()
        if dims != ["time","lon","lat"]:
            raise ValueError(f"Unexpected dimension order {dims}: {path}")
        fill = np.asarray(values.attrs.get("_FillValue",np.nan)).ravel()[0]
        result = []
        for x,y in points:
            i,j = int(np.abs(lon-x).argmin()), int(np.abs(lat-y).argmin())
            dx,dy = abs(float(np.median(np.diff(lon)))),abs(float(np.median(np.diff(lat))))
            # Coordinates are float32; 0.1-degree cell boundaries can differ
            # by several microdegrees after serialization.
            if abs(lon[i]-x)>dx/2+1e-4 or abs(lat[j]-y)>dy/2+1e-4:
                result.append(np.nan); continue
            value = float(values[0,i,j])
            result.append(value if np.isfinite(value) and value != fill and value >= 0 else np.nan)
        return result
