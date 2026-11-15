"""Nombres del entorno del centro del mapa; separados de las regiones y datos NASA."""

import threading
import time
from collections import OrderedDict
from pathlib import Path

from packages.contracts.api import MapPlace
from pipelines.ingestion.http import IngestionError, JsonHTTPClient


class PlaceLookupBusy(RuntimeError):
    pass


class PlaceLookupUnavailable(RuntimeError):
    pass


class MapPlaceService:
    def __init__(self, endpoint, http=None, clock=time.monotonic):
        self.endpoint = endpoint
        self.http = http if http is not None else JsonHTTPClient(
            cache_dir=Path("data/cache/places"), timeout=5, attempts=1, cache_ttl=86400)
        self.clock, self.lock = clock, threading.Lock()
        self.cache = OrderedDict()
        self.next_request = 0.

    def resolve(self, latitude, longitude):
        key = (round(latitude, 3), round(longitude, 3))
        # Coordenadas aproximadas, sin nombres de fincas, usuarios o datos privados.
        if not self.lock.acquire(blocking=False):
            raise PlaceLookupBusy()
        try:
            now = self.clock()
            cached = self.cache.get(key)
            if cached and cached[0] > now:
                self.cache.move_to_end(key)
                return cached[1]
            if now < self.next_request:
                raise PlaceLookupBusy()
            self.next_request = now + 1.1
            try:
                payload = self.http.get(self.endpoint, {"lat": key[0], "lon": key[1], "limit": 1, "radius": 3})
                features = payload.get("features")
                if not isinstance(features, list):
                    raise ValueError("Respuesta de lugares inválida")
                label = None
                if features:
                    props = features[0].get("properties")
                    if not isinstance(props, dict):
                        raise ValueError("Respuesta de lugares inválida")
                    locality = props.get("district") or props.get("locality")
                    if not locality and props.get("osm_key") == "place":
                        locality = props.get("name")
                    values = [locality, props.get("city") or props.get("county"), props.get("state"), props.get("country")]
                    parts = []
                    for value in values:
                        if isinstance(value, str) and value.strip() and value.casefold() not in {part.casefold() for part in parts}:
                            parts.append(value.strip()[:150])
                    label = ", ".join(parts) or None
                result = MapPlace(latitude=key[0], longitude=key[1], label=label)
            except (IngestionError, ValueError, TypeError, AttributeError):
                raise PlaceLookupUnavailable() from None
            self.cache[key] = (now + 86400, result)
            self.cache.move_to_end(key)
            while len(self.cache) > 256:
                self.cache.popitem(last=False)
            return result
        finally:
            self.lock.release()
