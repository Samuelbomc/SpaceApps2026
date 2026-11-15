#!/usr/bin/env python3
"""
DANE MGN boundaries -> simplified GeoJSON for the public data portal (Module A).

Source
    Departamento Administrativo Nacional de Estadística (DANE),
    Marco Geoestadístico Nacional (MGN), version 2025.
    ArcGIS FeatureServer:
      https://geoportal.dane.gov.co/mparcgis/rest/services/MGN2025/Serv_CapasMGN_2025/FeatureServer
        layer 319 = Departamento, layer 317 = Municipio
    DANE states that department and municipal limits in the MGN follow the
    official limits supplied by IGAC.
    Reuse terms (dane.gov.co "Términos de uso"): use and transformation are
    authorised with the citation
      "Fuente: Departamento Administrativo Nacional de Estadística: www.dane.gov.co".

What this script does (reproducible, Python standard library only)
    1. Queries the FeatureServer in WGS84 (outSR=4326). The service is stored in
       Web Mercator (EPSG:3857); reprojection is done server-side by ArcGIS.
    2. Simplifies geometry server-side with `maxAllowableOffset` (Douglas–Peucker
       style generalisation, tolerance in degrees) and rounds coordinates with
       `geometryPrecision`. Tolerances are recorded in the metadata file.
    3. Converts Esri JSON polygons (rings) to RFC 7946 GeoJSON (outer rings CCW,
       holes CW, holes assigned to their containing outer ring).
    4. Computes a label point inside each polygon (pole-of-inaccessibility
       approximation) so names never float outside small/concave municipalities.
    5. Validates: expected counts, unique DIVIPOLA codes, non-empty names,
       coordinates within Colombia's bounding box, closed rings, and the area
       change caused by simplification versus DANE's official area field.
    6. Writes GeoJSON + a metadata/quality report into the frontend public folder.

Usage
    python3 pipelines/ingestion/sources/colombia/dane_mgn.py [--out frontend/public/geo]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

SERVICE = (
    "https://geoportal.dane.gov.co/mparcgis/rest/services/MGN2025/Serv_CapasMGN_2025/FeatureServer"
)
MGN_VERSION = "MGN 2025"
LAYER_DEPARTMENTS = 319
LAYER_MUNICIPALITIES = 317
CITATION = "Fuente: Departamento Administrativo Nacional de Estadística: www.dane.gov.co"

PILOT_DEPARTMENT_CODE = "05"  # Antioquia
EXPECTED_DEPARTMENTS = 33  # 32 departments + Bogotá D.C.
EXPECTED_PILOT_MUNICIPALITIES = 125  # Antioquia

# Simplification tolerances in degrees (~111 km per degree at the equator).
DEPT_TOLERANCE_DEG = 0.01  # ≈ 1.1 km — national overview scale
MUNI_TOLERANCE_DEG = 0.002  # ≈ 220 m — municipal scale in Antioquia
DEPT_PRECISION = 4  # decimal places ≈ 11 m
MUNI_PRECISION = 5  # decimal places ≈ 1.1 m

COLOMBIA_BBOX = (-82.0, -4.5, -66.0, 16.5)  # lon_min, lat_min, lon_max, lat_max (incl. San Andrés)
EARTH_RADIUS_KM = 6371.0088


# --------------------------------------------------------------------------- fetch
def query(layer: int, where: str, out_fields: str, tolerance: float, precision: int) -> dict:
    params = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": "true",
        "outSR": "4326",
        "maxAllowableOffset": str(tolerance),
        "geometryPrecision": str(precision),
        "f": "json",
    }
    url = f"{SERVICE}/{layer}/query?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "agrogeo-pipeline/0.1"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.load(resp)
    if "error" in data:
        raise RuntimeError(f"ArcGIS error for layer {layer}: {data['error']}")
    if data.get("exceededTransferLimit"):
        raise RuntimeError(f"Layer {layer}: transfer limit exceeded; paginate the query.")
    return data


# ------------------------------------------------------------------ geometry utils
def signed_area(ring: list[list[float]]) -> float:
    """Shoelace signed area in coordinate units (positive = counter-clockwise)."""
    s = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        s += x1 * y2 - x2 * y1
    return s / 2.0


def point_in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def esri_rings_to_geojson(rings: list[list[list[float]]]) -> dict:
    """Esri: outer rings clockwise, holes counter-clockwise. GeoJSON (RFC 7946): the reverse."""
    rings = [r if r[0] == r[-1] else r + [r[0]] for r in rings if len(r) >= 4]
    outers, holes = [], []
    for r in rings:
        (outers if signed_area(r) < 0 else holes).append(r)
    polygons = [[list(reversed(o))] for o in outers]  # outer -> CCW
    for h in holes:
        x, y = h[0]
        target = next(
            (p for p, o in zip(polygons, outers) if point_in_ring(x, y, o)),
            None,
        )
        if target is not None:
            target.append(list(reversed(h)))  # hole -> CW
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}
    return {"type": "MultiPolygon", "coordinates": polygons}


def polygons_of(geom: dict) -> list:
    return [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]


def ring_area_km2(ring: list[list[float]]) -> float:
    """Spherical polygon area (Chamberlain & Duquette 2007), km², absolute value."""
    total = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(ring, ring[1:]):
        total += math.radians(lon2 - lon1) * (
            2 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2))
        )
    return abs(total * EARTH_RADIUS_KM**2 / 2.0)


def geometry_area_km2(geom: dict) -> float:
    area = 0.0
    for poly in polygons_of(geom):
        area += ring_area_km2(poly[0]) - sum(ring_area_km2(h) for h in poly[1:])
    return area


def dist_to_segment(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def label_point(geom: dict, grid: int = 24) -> list[float]:
    """Approximate pole of inaccessibility of the largest polygon (grid search)."""
    poly = max(polygons_of(geom), key=lambda p: ring_area_km2(p[0]))
    outer = poly[0]
    xs, ys = [p[0] for p in outer], [p[1] for p in outer]
    best, best_d = None, -1.0
    for i in range(1, grid):
        for j in range(1, grid):
            x = min(xs) + (max(xs) - min(xs)) * i / grid
            y = min(ys) + (max(ys) - min(ys)) * j / grid
            if not point_in_ring(x, y, outer) or any(point_in_ring(x, y, h) for h in poly[1:]):
                continue
            d = min(dist_to_segment(x, y, *a, *b) for ring in poly for a, b in zip(ring, ring[1:]))
            if d > best_d:
                best, best_d = [x, y], d
    if best is None:  # extremely thin shape: fall back to first vertex
        best = outer[0]
    return [round(best[0], 5), round(best[1], 5)]


# -------------------------------------------------------------------- validation
def validate(
    features: list[dict], code_key: str, name_key: str, expected: int, area_key: str | None
):
    report = {"count": len(features), "expected": expected, "errors": [], "warnings": []}
    if len(features) != expected:
        report["errors"].append(f"Expected {expected} features, got {len(features)}")
    codes = [f["properties"][code_key] for f in features]
    if len(set(codes)) != len(codes):
        report["errors"].append("Duplicate codes found")
    for f in features:
        p = f["properties"]
        if not p.get(name_key):
            report["errors"].append(f"Empty name for code {p[code_key]}")
        for poly in polygons_of(f["geometry"]):
            for ring in poly:
                if ring[0] != ring[-1] or len(ring) < 4:
                    report["errors"].append(f"Invalid ring in {p[code_key]}")
                for lon, lat in ring:
                    if not (
                        COLOMBIA_BBOX[0] <= lon <= COLOMBIA_BBOX[2]
                        and COLOMBIA_BBOX[1] <= lat <= COLOMBIA_BBOX[3]
                    ):
                        report["errors"].append(
                            f"Coordinate outside Colombia bbox in {p[code_key]}"
                        )
                        break
    if area_key:
        deviations = []
        for f in features:
            official = f["properties"].get(area_key)
            if official:
                computed = geometry_area_km2(f["geometry"])
                deviations.append(
                    (abs(computed - official) / official * 100, f["properties"][code_key])
                )
        if deviations:
            deviations.sort(reverse=True)
            report["areaDeviationPct"] = {
                "max": round(deviations[0][0], 3),
                "maxCode": deviations[0][1],
                "mean": round(sum(d for d, _ in deviations) / len(deviations), 3),
                "note": "Simplified-geometry spherical area vs. DANE official area field.",
            }
            if deviations[0][0] > 2.0:
                report["warnings"].append(
                    "Some features changed area by more than 2% after simplification."
                )
    return report


# -------------------------------------------------------------------------- main
def build(out_dir: Path) -> None:
    retrieved = datetime.now(UTC).isoformat(timespec="seconds")

    deps_raw = query(
        LAYER_DEPARTMENTS,
        "DPTO_CCDGO IS NOT NULL",
        "DPTO_CCDGO,DPTO_CNMBRE,DPTO_NAREA",
        DEPT_TOLERANCE_DEG,
        DEPT_PRECISION,
    )
    departments = []
    for f in deps_raw["features"]:
        a = f["attributes"]
        geom = esri_rings_to_geojson(f["geometry"]["rings"])
        departments.append(
            {
                "type": "Feature",
                "id": int(a["DPTO_CCDGO"]),  # numeric id enables MapLibre feature-state
                "properties": {
                    "code": a["DPTO_CCDGO"],
                    "name": a["DPTO_CNMBRE"],
                    "areaKm2": round(a["DPTO_NAREA"], 1) if a.get("DPTO_NAREA") else None,
                    "isPilot": a["DPTO_CCDGO"] == PILOT_DEPARTMENT_CODE,
                    "labelLon": label_point(geom)[0],
                    "labelLat": label_point(geom)[1],
                },
                "geometry": geom,
            }
        )
    departments.sort(key=lambda f: f["properties"]["code"])

    munis_raw = query(
        LAYER_MUNICIPALITIES,
        f"DPTO_CCDGO='{PILOT_DEPARTMENT_CODE}'",
        "DPTO_CCDGO,MPIO_CDPMP,MPIO_CNMBRE,MPIO_TIPO,MPIO_NAREA",
        MUNI_TOLERANCE_DEG,
        MUNI_PRECISION,
    )
    municipalities = []
    for f in munis_raw["features"]:
        a = f["attributes"]
        geom = esri_rings_to_geojson(f["geometry"]["rings"])
        lp = label_point(geom)
        municipalities.append(
            {
                "type": "Feature",
                "id": int(a["MPIO_CDPMP"]),
                "properties": {
                    "code": a["MPIO_CDPMP"],
                    "departmentCode": a["DPTO_CCDGO"],
                    "name": a["MPIO_CNMBRE"],
                    "type": a.get("MPIO_TIPO"),
                    "areaKm2": round(a["MPIO_NAREA"], 1) if a.get("MPIO_NAREA") else None,
                    "labelLon": lp[0],
                    "labelLat": lp[1],
                },
                "geometry": geom,
            }
        )
    municipalities.sort(key=lambda f: f["properties"]["code"])

    dep_report = validate(departments, "code", "name", EXPECTED_DEPARTMENTS, "areaKm2")
    mun_report = validate(municipalities, "code", "name", EXPECTED_PILOT_MUNICIPALITIES, "areaKm2")
    if dep_report["errors"] or mun_report["errors"]:
        print(
            json.dumps(
                {"departments": dep_report, "municipalities": mun_report},
                indent=2,
                ensure_ascii=False,
            )
        )
        sys.exit("Validation failed; nothing written.")

    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "colombia-departamentos.geojson": departments,
        f"municipios-{PILOT_DEPARTMENT_CODE}.geojson": municipalities,
    }
    for name, feats in files.items():
        (out_dir / name).write_text(
            json.dumps(
                {"type": "FeatureCollection", "features": feats},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

    metadata = {
        "source": {
            "institution": "Departamento Administrativo Nacional de Estadística (DANE)",
            "product": f"Marco Geoestadístico Nacional ({MGN_VERSION})",
            "service": SERVICE,
            "layers": {"departments": LAYER_DEPARTMENTS, "municipalities": LAYER_MUNICIPALITIES},
            "officialLimitsNote": "DANE indicates MGN department and municipal limits follow official IGAC limits.",
            "citation": CITATION,
            "termsUrl": "https://www.dane.gov.co/index.php/terrminos-y-condiciones-dane",
        },
        "retrievedAt": retrieved,
        "processing": {
            "sourceCrs": "EPSG:3857 (Web Mercator)",
            "outputCrs": "EPSG:4326 (WGS84), reprojected server-side by ArcGIS (outSR=4326)",
            "simplification": {
                "method": "ArcGIS maxAllowableOffset (server-side generalisation)",
                "departmentsToleranceDeg": DEPT_TOLERANCE_DEG,
                "municipalitiesToleranceDeg": MUNI_TOLERANCE_DEG,
                "departmentsPrecisionDecimals": DEPT_PRECISION,
                "municipalitiesPrecisionDecimals": MUNI_PRECISION,
                "caveat": "Generalised boundaries for visualisation only; not for cadastral or legal use.",
            },
            "labelPoints": "Approximate pole of inaccessibility (grid search) of the largest part.",
            "script": "pipelines/ingestion/sources/colombia/dane_mgn.py",
        },
        "files": {
            name: {"features": len(feats), "bytes": (out_dir / name).stat().st_size}
            for name, feats in files.items()
        },
        "quality": {"departments": dep_report, "municipalities": mun_report},
    }
    (out_dir / "boundaries.metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata["files"], indent=2))
    print(json.dumps(metadata["quality"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", default="frontend/public/geo", type=Path)
    build(parser.parse_args().out)
