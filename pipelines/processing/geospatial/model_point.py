"""Extrae celdas nativas para un punto, con las reglas científicas de entrenamiento."""

import re

import numpy as np
import pandas as pd

from pipelines.ingestion.sources.nasa.model_inputs import POWER_FIELDS


def power_frame(envelope, index):
    raw = envelope["raw_responses"][0]
    if raw["query"]["time-standard"] != "LST":
        raise ValueError("Los modelos requieren POWER LST.")
    response = raw["response"]
    if response.get("header", {}).get("time_standard") != "LST":
        raise ValueError("La respuesta POWER no confirma el estándar LST.")
    expected = ("C", "C", "C", "%", "g/kg", "m/s", "MJ/m^2/day")
    for field, unit in zip(POWER_FIELDS, expected):
        if response["parameters"][field]["units"] != unit:
            raise ValueError(f"Unidad POWER incompatible: {field}.")
    f = pd.DataFrame(response["properties"]["parameter"])[list(POWER_FIELDS)]
    f.index = pd.to_datetime(f.index, format="%Y%m%d")
    if f.index.has_duplicates:
        raise ValueError("Fechas POWER duplicadas.")
    f = f.astype(float).replace([-999, np.inf, -np.inf], np.nan).reindex(index)
    for key in POWER_FIELDS[:3]:
        f.loc[~f[key].between(-100, 70), key] = np.nan
    bad = (f.T2M_MIN > f.T2M) | (f.T2M > f.T2M_MAX)
    f.loc[bad, list(POWER_FIELDS[:3])] = np.nan
    f.loc[~f.RH2M.between(0, 100), "RH2M"] = np.nan
    for key in POWER_FIELDS[4:]:
        f.loc[f[key] < 0, key] = np.nan
    return f


