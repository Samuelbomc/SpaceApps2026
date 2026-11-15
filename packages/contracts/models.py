"""Contratos geográficos y temporales comunes (WGS84, EPSG:4326)."""

from dataclasses import asdict, dataclass
from datetime import date
from math import isfinite


@dataclass(frozen=True)
class GeoPoint:
    latitude: float
    longitude: float

    def __post_init__(self):
        if not all(isfinite(v) for v in (self.latitude, self.longitude)):
            raise ValueError("Las coordenadas deben ser finitas.")
        if not (-90 <= self.latitude <= 90 and -180 <= self.longitude <= 180):
            raise ValueError("Latitud fuera de [-90,90] o longitud fuera de [-180,180].")

    @property
    def cmr(self) -> str:
        # CMR usa longitud,latitud; la entrada pública usa campos con nombre.
        return f"{self.longitude},{self.latitude}"

    def as_dict(self) -> dict:
        return {
            "crs": "EPSG:4326",
            "latitude": float(self.latitude),
            "longitude": float(self.longitude),
        }


@dataclass(frozen=True)
class BoundingBox:
    west: float
    south: float
    east: float
    north: float

    def __post_init__(self):
        if not all(isfinite(v) for v in asdict(self).values()):
            raise ValueError("Las coordenadas deben ser finitas.")
        if not (-180 <= self.west < self.east <= 180):
            raise ValueError("Se requiere -180 <= oeste < este <= 180.")
        if not (-90 <= self.south < self.north <= 90):
            raise ValueError("Se requiere -90 <= sur < norte <= 90.")

    @property
    def cmr(self) -> str:
        return ",".join(map(str, (self.west, self.south, self.east, self.north)))

    def as_dict(self) -> dict:
        return {"crs": "EPSG:4326", **{key: float(value) for key, value in asdict(self).items()}}


ANTIOQUIA_ORIENTE = BoundingBox(-75.5830, 5.4110, -74.6167, 6.5866)


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date

    def __post_init__(self):
        if self.start > self.end:
            raise ValueError("La fecha inicial debe ser anterior o igual a la final.")

    @classmethod
    def parse(cls, start: str, end: str):
        return cls(date.fromisoformat(start), date.fromisoformat(end))

    @property
    def cmr(self) -> str:
        return f"{self.start.isoformat()}T00:00:00Z,{self.end.isoformat()}T23:59:59Z"

    def as_dict(self) -> dict:
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}
