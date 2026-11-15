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
    validation_status: Literal["experimental"] = "experimental"
    unit: str
    features: list[str]
    formula: str
    evaluation_mae: FiniteFloat
    baseline_mae: FiniteFloat
    evaluation_note: str = (
        "Métricas de evaluation_model.json; model.json fue reajustado con todos los datos."
    )


class ModelCatalog(Contract):
    models: list[ModelInfo]
    recipe_version: str = "expanded-v1"
    supported_horizons: list[int]
    limitations: list[str]


class ExpandedFeatures(Contract):
    recipe_version: Literal["expanded-v1"] = "expanded-v1"
    region_id: str = Field(min_length=1, max_length=100)
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
