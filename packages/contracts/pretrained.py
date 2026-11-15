"""Entradas procesadas de la receta expandida y metadatos de modelos recibidos."""

from datetime import date, timedelta
from typing import Literal

from pydantic import Field, FiniteFloat, model_validator

from packages.contracts.api import Contract


class ModelInfo(Contract):
    model_id: str
    model_kind: Literal["climate", "soil"]
    version: str
    horizon_days: int = 7
    forecast_type: Literal["period_aggregate", "direct_daily"] = "period_aggregate"
    supported_leads: list[int] = Field(default_factory=list)
    validation_status: Literal["experimental"] = "experimental"
    unit: str
    features: list[str]
    formula: str
    evaluation_mae: FiniteFloat
    baseline_mae: FiniteFloat
    evaluation_note: str = (
        "Selección rolling-origin con cuatro ventanas purgadas; métricas del test de "
        "evaluation_model.json. model.json fue reajustado con todos los datos y no tiene "
        "un test independiente posterior."
    )


class ModelInputContract(Contract):
    recipe_version: Literal["daily-direct-1-60-v1"] = "daily-direct-1-60-v1"
    input_lag_days: Literal[2] = 2
    feature_window_days: Literal[30] = 30
    radiation_lag_days: Literal[7] = 7
    forecast_start_rule: str = (
        "target_date = issue_date + lead_days; salidas diarias directas 1..60"
    )
    derived_features: list[str] = Field(
        default_factory=lambda: [
            "lead_days",
            "target_day_of_year_sin",
            "target_day_of_year_cos",
            "target_week_of_year",
        ]
    )
    csv_metadata_fields: list[str] = Field(
        default_factory=lambda: [
            "point_id",
            "latitude",
            "longitude",
            "issue_date",
            "observation_cutoff",
            "radiation_observation_cutoff",
        ]
    )
    climate_features: list[str]
    soil_features: list[str]
    climate_sources: list[str] = Field(
        default_factory=lambda: ["NASA POWER", "GPM IMERG Late", "SRTM", "Calendario"]
    )
    soil_additional_sources: list[str] = Field(
        default_factory=lambda: ["SMAP", "SoilGrids", "SRTM (pendiente)"]
    )
    provenance: str = (
        "El receptor calcula SHA-256 del archivo; region_id se declara como parámetro."
    )
    missing_values: str = "El receptor no rellena. El productor respeta rellenos causales y sus contadores de la receta diaria; suelo completo u omitido."
    labels: str = "target y fechas futuras no son necesarios para recibir entradas de inferencia."


class ModelCatalog(Contract):
    models: list[ModelInfo]
    recipe_version: str = "daily-direct-1-60-v1"
    supported_horizons: list[int]
    limitations: list[str]
    input_contract: ModelInputContract | None = None


class ExpandedFeatures(Contract):
    recipe_version: Literal["expanded-v1"] = "expanded-v1"
    region_id: str = Field(min_length=1, max_length=100)
    point_id: str | None = Field(default=None, min_length=1, max_length=100)
    longitude: FiniteFloat = Field(ge=-180, le=180)
    latitude: FiniteFloat = Field(ge=-90, le=90)
    issue_date: date
    observation_cutoff: date
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    climate: dict[str, FiniteFloat] = Field(min_length=1)
    soil: dict[str, FiniteFloat] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def exact_cutoff(self):
        if self.observation_cutoff != self.issue_date - timedelta(days=2):
            raise ValueError("La receta expanded-v1 exige observaciones hasta t-2.")
        if self.soil is not None and any(
            key in self.soil and self.soil[key] != value for key, value in self.climate.items()
        ):
            raise ValueError(
                "Clima y suelo deben compartir las mismas variables climáticas de esta celda."
            )
        return self


class DailyFeatures(ExpandedFeatures):
    recipe_version: Literal["daily-direct-1-60-v1"] = "daily-direct-1-60-v1"
    radiation_observation_cutoff: date

    @model_validator(mode="after")
    def radiation_cutoff(self):
        if self.radiation_observation_cutoff != self.issue_date - timedelta(days=7):
            raise ValueError("La receta diaria exige radiación hasta t-7.")
        return self
