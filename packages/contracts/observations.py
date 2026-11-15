"""Observaciones POWER procesadas, independientes del motor de almacenamiento."""

import hashlib
import json
from typing import TypedDict

from .models import GeoPoint


def power_location_id(point: GeoPoint) -> str:
    """Identifica la ubicación solicitada; NO un píxel nativo del proveedor."""
    coordinates = [float(point.latitude) or 0.0, float(point.longitude) or 0.0]
    return hashlib.sha256(json.dumps(coordinates, separators=(",", ":")).encode()).hexdigest()


class PowerObservation(TypedDict):
    source: str
    product: str
    product_version: str | None
    api_version: str | None
    location_id: str
    cell_id: str | None
    latitude: float
    longitude: float
    response_latitude: float
    response_longitude: float
    date: str
    variable: str
    value: float | None
    raw_value: str | None
    unit: str
    quality: str
    time_standard: str
    resolution: str
    retrieved_at: str
    data_sources: str
    response_sha256: str
    raw_path: str | None
