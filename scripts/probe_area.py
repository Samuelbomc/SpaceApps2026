"""Prueba pública reproducible: AOI métrico, catálogos y observaciones POWER."""

import argparse
import csv
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from math import isfinite
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from apps.api.app.services.nasa_data import NASADataService
from packages.contracts import BoundingBox, DataQuery, DateRange, GeoPoint
from pipelines.ingestion.http import IngestionError, JsonHTTPClient, utc_now, write_json
from pipelines.ingestion.sources.nasa.catalog import PRODUCTS
from pipelines.ingestion.storage.power import arrow_modules, observation_schema
from pipelines.processing.cleaning.power_point import process_power_point
from pipelines.processing.geospatial.aoi import square_aoi


def science_url(source: str, granules: list[dict]) -> str | None:
    """Selecciona un activo científico, excluyendo QA sueltos, XML y previews."""
    suffixes = {
        "gpm": (".nc4",),
        "smap": (".h5",),
        "srtm": (".hgt.zip", ".hgt"),
        "grace": (".nc", ".nc4"),
        "ecostress": ("_ETdaily.tif",),
        "ecostress-lst": ("_LST.tif",),
        "landsat": (".B04.tif",),
    }
    return next(
        (
            url
            for granule in granules
            for url in granule["data_urls"]
            if urlsplit(url).path.endswith(suffixes[source])
        ),
        None,
    )


def probe_public_access(url: str | None, *, opener=urlopen) -> dict:
    if url is None:
        return {"status": "no_science_asset", "science_values_read": False}
    host = urlsplit(url).hostname or ""
    if not host.endswith(".nasa.gov"):
        return {"status": "host_not_probed", "science_values_read": False}
    request = Request(url, method="HEAD", headers={"User-Agent": "FieldShift-AOI-Probe/0.1"})
    try:
        with opener(request, timeout=20) as response:
            content_type = response.headers.get("Content-Type", "")
            final_host = urlsplit(response.geturl()).hostname or ""
            status = (
                "login_page"
                if final_host == "urs.earthdata.nasa.gov"
                else "html_instead_of_data"
                if "text/html" in content_type.lower()
                else "head_accessible"
            )
            length = response.headers.get("Content-Length", "")
            return {
                "status": status,
                "http_status": response.status,
                "content_type": content_type,
                "content_length_bytes": int(length) if length.isdigit() else None,
                "science_values_read": False,
                "method": "HEAD",
                "url": url,
            }
    except HTTPError as exc:
        code = exc.code
        exc.close()
        return {
            "status": "authentication_required"
            if code == 401
            else "forbidden"
            if code == 403
            else "http_error",
            "http_status": code,
            "science_values_read": False,
            "method": "HEAD",
            "url": url,
        }
    except (URLError, TimeoutError):
        return {
            "status": "connection_error",
            "science_values_read": False,
            "method": "HEAD",
            "url": url,
        }


def probe_public_sample(url: str | None, *, opener=urlopen) -> dict:
    """GET acotado al encabezado; HEAD 200 no demuestra permiso de descarga."""
    if url is None:
        return {"status": "no_science_asset", "science_values_read": False}
    if not (urlsplit(url).hostname or "").endswith(".nasa.gov"):
        return {"status": "host_not_probed", "science_values_read": False}
    context = {
        "url": url,
        "method": "GET",
        "range": "bytes=0-15",
        "verified_at": utc_now(),
        "science_values_read": False,
    }
    request = Request(
        url, headers={"Range": "bytes=0-15", "User-Agent": "FieldShift-AOI-Probe/0.1"}
    )
    try:
        with opener(request, timeout=20) as response:
            header = response.read(16)  # También se limita si el servidor ignora Range.
            return {
                **context,
                "status": "header_read_only",
                "http_status": response.status,
                "content_type": response.headers.get("Content-Type"),
                "bytes_read": len(header),
                "signature_hex": header.hex(),
            }
    except HTTPError as exc:
        code = exc.code
        exc.close()
        return {
            **context,
            "status": "authentication_required"
            if code == 401
            else "forbidden"
            if code == 403
            else "http_error",
            "http_status": code,
            "bytes_read": 0,
        }
    except (URLError, TimeoutError):
        return {**context, "status": "connection_error", "bytes_read": 0}


