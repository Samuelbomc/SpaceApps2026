"""Verify downloaded static rasters cover the AOI and every local POWER point."""
import argparse
import json
from pathlib import Path
import re

import numpy as np
import rasterio
from rasterio.warp import transform


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--power-directory", type=Path, required=True)
    parser.add_argument("--bbox", type=float, nargs=4, required=True)
    parser.add_argument("--expected-count", type=int, required=True)
    args = parser.parse_args()
    west, south, east, north = args.bbox
    points = [(west,south),(west,north),(east,south),(east,north)]
    power_points = []
    for path in args.power_directory.rglob("*.csv"):
        text = path.read_text(encoding="utf-8-sig")[:4000]
        match = re.search(r"Location: latitude\s+([-\d.]+)\s+longitude\s+([-\d.]+)",text)
        if match:
            lat, lon = map(float,match.groups())
            power_points.append((lon,lat))
    points += sorted(set(power_points))
    results = []
    for path in sorted(args.directory.glob("*.tif")):
        record = {"file":path.name,"errors":[]}
        try:
            with rasterio.open(path) as ds:
                if ds.crs is None:
                    raise ValueError("Missing CRS")
                xs, ys = transform("EPSG:4326", ds.crs, [p[0] for p in points], [p[1] for p in points])
                for source, x, y in zip(points,xs,ys):
                    row,col = ds.index(x,y)
                    if not (0 <= row < ds.height and 0 <= col < ds.width):
                        record["errors"].append(f"Outside raster: {source}")
                        continue
                    value = ds.read(1,window=((row,row+1),(col,col+1)),masked=True)[0,0]
                    if np.ma.is_masked(value) or not np.isfinite(value):
                        record["errors"].append(f"No valid value at {source}")
                record.update(crs=str(ds.crs),width=ds.width,height=ds.height,bounds=list(ds.bounds))
        except Exception as exc:
            record["errors"].append(str(exc))
        results.append(record)
    passed = bool(power_points) and len(results) == args.expected_count and all(not r["errors"] for r in results)
    report = {"passed":passed,"power_points_checked":len(set(power_points)),"aoi_corners_checked":4,"rasters":results}
    (args.directory/"coverage_validation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(f"Coverage {'PASS' if passed else 'FAIL'}: {len(results)} rasters; {len(set(power_points))} POWER points; four AOI corners")
    if not passed:
        for record in results:
            for error in record["errors"]:
                print(record["file"],error)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
