"""Áreas locales pequeñas construidas y verificadas sobre el elipsoide WGS84."""

import hashlib
import json
from math import isfinite

from packages.contracts import BoundingBox, GeoPoint
from pipelines.ingestion.http import IngestionError


def square_aoi(center: GeoPoint, side_m: float = 10) -> dict:
    if not isfinite(side_m) or not 0 < side_m <= 1000:
        raise ValueError("La prueba local admite lados entre 0 y 1000 m.")
    try:
        from geographiclib.geodesic import Geodesic
    except ImportError:
        raise IngestionError("Instala el extra geoespacial: python -m pip install '.[geospatial]'.") from None
    geod = Geodesic.WGS84
    endpoints = {az: geod.Direct(center.latitude, center.longitude, az, side_m / 2)
                 for az in (0, 90, 180, 270)}
    bbox = BoundingBox(endpoints[270]["lon2"], endpoints[180]["lat2"],
                       endpoints[90]["lon2"], endpoints[0]["lat2"])
    ring = [[bbox.west, bbox.south], [bbox.east, bbox.south], [bbox.east, bbox.north],
            [bbox.west, bbox.north], [bbox.west, bbox.south]]
    polygon = geod.Polygon()
    for lon, lat in ring[:-1]:
        polygon.AddPoint(lat, lon)
    _, perimeter, area = polygon.Compute()
    geometry = {"type": "Polygon", "coordinates": [ring]}
    aoi_id = hashlib.sha256(json.dumps(geometry, sort_keys=True).encode()).hexdigest()
    return {"type": "Feature", "geometry": geometry, "properties": {
        "aoi_id": aoi_id, "crs": "EPSG:4326", "center": center.as_dict(),
        "bbox": bbox.as_dict(), "requested_side_m": float(side_m),
        "east_west_center_m": geod.Inverse(center.latitude, bbox.west, center.latitude, bbox.east)["s12"],
        "north_south_center_m": geod.Inverse(bbox.south, center.longitude, bbox.north, center.longitude)["s12"],
        "area_geodesic_m2": abs(area), "perimeter_geodesic_m": perimeter,
        "method": "WGS84 cardinal offsets; geographic bbox, dimensions verified geodesically",
    }}
