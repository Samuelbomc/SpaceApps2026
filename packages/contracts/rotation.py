"""Reglas de agua por cultivo y periodo; nunca se deducen de mm/año."""

from typing import Literal

from pydantic import Field, FiniteFloat, model_validator

from packages.contracts.api import Contract


class WaterRequirement(Contract):
    crop_id: str
    horizon_days: Literal[7, 15, 30, 60]
    precipitation_min_mm: FiniteFloat = Field(ge=0)
    precipitation_max_mm: FiniteFloat = Field(ge=0)
    surface_moisture_min: FiniteFloat = Field(ge=0, le=1)
    surface_moisture_max: FiniteFloat = Field(ge=0, le=1)
    source: str = Field(min_length=1)

    @model_validator(mode='after')
    def ordered(self):
        if (self.precipitation_min_mm > self.precipitation_max_mm or
                self.surface_moisture_min > self.surface_moisture_max):
            raise ValueError('Los límites de agua deben estar ordenados.')
        return self


class RotationWaterRules(Contract):
    version: str = Field(min_length=1)
    review_status: Literal['pending', 'reviewed']
    requirements: list[WaterRequirement] = Field(default_factory=list)

    @model_validator(mode='after')
    def unique_rules(self):
        keys = [(r.crop_id, r.horizon_days) for r in self.requirements]
        if len(set(keys)) != len(keys):
            raise ValueError('Hay reglas duplicadas para el mismo cultivo y horizonte.')
        return self
