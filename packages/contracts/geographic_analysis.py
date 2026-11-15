"""Selección pública y estado durable de un análisis geográfico."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, FiniteFloat

from packages.contracts.api import AnalysisResult, Contract, Observation
from packages.contracts.farms import FarmPolygon


class AnalysisPoint(Contract):
    type: Literal["Point"] = "Point"
    coordinates: tuple[FiniteFloat, FiniteFloat]


class GeographicAnalysisRequest(Contract):
    geometry: AnalysisPoint | FarmPolygon
    horizon_days: Literal[7, 15, 30, 60] = 7


class RegionalReference(Contract):
    kind: Literal["prepared_reference", "bundled_public_snapshot"]
    result: AnalysisResult


class GeographicObservation(Observation):
    latitude: FiniteFloat = Field(ge=-90, le=90)
    longitude: FiniteFloat = Field(ge=-180, le=180)
    time_standard: Literal["UTC", "LST"]
    retrieved_at: datetime


class GeographicAnalysis(Contract):
    request_id: UUID
    area_id: str
    geometry: AnalysisPoint | FarmPolygon
    sampling_point: AnalysisPoint
    sampling_method: Literal["selected_point", "interior_reference_point"]
    horizon_days: Literal[7, 15, 30, 60]
    forecast_start_date: date
    status: Literal["queued", "running", "waiting_inputs", "retry_scheduled", "completed", "failed"]
    attempts: int
    created_at: datetime
    updated_at: datetime
    retry_at: datetime | None = None
    messages: list[str] = Field(default_factory=list)
    result: AnalysisResult | None = None
    reference: RegionalReference | None = None
    observations: list[GeographicObservation] = Field(default_factory=list)
