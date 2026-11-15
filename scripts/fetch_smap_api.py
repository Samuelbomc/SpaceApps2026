"""Download complete regional SPL3SMP_E.006 via NASA CMR and Harmony APIs.

Requires requests and rasterio. EARTHDATA_TOKEN is read only from the environment.
Use --catalog-only for public discovery. Resume by rerunning with the same output.
The legacy collection is deleted only after complete validation with --replace-old.
"""

import argparse
import json
import os
import re
import shutil
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import rasterio
import requests

CMR = "https://cmr.earthdata.nasa.gov/search"
HARMONY = "https://harmony.earthdata.nasa.gov"
BBOX = "-75.583,5.411,-74.6167,6.5866"
FIELDS = [
    f"/Soil_Moisture_Retrieval_Data_{period}/{field}{suffix}"
    for period, suffix in (("AM", ""), ("PM", "_pm"))
    for field in ("soil_moisture", "soil_moisture_error", "retrieval_qual_flag", "surface_flag")
]


def get_json(session, url, **kwargs):
    response = session.get(url, timeout=120, **kwargs)
    response.raise_for_status()
    return response.json()


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


def download_assets(session, catalog_url, directory):
    pending, visited, downloaded = [catalog_url], set(), []
    while pending:
        url = pending.pop()
        if url in visited:
            continue
        visited.add(url)
        document = get_json(session, url)
        pending.extend(
            urljoin(url, link["href"])
            for link in document.get("links", [])
            if link.get("rel") in ("item", "child", "next")
        )
        for asset in document.get("assets", {}).values():
            href = urljoin(url, asset["href"])
            name = unquote(Path(urlparse(href).path).name)
            if not name.lower().endswith((".tif", ".tiff")):
                continue
            target = directory / name
            if not target.exists():
                # Signed output URLs do not need the Earthdata bearer token.
                with requests.get(href, stream=True, timeout=180) as response:
                    response.raise_for_status()
                    temporary = target.with_suffix(".part")
                    with temporary.open("wb") as stream:
                        for chunk in response.iter_content(1024 * 1024):
                            stream.write(chunk)
                    temporary.replace(target)
            with rasterio.open(target) as ds:
                if ds.crs is None or ds.width == 0 or ds.height == 0:
                    raise ValueError(f"Invalid raster: {target}")
                ds.read(1, masked=True)  # Fully decode to check corruption.
            downloaded.append(name)
    return sorted(set(downloaded))


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--end", default="2026-11-12")
    parser.add_argument("--output", type=Path, default=Path("data/SMAP/SPL3SMP_E_006_API_complete"))
    parser.add_argument("--catalog-only", action="store_true")
    parser.add_argument("--replace-old", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    public = requests.Session()
    entries = get_json(
        public,
        f"{CMR}/collections.json",
        params={"short_name": "SPL3SMP_E", "version": "006", "page_size": 10},
    )["feed"]["entry"]
    if len(entries) != 1:
        raise ValueError("Expected one SMAP version 006 collection")
    collection = entries[0]["id"]
    granules, page = [], 1
    while True:
        items = get_json(
            public,
            f"{CMR}/granules.json",
            params={
                "collection_concept_id": collection,
                "bounding_box": BBOX,
                "temporal": f"2015-03-31T00:00:00Z,{args.end}T23:59:59Z",
                "page_size": 2000,
                "page_num": page,
                "sort_key[]": "start_date",
            },
        )["feed"]["entry"]
        granules.extend(items)
        if len(items) < 2000:
            break
        page += 1
    expected = sorted({g["time_start"][:10] for g in granules})
    write_json(
        args.output / "cmr_inventory.json",
        {"collection": collection, "bbox": BBOX, "dates": expected, "granules": granules},
    )
    print(
        f"CMR: {len(granules)} granules on {len(expected)} dates; {expected[0]} through {expected[-1]}",
        flush=True,
    )
    if args.catalog_only:
        return
    token = os.environ.get("EARTHDATA_TOKEN")
    if not token:
        raise SystemExit(
            "Download blocked: configure EARTHDATA_TOKEN locally. Public inventory saved; old SMAP data retained."
        )
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {token}"
    # Monthly requests avoid truncation/preview limits and permit durable resume.
    for month in sorted({day[:7] for day in expected}):
        state_path = args.output / f"job_{month}.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        if not state.get("job_id"):
            month_start = date.fromisoformat(month + "-01")
            next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            start = max(month_start, date(2015, 3, 31))
            end = min(next_month - timedelta(days=1), date.fromisoformat(args.end))
            params = [
                ("subset", "lon(-75.583:-74.6167)"),
                ("subset", "lat(5.411:6.5866)"),
                ("subset", f'time("{start}T00:00:00Z":"{end}T23:59:59Z")'),
                ("variable", ",".join(FIELDS)),
                ("format", "image/tiff"),
                ("outputCrs", "EPSG:4326"),
                ("forceAsync", "true"),
                ("skipPreview", "true"),
                ("ignoreErrors", "false"),
                ("maxResults", "100"),
            ]
            response = session.get(
                f"{HARMONY}/{collection}/ogc-api-coverages/1.0.0/collections/parameter_vars/coverage/rangeset",
                params=params,
                timeout=180,
            )
            response.raise_for_status()
            state = {"job_id": response.json()["jobID"]}
            write_json(state_path, state)
        status_url = f"{HARMONY}/jobs/{state['job_id']}"
        while True:
            status = get_json(session, status_url)
            print(f"{month}: {status.get('status')} {status.get('progress', '')}", flush=True)
            if status.get("status") == "successful":
                break
            if status.get("status") in ("failed", "canceled"):
                raise RuntimeError(f"Harmony job {state['job_id']} did not succeed")
            time.sleep(15)
        state["files"] = download_assets(session, f"{HARMONY}/stac/{state['job_id']}", args.output)
        write_json(state_path, state)
    # Require all eight AM/PM layers on every date returned by CMR. Real mission
    # outages are absent from CMR and are not fabricated by interpolation.
    paths = list(args.output.glob("*.tif")) + list(args.output.glob("*.tiff"))
    missing = []
    for day in expected:
        day_files = [p.name for p in paths if day.replace("-", "") in p.name]
        for field in FIELDS:
            group, name = field.strip("/").split("/")
            if not any(
                group in p and re.search(rf"_{re.escape(name)}(?:_|\.)", p) for p in day_files
            ):
                missing.append([day, field])
    write_json(
        args.output / "validation.json",
        {
            "expected_dates": len(expected),
            "tiff_files": len(paths),
            "missing_layers": missing,
            "complete": not missing,
        },
    )
    if missing:
        raise SystemExit(
            f"Incomplete replacement: {len(missing)} missing layers. Old collection retained."
        )
    if args.replace_old:
        old = Path("data/SMAP/SPL3SMP_E_006-20261114_235253").resolve()
        allowed = Path("data/SMAP").resolve()
        if old.parent != allowed or old == args.output.resolve():
            raise ValueError("Unsafe legacy removal target")
        if old.exists():
            shutil.rmtree(old)
    print("Replacement validated successfully.")


if __name__ == "__main__":
    main()
