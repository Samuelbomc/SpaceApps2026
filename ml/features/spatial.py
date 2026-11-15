"""Correspondencia explícita entre selección y observaciones geográficas disponibles."""

import math
from dataclasses import dataclass

from packages.contracts.api import SpatialMatch
from packages.contracts.pretrained import DailyFeatures


def distance_km(lon_a, lat_a, lon_b, lat_b):
    lat_a, lat_b, delta_lon = map(math.radians, (lat_a, lat_b, lon_b - lon_a))
    delta_lat = lat_b - lat_a
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    )
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(max(0.0, value))))


@dataclass(frozen=True)
class MatchedDailyInputs:
    snapshot: DailyFeatures
    spatial: SpatialMatch


def matched_inputs(region, snapshot):
    distance = distance_km(
        region["longitude"], region["latitude"], snapshot.longitude, snapshot.latitude
    )
    exact = (
        abs(region["longitude"] - snapshot.longitude) <= 1e-7
        and abs(region["latitude"] - snapshot.latitude) <= 1e-7
    )
    return MatchedDailyInputs(
        snapshot,
        SpatialMatch(
            method="exact" if exact else "nearest",
            requested_longitude=region["longitude"],
            requested_latitude=region["latitude"],
            used_longitude=snapshot.longitude,
            used_latitude=snapshot.latitude,
            distance_km=distance,
            source_point_id=snapshot.point_id,
            source_sha256=snapshot.source_sha256,
            issue_date=snapshot.issue_date,
        ),
    )
