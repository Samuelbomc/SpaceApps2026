"""Audit a downloaded SRTM collection without changing its rasters."""

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    names = {
        "raw": "srtmgl1_dem_raw.tif",
        "filled": "srtmgl1_dem_filled_for_hydrology.tif",
        "slope": "srtmgl1_slope_degrees.tif",
        "direction": "srtmgl1_d8_flow_direction.tif",
        "accumulation": "srtmgl1_d8_flow_accumulation_cells.tif",
    }
    arrays, records, grids = {}, {}, []
    for key, name in names.items():
        with rasterio.open(args.directory / name) as ds:
            values = ds.read(1, masked=True)
            valid = values.compressed()
            records[key] = {
                "file": name,
                "width": ds.width,
                "height": ds.height,
                "crs": str(ds.crs),
                "bounds": list(ds.bounds),
                "pixel_size_degrees": list(ds.res),
                "valid_cells": int(valid.size),
                "missing_cells": int(values.size - valid.size),
                "nonfinite_cells": int((~np.isfinite(valid)).sum()),
                "minimum": float(valid.min()),
                "maximum": float(valid.max()),
                "mean": float(valid.mean(dtype=np.float64)),
            }
            arrays[key] = values.filled(0)
            grids.append((ds.shape, ds.transform, ds.crs))
    raw, filled = arrays["raw"], arrays["filled"]
    delta = filled.astype(np.float64) - raw
    fill_stats = {
        "lowered_cells": int((delta < -1e-6).sum()),
        "raised_cells": int((delta > 1e-6).sum()),
        "maximum_raise_m": float(delta.max()),
        "mean_raise_m": float(delta.mean()),
    }
    del delta
    pointer, accumulation = arrays["direction"], arrays["accumulation"]
    interior_zeros = int((pointer[1:-1, 1:-1] == 0).sum())
    codes = [int(v) for v in np.unique(pointer)]
    bad_codes = [v for v in codes if v not in (0, 1, 2, 4, 8, 16, 32, 64, 128)]
    # Whitebox default D8 codes: NE,E,SE,S,SW,W,NW,N.
    violations = uphill = routed = 0
    rows, cols = pointer.shape
    for code, dr, dc in (
        (1, -1, 1),
        (2, 0, 1),
        (4, 1, 1),
        (8, 1, 0),
        (16, 1, -1),
        (32, 0, -1),
        (64, -1, -1),
        (128, -1, 0),
    ):
        r0, r1 = max(0, -dr), min(rows, rows - dr)
        c0, c1 = max(0, -dc), min(cols, cols - dc)
        mask = pointer[r0:r1, c0:c1] == code
        downstream = accumulation[r0 + dr : r1 + dr, c0 + dc : c1 + dc]
        upstream = accumulation[r0:r1, c0:c1]
        routed += int(mask.sum())
        violations += int((mask & (downstream <= upstream)).sum())
        uphill += int(
            (mask & (filled[r0 + dr : r1 + dr, c0 + dc : c1 + dc] > filled[r0:r1, c0:c1])).sum()
        )
    checks = {
        "identical_grids": all(g == grids[0] for g in grids),
        "no_missing_or_nonfinite_values": all(
            r["missing_cells"] == 0 and r["nonfinite_cells"] == 0 for r in records.values()
        ),
        "slope_in_0_to_90_degrees": records["slope"]["minimum"] >= 0
        and records["slope"]["maximum"] <= 90,
        "filled_dem_never_lowered": fill_stats["lowered_cells"] == 0,
        "valid_d8_codes": not bad_codes,
        "no_interior_sinks": interior_zeros == 0,
        "positive_accumulation": records["accumulation"]["minimum"] >= 1,
        "accumulation_grows_downstream": violations == 0,
        "flow_never_goes_uphill": uphill == 0,
    }
    report = {
        "passed": all(checks.values()),
        "checks": checks,
        "rasters": records,
        "fill_changes": fill_stats,
        "d8_codes": codes,
        "interior_sinks": interior_zeros,
        "routed_cells_checked": routed,
        "accumulation_violations": violations,
        "uphill_violations": uphill,
        "limitation": "Flow accumulation only includes upstream cells inside the downloaded DEM; this is internal consistency validation, not field validation.",
    }
    (args.directory / "srtm_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