def normalize_catalog(source: str, result: dict, aoi_id: str) -> list[dict]:
    rows = []
    payload = result.get("data") or {}
    for granule in payload.get("granules", []):
        size = granule.get("size_mb_reported")
        try:
            size = float(size)
            if not isfinite(size) or size < 0:
                size = None
        except (TypeError, ValueError):
            size = None

        def timestamp(value):
            return (
                datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat() if value else None
            )

        raw = granule["raw_metadata"]
        rows.append(
            {
                "aoi_id": aoi_id,
                "source": source,
                "product": payload["product"]["short_name"],
                "version": payload["product"]["version"],
                "granule_id": granule["id"],
                "observed_start": timestamp(granule.get("start")),
                "observed_end": timestamp(granule.get("end")),
                "file_size_reported_mb": size,
                "native_resolution": payload["product"]["resolution"],
                "data_urls": json.dumps(granule["data_urls"]),
                "native_extent": json.dumps(
                    {k: raw[k] for k in ("boxes", "polygons", "points") if k in raw}
                ),
                "spatial_selection": "catalog_intersection_only",
                "science_values_read": False,
            }
        )
    return rows


def run_probe(
    center: GeoPoint,
    period: DateRange,
    directory: Path,
    *,
    side_m: float = 10,
    limit: int = 3,
    check_access: bool = True,
    service=None,
    access_probe=probe_public_access,
    sample_probe=probe_public_sample,
) -> dict:
    pa, pq = arrow_modules()
    area = square_aoi(center, side_m)
    properties = area["properties"]
    aoi_id = properties["aoi_id"]
    bounds = properties["bbox"]
    bbox = BoundingBox(*(bounds[key] for key in ("west", "south", "east", "north")))
    service = service if service is not None else NASADataService(JsonHTTPClient())
    params = ("T2M", "T2M_MIN", "T2M_MAX", "RH2M", "WS10M", "ALLSKY_SFC_SW_DWN")
    point_query = DataQuery(point=center, period=period, power_parameters=params)
    area_query = DataQuery(bbox=bbox, period=period, limit=limit, power_parameters=params)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError(
            "Usa un directorio de prueba vacío para no mezclar evidencias de distintas ejecuciones."
        )
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / "area.geojson", area)
    write_json(
        directory / "request.json", {"area": area, "period": period.as_dict(), "limit": limit}
    )
    print("Consultando POWER en el centro del área...", flush=True)
    power = service.fetch(point_query, sources=("power",))
    write_json(directory / "raw/power-result.json", power)
    print(f"Consultando CMR con el bbox de {side_m:g} × {side_m:g} m...", flush=True)
    catalogs = service.fetch(area_query, sources=tuple(PRODUCTS))
    write_json(directory / "raw/catalog-results.json", catalogs)
    sources, observations, catalog_rows = {}, [], []
    power_result = power["sources"]["power"]
    power_raw = power_result.get("data")
    if power_raw is not None:
        observations = process_power_point(power_raw)
        for row in observations:
            row.update(
                {
                    "aoi_id": aoi_id,
                    "spatial_selection": "center_point_native_grid",
                    "raw_path": str(directory / "raw/power-result.json"),
                }
            )
        schema = (
            observation_schema()
            .append(pa.field("aoi_id", pa.string()))
            .append(pa.field("spatial_selection", pa.string()))
        )
        schema = schema.with_metadata({b"field_shift_schema": b"aoi_probe_power_v1"})
        records = [
            {**row, "date": datetime.fromisoformat(row["date"]).date()} for row in observations
        ]
        pq.write_table(
            pa.Table.from_pylist(records, schema=schema),
            directory / "power-observations.parquet",
            compression="snappy",
        )
    statistics = {}
    for variable in params:
        rows = [r for r in observations if r["variable"] == variable]
        values = [
            r["value"]
            for r in rows
            if r["value"] is not None and r["quality"] == "provider_value_unvalidated"
        ]
        statistics[variable] = {
            "rows": len(rows),
            "usable_basic_qc": len(values),
            "missing_or_flagged": len(rows) - len(values),
            "units": sorted({r["unit"] for r in rows}),
            "min": min(values) if values else None,
            "max": max(values) if values else None,
        }
    sources["power"] = {
        "status": power_result["status"],
        "data_kind": "scientific_observations",
        "science_values_read": bool(observations),
        "records": len(observations),
        "native_resolution": power_result["metadata"]["spatial_resolution"],
        "spatial_selection": "center_point_native_grid",
        "statistics": statistics,
        "error": power_result["error"],
    }
    for source, result in catalogs["sources"].items():
        catalog_rows.extend(normalize_catalog(source, result, aoi_id))
        payload = result.get("data") or {}
        granules = payload.get("granules", [])
        sources[source] = {
            "status": result["status"],
            "data_kind": "granule_catalog",
            "science_values_read": False,
            "granules_returned": len(granules),
            "limit_reached": payload.get("limit_reached", False),
            "native_resolution": result["metadata"]["spatial_resolution"],
            "science_asset": science_url(source, granules),
            "error": result["error"],
        }
    if check_access:
        print("Comprobando acceso público a activos con HEAD, sin descargar cuerpos...", flush=True)
        items = list(catalogs["sources"])
        with ThreadPoolExecutor(max_workers=3) as executor:
            checks = list(executor.map(access_probe, [sources[s]["science_asset"] for s in items]))
            samples = list(executor.map(sample_probe, [sources[s]["science_asset"] for s in items]))
        for source, check in zip(items, checks):
            sources[source]["access_probe"] = check
        for source, sample in zip(items, samples):
            sources[source]["content_access_probe"] = sample
    if catalog_rows:
        with (directory / "granule-catalog.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(catalog_rows[0]))
            writer.writeheader()
            writer.writerows(catalog_rows)
        schema = pa.schema(
            [
                (
                    key,
                    pa.float64()
                    if key == "file_size_reported_mb"
                    else pa.bool_()
                    if key == "science_values_read"
                    else pa.string(),
                )
                for key in catalog_rows[0]
            ],
            metadata={b"field_shift_schema": b"aoi_granule_catalog_v1"},
        )
        pq.write_table(
            pa.Table.from_pylist(catalog_rows, schema=schema),
            directory / "granule-catalog.parquet",
            compression="snappy",
        )
    errors = [s for s, result in sources.items() if result["status"] == "error"]
    summary = {
        "schema_version": 1,
        "completed_at": utc_now(),
        "aoi": properties,
        "period": period.as_dict(),
        "access_mode": "public_only",
        "sources": sources,
        "status": "partial" if errors else "ok",
        "query_errors": errors,
        "scientific_extraction_complete": False,
        "notes": "POWER representa su celda nativa en el centro del AOI. CMR selecciona archivos "
        "que intersectan el AOI, sin recortar ni leer píxeles. HEAD no extrae valores. "
        "No se interpoló a 10 m, no se calcularon NDVI/pendiente/ET y no se alinearon fechas.",
    }
    write_json(directory / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Prueba pública de un AOI métrico pequeño sobre WGS84"
    )
    parser.add_argument("--latitude", type=float, default=6.2442)
    parser.add_argument("--longitude", type=float, default=-75.5812)
    parser.add_argument("--side-m", type=float, default=10)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--skip-access-probe", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = run_probe(
            GeoPoint(args.latitude, args.longitude),
            DateRange.parse(args.start, args.end),
            args.directory,
            side_m=args.side_m,
            limit=args.limit,
            check_access=not args.skip_access_probe,
        )
        print(
            json.dumps(
                {
                    "directory": str(args.directory),
                    "status": summary["status"],
                    "sources": {key: value["status"] for key, value in summary["sources"].items()},
                },
                indent=2,
            )
        )
        return 1 if summary["query_errors"] else 0
    except (IngestionError, ValueError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