class NativePointReader:
    def read(self, root, region, index, *, smap_root=None):
        # Dependencias científicas solo en workers; el servidor HTTP no las importa.
        import h5py

        from ml.scripts.dataset_sources import netcdf_samples, samples, select_static

        point = [(region["longitude"], region["latitude"])]
        rain = pd.Series(np.nan, index=index)
        provenance = []
        for path in sorted((root / "GPM").rglob("*3IMERGDL*.nc4")):
            match = re.search(r"3IMERG\.(\d{8})-", path.name)
            if not match or pd.Timestamp(match[1]) not in index:
                continue
            day = pd.Timestamp(match[1])
            if any(
                entry.get("source") == "GPM" and entry.get("date") == str(day.date())
                for entry in provenance
            ):
                raise ValueError("Dos archivos GPM para el mismo día.")
            rain.loc[day] = netcdf_samples(path, point)[0]
            with h5py.File(path) as ds:
                xx, yy = ds["lon"][:], ds["lat"][:]
                col = int(np.abs(xx - point[0][0]).argmin())
                row = int(np.abs(yy - point[0][1]).argmin())
                cell = {
                    "longitude": float(xx[col]),
                    "latitude": float(yy[row]),
                    "row": row,
                    "column": col,
                }
            provenance.append(
                {
                    "source": "GPM",
                    "path": str(path),
                    "date": str(day.date()),
                    "unit": "mm/day",
                    "resolution": "0.1 degree",
                    "cell": cell,
                }
            )
        terrain = {}
        for key, filename in (
            ("elevation_m", "srtmgl1_dem_raw.tif"),
            ("slope_degrees", "srtmgl1_slope_degrees.tif"),
        ):
            folder = root / "SRTM"
            if folder.is_dir():
                path = select_static(folder) / filename
                if path.is_file():
                    terrain[key] = samples(path, point)[0]
                    if key == "slope_degrees" and not 0 <= terrain[key] <= 90:
                        terrain[key] = np.nan
                    provenance.append(
                        {"source": "SRTM", "path": str(path), "resolution": "1 arc-second"}
                    )
        for prop, scale in {
            "sand": 1,
            "silt": 1,
            "clay": 1,
            "soc": 0.1,
            "bdod": 0.01,
            "wv0010": 0.001,
            "wv0033": 0.001,
            "wv1500": 0.001,
        }.items():
            folder = root / "SOILGRIDS"
            if not folder.is_dir():
                continue
            for statistic in ("mean", "uncertainty"):
                path = select_static(folder) / f"soilgrids_v2_0_{prop}_0-5cm_{statistic}.tif"
                if not path.is_file():
                    continue
                value = samples(path, point)[0]
                terrain[f"soil_{prop}_{statistic}"] = (
                    value * (scale if statistic == "mean" else 1) if value >= 0 else np.nan
                )
                provenance.append(
                    {
                        "source": "SoilGrids 2.0",
                        "path": str(path),
                        "depth": "0-5cm",
                        "statistic": statistic,
                        "scale": scale if statistic == "mean" else 1,
                    }
                )
        moisture, counts, recommended = self.moisture(
            smap_root if smap_root is not None else root / "SMAP", point[0], index, provenance
        )
        return rain, moisture, counts, recommended, terrain, provenance

    @staticmethod
    def moisture(root, point, index, provenance):
        import h5py
        from rasterio.warp import transform

        values = pd.Series(np.nan, index=index)
        counts, recommended = pd.Series(0.0, index=index), pd.Series(0.0, index=index)
        files = {}
        for path in sorted(root.rglob("*"), key=lambda p: (p.name, str(p))):
            if path.suffix not in (".nc4", ".nc", ".h5"):
                continue
            match = re.search(r"_E_(\d{8})_", path.name)
            if not match or pd.Timestamp(match[1]) not in index:
                continue
            # Misma política de entrenamiento: revisión de nombre más reciente por día.
            files[pd.Timestamp(match[1])] = path
        for day, path in sorted(files.items()):
            accepted, good_count, cells = [], 0, []
            with h5py.File(path) as ds:
                for period, suffix in (("AM", ""), ("PM", "_pm")):
                    group = ds["Soil_Moisture_Retrieval_Data_" + period]
                    var = group["soil_moisture" + suffix]
                    if "x_global" in ds and "y_global" in ds:
                        x, y = transform("EPSG:4326", "EPSG:6933", [point[0]], [point[1]])
                        xx, yy = ds["x_global"][:], ds["y_global"][:]
                        col, row = int(np.abs(xx - x[0]).argmin()), int(np.abs(yy - y[0]).argmin())
                        if (
                            len(xx) < 2
                            or len(yy) < 2
                            or abs(xx[col] - x[0]) > abs(np.median(np.diff(xx))) / 2
                            or abs(yy[row] - y[0]) > abs(np.median(np.diff(yy))) / 2
                        ):
                            continue
                        lon, lat = transform(
                            "EPSG:6933", "EPSG:4326", [float(xx[col])], [float(yy[row])]
                        )
                    else:
                        # Global EASE2 M09 grid: native row/column, no resampling.
                        x, y = transform("EPSG:4326", "EPSG:6933", [point[0]], [point[1]])
                        col = int(np.floor((x[0] + 17367530.4451615) / 9008.055210146))
                        row = int(np.floor((7314540.8306386 - y[0]) / 9008.055210146))
                        if not (0 <= row < var.shape[0] and 0 <= col < var.shape[1]):
                            continue
                        lon, lat = (
                            [float(group["longitude" + suffix][row, col])],
                            [float(group["latitude" + suffix][row, col])],
                        )
                        # Fail closed if a subset/different grid was supplied as a global file.
                        cx, cy = transform("EPSG:4326", "EPSG:6933", lon, lat)
                        if abs(cx[0] - x[0]) > 4504.1 or abs(cy[0] - y[0]) > 4504.1:
                            raise ValueError("La geolocalización SMAP no coincide con EASE2 M09.")
                    quality = group["retrieval_qual_flag" + suffix]
                    value, flag = float(var[row, col]), float(quality[row, col])
                    cells.append(
                        {
                            "period": period,
                            "row": row,
                            "column": col,
                            "longitude": lon[0],
                            "latitude": lat[0],
                        }
                    )
                    unit = var.attrs.get("units", b"cm**3/cm**3")
                    if isinstance(unit, bytes):
                        unit = unit.decode()
                    if unit not in ("cm**3/cm**3", "m3/m3", "m^3/m^3", "m**3/m**3"):
                        raise ValueError("Unidad SMAP incompatible.")
                    if (
                        np.isfinite(value)
                        and 0.02 <= value <= 0.5
                        and np.isfinite(flag)
                        and flag == int(flag)
                        and not (int(flag) & 2)
                    ):
                        accepted.append(value)
                        good_count += int(not (int(flag) & 1))
                if accepted:
                    values.loc[day], counts.loc[day], recommended.loc[day] = (
                        np.mean(accepted),
                        len(accepted),
                        good_count,
                    )
            provenance.append(
                {
                    "source": "SMAP L3 enhanced 006",
                    "path": str(path),
                    "date": str(day.date()),
                    "unit": "m3/m3",
                    "resolution": "9 km",
                    "cells": cells,
                }
            )
        return values, counts, recommended
