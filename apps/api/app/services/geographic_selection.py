"""Identidad estable y muestreo interior explícito; no aumenta resolución."""

import hashlib
import json

from packages.contracts.models import ANTIOQUIA_ORIENTE


def selection(geometry):
    body = geometry.model_dump(mode="json")
    if body["type"] == "Point":
        point = body["coordinates"]
        method = "selected_point"
        vertices = [point]
    else:
        ring = body["coordinates"][0][:-1]
        # Inicio y orientación del mismo anillo no crean áreas diferentes.
        variants = []
        for oriented in (ring, list(reversed(ring))):
            start = min(range(len(oriented)), key=lambda i: tuple(oriented[i]))
            variants.append(oriented[start:] + oriented[:start])
        ring = min(variants)
        body["coordinates"] = [[*ring, ring[0]]]
        vertices = ring
        # Intersecciones de una horizontal entre niveles de vértices: punto interior
        # incluso para polígonos cóncavos cuyo centro de bbox quede fuera.
        levels = sorted({p[1] for p in ring})
        spans = []
        for low, high in zip(levels, levels[1:]):
            lat = (low + high) / 2
            hits = []
            for a, b in zip(ring, [*ring[1:], ring[0]]):
                if (a[1] > lat) != (b[1] > lat):
                    hits.append(a[0] + (lat - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
            hits.sort()
            spans.extend((b - a, (a + b) / 2, lat) for a, b in zip(hits[::2], hits[1::2]))
        _, lon, lat = max(spans)
        point, method = [lon, lat], "interior_reference_point"
    # Alcance de los modelos integrados; fuera se necesita otra validación.
    scope = ANTIOQUIA_ORIENTE
    if any(
        not (scope.west <= lon <= scope.east and scope.south <= lat <= scope.north)
        for lon, lat in vertices
    ):
        raise ValueError("La selección está fuera del ámbito geográfico de los modelos integrados.")
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return digest, body, {"type": "Point", "coordinates": point}, method
