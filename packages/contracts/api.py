"""Contratos HTTP y puertos ML. No requieren XGBoost para levantar la API."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Region(Contract):
    region_id: str
    name: str
    latitude: FiniteFloat = Field(ge=-90, le=90)
    longitude: FiniteFloat = Field(ge=-180, le=180)


class MapPlace(Contract):
    latitude: FiniteFloat
    longitude: FiniteFloat
    label: str | None = None
    source: Literal["Photon/OpenStreetMap"] = "Photon/OpenStreetMap"


class AnalysisRequest(Contract):
    region_id: str = Field(min_length=1, max_length=100)
    reference_date: date
    horizon_days: int = Field(default=7, ge=1, le=90)
    forecast_start_date: date | None = Field(
        default=None,
        description="Inicio del periodo objetivo; si se omite, el día posterior a reference_date",
    )

    @model_validator(mode="after")
    def forecast_follows_inputs(self):
        if self.forecast_start_date is not None and self.forecast_start_date <= self.reference_date:
            raise ValueError(
                "El periodo objetivo debe comenzar después de la última fecha de entrada"
            )
        return self


class ForecastValue(Contract):
    variable: str
    value: FiniteFloat
    unit: str
    aggregation: str = Field(
        description="Ej.: media del periodo o acumulado; debe definirlo el modelo"
    )
    statistic: Literal["mean", "sum"] | None = None


class Forecast(Contract):
    model_kind: Literal["climate", "soil"]
    model_version: str = Field(min_length=1)
    validation_status: Literal["experimental", "validated", "unspecified"] = "unspecified"
    region_id: str
    reference_date: date
    forecast_start_date: date | None = None
    horizon_days: int = Field(ge=1, le=90)
    values: list[ForecastValue] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)


class Rotation(Contract):
    name: str
    crops: list[str] = Field(min_length=1)
    reasons: list[str] = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)


class Recommendations(Contract):
    engine_version: str = Field(min_length=1)
    catalog_version: str | None = Field(default=None, min_length=1)
    alternatives: list[Rotation] = Field(min_length=3)


class RotationCheck(Contract):
    variable: Literal["temperature", "precipitation", "surface_soil_moisture", "crop_family"]
    status: Literal["within_range", "outside_range", "unknown"]
    value: FiniteFloat | None = None
    unit: str
    explanation: str


class RotationCandidate(Contract):
    crop_id: str
    crop_name: str
    family: str
    status: Literal["excluded", "pending_requirements", "within_checked_ranges"]
    checks: list[RotationCheck]


class RotationStage(Contract):
    crop_id: str
    crop_name: str
    family: str
    forecast_evaluated: bool


class RotationScenario(Contract):
    stages: list[RotationStage]
    status: Literal["conditional"] = "conditional"
    explanation: str


class RotationAssessment(Contract):
    status: Literal[
        "pending_forecasts",
        "pending_agronomic_requirements",
        "evaluated",
        "no_compatible_candidates",
    ]
    engine_version: str
    catalog_version: str
    rules_version: str
    input_snapshot_id: str
    region_id: str
    forecast_start_date: date
    horizon_days: int
    climate_model_version: str | None = None
    soil_model_version: str | None = None
    forecast_values: dict[str, FiniteFloat] = Field(default_factory=dict)
    candidates: list[RotationCandidate] = Field(default_factory=list)
    scenarios: list[RotationScenario] = Field(default_factory=list)
    limitations: list[str]
    recommendation_ready: bool = False


class AnalysisResult(Contract):
    status: Literal[
        "pending_model", "pending_run", "insufficient_data", "pending_recommendations", "ready"
    ]
    request: AnalysisRequest
    analysis_id: str | None = None
    input_snapshot_id: str | None = None
    climate: Forecast | None = None
    soil: Forecast | None = None
    recommendations: Recommendations | None = None
    rotation_assessment: RotationAssessment | None = None
    messages: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def ready_requires_results(self):
        if self.status == "ready" and not (self.climate and self.soil and self.recommendations):
            raise ValueError("ready requiere ambos modelos y recomendaciones")
        return self


class Observation(Contract):
    source: str
    date: date
    variable: str
    value: FiniteFloat | None
    unit: str
    quality: str
    resolution: str


class ObservationPage(Contract):
    region_id: str
    items: list[Observation]
    limit: int
    offset: int = Field(default=0, ge=0)
    total: int | None = Field(default=None, ge=0)
    first_date: date | None = None
    last_date: date | None = None
    last_updated_at: datetime | None = None


class IngestionRun(Contract):
    run_id: str
    region_id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: Literal["running", "ok", "partial", "failed"]
    summary: dict = Field(default_factory=dict)


class Schedule(Contract):
    job_key: str
    interval_seconds: int
    next_run_at: datetime
    last_success_at: datetime | None = None
    last_error: str | None = None
    retry_at: datetime | None = None
    consecutive_failures: int = Field(default=0, ge=0)
    pending_sources: list[str] = Field(default_factory=list)
    last_result: dict = Field(default_factory=dict)


class StatusResponse(Contract):
    database: Literal["postgresql"] = "postgresql"
    climate_model: Literal["not_configured", "configured"]
    soil_model: Literal["not_configured", "configured"]
    recommendations: Literal["not_configured", "configured"]
    schedule: Schedule | None
    recent_runs: list[IngestionRun]
