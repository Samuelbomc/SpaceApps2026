"""Contrato de consulta y respuesta compartido por todas las fuentes externas."""

import hashlib
import json
from dataclasses import dataclass
from typing import Literal, Protocol, TypedDict

from .models import BoundingBox, DateRange, GeoPoint

DEFAULT_POWER_PARAMETERS = ("T2M", "T2M_MIN", "T2M_MAX", "RH2M", "ALLSKY_SFC_SW_DWN", "WS2M")


@dataclass(frozen=True)
class DataQuery:
    period: DateRange | None = None
    point: GeoPoint | None = None
    bbox: BoundingBox | None = None
    limit: int = 20
    page_size: int = 100
    power_parameters: tuple[str, ...] = DEFAULT_POWER_PARAMETERS

    def __post_init__(self):
        if (self.point is None) == (self.bbox is None):
            raise ValueError("Especifica exactamente una ubicación: latitud/longitud o bbox.")
        if self.point is not None and not isinstance(self.point, GeoPoint):
            raise ValueError("point debe ser GeoPoint.")
        if self.bbox is not None and not isinstance(self.bbox, BoundingBox):
            raise ValueError("bbox debe ser BoundingBox.")
        if self.period is not None and not isinstance(self.period, DateRange):
            raise ValueError("period debe ser DateRange.")
        if (
            type(self.limit) is not int
            or not 1 <= self.limit <= 10000
            or type(self.page_size) is not int
            or not 1 <= self.page_size <= 2000
        ):
            raise ValueError("limit debe estar entre 1 y 10000; page_size entre 1 y 2000.")
        if isinstance(self.power_parameters, str):
            raise ValueError("power_parameters debe ser una lista de códigos, no una cadena.")
        parameters = tuple(dict.fromkeys(self.power_parameters))
        if not parameters or any(
            not isinstance(p, str) or not p or not p.replace("_", "").isalnum() for p in parameters
        ):
            raise ValueError("power_parameters debe contener códigos de variable válidos.")
        if self.point is not None and len(parameters) > 20:
            raise ValueError("POWER puntual admite hasta 20 variables por consulta.")
        object.__setattr__(self, "power_parameters", parameters)

    @classmethod
    def from_dict(cls, payload: dict):
        """Contrato JSON plano para consumidores; rechaza parámetros ignorados."""
        allowed = {
            "latitude",
            "longitude",
            "bbox",
            "start",
            "end",
            "limit",
            "page_size",
            "power_parameters",
        }
        if not isinstance(payload, dict) or payload.keys() - allowed:
            raise ValueError("Consulta inválida o con parámetros desconocidos.")
        has_point = "latitude" in payload or "longitude" in payload
        if has_point and not ("latitude" in payload and "longitude" in payload):
            raise ValueError("Se requieren latitude y longitude juntos.")
        if has_point and "bbox" in payload:
            raise ValueError("Selecciona punto o bbox, no ambos.")
        if ("start" in payload) != ("end" in payload):
            raise ValueError("Se requieren start y end juntos.")
        try:
            point = (
                GeoPoint(float(payload["latitude"]), float(payload["longitude"]))
                if has_point
                else None
            )
            values = payload.get("bbox")
            if values is not None and (not isinstance(values, (list, tuple)) or len(values) != 4):
                raise ValueError("bbox debe contener [oeste, sur, este, norte].")
            bbox = BoundingBox(*(float(v) for v in values)) if values is not None else None
            period = (
                DateRange.parse(payload["start"], payload["end"]) if "start" in payload else None
            )
            return cls(
                point=point,
                bbox=bbox,
                period=period,
                limit=payload.get("limit", 20),
                page_size=payload.get("page_size", 100),
                power_parameters=payload.get("power_parameters", DEFAULT_POWER_PARAMETERS),
            )
        except (TypeError, AttributeError, OverflowError):
            raise ValueError("Tipos inválidos en los parámetros de consulta.") from None

    def as_dict(self) -> dict:
        location = self.point.as_dict() if self.point is not None else self.bbox.as_dict()
        return {
            "location": {"type": "point" if self.point is not None else "bbox", **location},
            "period": self.period.as_dict() if self.period else None,
            "time_standard": "UTC",
            "limit": self.limit,
            "page_size": self.page_size,
            "power_parameters": list(self.power_parameters),
        }

    @property
    def query_id(self) -> str:
        canonical = json.dumps(
            self.as_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


class SourceResult(TypedDict):
    query_id: str
    source: str
    status: Literal["ok", "empty", "error"]
    data_kind: Literal["provider_response", "granule_catalog"]
    requested: dict
    metadata: dict
    data: dict | None
    error: str | None


class DataRepository(Protocol):
    def fetch(self, query: DataQuery) -> SourceResult: ...
