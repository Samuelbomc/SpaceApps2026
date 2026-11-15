"""Contratos del ciclo de vida ML; sin dependencia de FastAPI ni XGBoost."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field, FiniteFloat, model_validator

from packages.contracts.api import Contract, Schedule

ModelKind = Literal["climate", "soil"]


class DatasetSnapshot(Contract):
    dataset_id: str
    region_id: str
    cutoff: date
    first_date: date
    last_date: date
    row_count: int = Field(gt=0)
    sha256: str
    schema_version: str = "power_observation_v1"


class LabeledSample(Contract):
    """El constructor debe demostrar que las entradas existían al emitir el pronóstico."""

    feature_date: date
    label_start: date
    label_end: date
    label_available_on: date
    features: dict[str, FiniteFloat]
    targets: dict[str, FiniteFloat]
    baseline: dict[str, FiniteFloat]
    label_sources: list[str] = Field(min_length=1)
    labels_verified: bool = False
    spatial_id: str = "region"
    longitude: FiniteFloat | None = None
    latitude: FiniteFloat | None = None
    observation_cutoff: date | None = None
    label_observed_days: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def temporal_order(self):
        if not self.feature_date < self.label_start <= self.label_end <= self.label_available_on:
            raise ValueError(
                "Las etiquetas deben ser posteriores a las entradas y estar disponibles después de su observación."
            )
        return self


class PreparedDataset(Contract):
    dataset_id: str
    recipe_version: str = Field(min_length=1)
    model_kind: ModelKind
    horizon_days: int = Field(ge=1, le=90)
    feature_names: list[str] = Field(min_length=1)
    target_units: dict[str, str] = Field(min_length=1)
    samples: list[LabeledSample]
    target_mode: Literal["complete", "per_target"] = "complete"
    publication_ready: bool = True
    provenance: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def consistent_columns(self):
        if len(set(self.feature_names)) != len(self.feature_names):
            raise ValueError("Las features deben tener nombres únicos y un orden explícito.")
        if len({(sample.feature_date, sample.spatial_id) for sample in self.samples}) != len(
            self.samples
        ):
            raise ValueError("Solo se admite una muestra por fecha y celda en cada tarea regional.")
        for sample in self.samples:
            expected = set(self.target_units)
            valid_targets = (
                set(sample.targets) == expected
                if self.target_mode == "complete"
                else bool(sample.targets) and set(sample.targets) <= expected
            )
            if (
                set(sample.features) != set(self.feature_names)
                or not valid_targets
                or set(sample.baseline) != set(sample.targets)
            ):
                raise ValueError(
                    "Features, targets y baseline deben coincidir con el esquema del dataset."
                )
            if (sample.label_end - sample.label_start).days + 1 != self.horizon_days:
                raise ValueError("Las etiquetas deben cubrir exactamente el horizonte declarado.")
        return self


class TrainingPolicy(Contract):
    version: str = "unconfigured-v1"
    min_train_samples: int = Field(default=365, ge=1)
    min_validation_samples: int = Field(default=90, ge=1)
    min_new_labels: int = Field(default=7, ge=1)
    validation_days: int = Field(default=180, ge=1)
    min_relative_improvement: FiniteFloat = Field(default=0.01, ge=0, lt=1)
    # Sin umbrales agronómicos explícitos no se permite publicar un modelo.
    max_mae: dict[str, FiniteFloat] = Field(default_factory=dict)
    split_strategy: Literal["rolling", "chronological_60_20_20", "rolling_origin"] = "rolling"
    min_test_samples: int = Field(default=1, ge=1)
    min_spatial_locations: int = Field(default=1, ge=1)
    publication_allowed: bool = True

    @model_validator(mode="after")
    def positive_errors(self):
        if any(value <= 0 for value in self.max_mae.values()):
            raise ValueError("Los límites MAE deben ser positivos y usar las unidades del target.")
        return self


class ModelRelease(Contract):
    slot: str
    version: str
    model_kind: ModelKind
    region_id: str
    horizon_days: int
    dataset_id: str
    training_fingerprint: str
    recipe_version: str
    policy_version: str
    trained_through: date
    feature_names: list[str]
    target_units: dict[str, str]
    artifact_sha256: dict[str, str]
    metrics: dict
    created_at: datetime
    evaluated_through: date | None = None
    validation_status: Literal["experimental", "validated"] = "validated"
    spatial_scope: dict = Field(default_factory=dict)
    forecast_type: Literal["period_aggregate", "direct_daily"] = "period_aggregate"
    supported_leads: list[int] = Field(default_factory=list)


class TrainingOutcome(Contract):
    slot: str
    status: Literal[
        "published",
        "rejected",
        "unchanged",
        "insufficient_labels",
        "pending_configuration",
        "pending_review",
    ]
    message: str
    dataset_id: str | None = None
    version: str | None = None


class AutomationStatus(Contract):
    results_backend: Literal["postgresql", "mongodb"]
    schedules: list[Schedule]
    published_models: list[ModelRelease]
    recent_training: list[TrainingOutcome]
    limitations: list[str]
