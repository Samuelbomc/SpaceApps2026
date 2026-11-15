"""Catálogo de requisitos y evaluación de rangos; no son probabilidades de cosecha."""

from datetime import date
from typing import Literal
from urllib.parse import parse_qs, urlparse

from pydantic import Field, FiniteFloat, model_validator

from packages.contracts.api import Contract


class NumericRange(Contract):
    minimum: FiniteFloat
    maximum: FiniteFloat

    @model_validator(mode="after")
    def ordered(self):
        if self.minimum > self.maximum:
            raise ValueError("El mínimo no puede superar el máximo.")
        return self


class EcologicalRequirement(Contract):
    optimal: NumericRange
    absolute: NumericRange
    unit: Literal["C", "mm/year", "pH"]

    @model_validator(mode="after")
    def nested(self):
        if (
            not self.absolute.minimum
            <= self.optimal.minimum
            <= self.optimal.maximum
            <= self.absolute.maximum
        ):
            raise ValueError("El rango óptimo debe estar dentro del rango absoluto.")
        if self.unit == "pH" and not 0 <= self.absolute.minimum <= self.absolute.maximum <= 14:
            raise ValueError("El pH debe estar entre 0 y 14.")
        if self.unit == "mm/year" and self.absolute.minimum < 0:
            raise ValueError("La precipitación no puede ser negativa.")
        return self


class QualitativeRequirement(Contract):
    optimal: str | None
    absolute: str | None


class CropProfile(Contract):
    crop_id: str
    chain: str
    crop_name: str
    scientific_name: str
    ecocrop_code: int = Field(gt=0)
    source_url: str
    temperature: EcologicalRequirement
    annual_rainfall: EcologicalRequirement
    soil_ph: EcologicalRequirement
    altitude_max_m: FiniteFloat | None = Field(default=None, ge=0)
    cycle_days: NumericRange
    lethal_temperature_rest_c: FiniteFloat | None = None
    lethal_temperature_early_growth_c: FiniteFloat | None = None
    qualitative_soil: dict[str, QualitativeRequirement]
    # Se conservan todos los textos y los valores originales, incluso los ambiguos.
    source_attributes: dict[str, str]
    quality_flags: list[str]

    @model_validator(mode="after")
    def identities_and_units(self):
        url = urlparse(self.source_url)
        if (
            url.scheme != "https"
            or url.netloc != "ecocrop.apps.fao.org"
            or url.path != "/ecocrop/srv/en/dataSheet"
            or parse_qs(url.query).get("id") != [str(self.ecocrop_code)]
        ):
            raise ValueError("El enlace de fuente debe corresponder al código ECOCROP.")
        if (self.temperature.unit, self.annual_rainfall.unit, self.soil_ph.unit) != (
            "C",
            "mm/year",
            "pH",
        ):
            raise ValueError("Las unidades no corresponden a los requisitos del cultivo.")
        if self.cycle_days.minimum <= 0 or any(
            value != int(value) for value in (self.cycle_days.minimum, self.cycle_days.maximum)
        ):
            raise ValueError("El ciclo requiere días enteros positivos.")
        return self


class CropCatalog(Contract):
    schema_version: Literal["ecocrop_catalog_v1"] = "ecocrop_catalog_v1"
    normalizer_version: Literal["ecocrop_tsv_v1"] = "ecocrop_tsv_v1"
    version: str
    source_sha256: str
    review_status: Literal["format_validated_agronomic_review_pending"] = (
        "format_validated_agronomic_review_pending"
    )
    crops: list[CropProfile] = Field(min_length=1)
    limitations: list[str]

    @model_validator(mode="after")
    def unique_profiles(self):
        if len({crop.crop_id for crop in self.crops}) != len(self.crops):
            raise ValueError("Los perfiles de cultivo deben tener identificadores únicos.")
        return self


class TemperatureEvidence(Contract):
    mean_c: FiniteFloat
    start: date
    end: date
    kind: Literal["historical", "forecast"]
    source: str = Field(min_length=1)

    @model_validator(mode="after")
    def dates(self):
        if self.start > self.end:
            raise ValueError("El periodo de temperatura es inválido.")
        return self


class AnnualRainfallEvidence(Contract):
    total_mm: FiniteFloat = Field(ge=0)
    start: date
    end: date
    valid_days: int = Field(ge=0, le=366)
    source: str = Field(min_length=1)

    @model_validator(mode="after")
    def annual_period(self):
        days = (self.end - self.start).days + 1
        if days not in (365, 366) or self.valid_days > days:
            raise ValueError(
                "La lluvia anual requiere un periodo de 365/366 días y cobertura explícita."
            )
        return self


class CropScreeningContext(Contract):
    region_id: str = Field(min_length=1)
    as_of: date
    temperature: TemperatureEvidence | None = None
    annual_rainfall: AnnualRainfallEvidence | None = None
    soil_ph: FiniteFloat | None = Field(default=None, ge=0, le=14)
    altitude_m: FiniteFloat | None = Field(default=None, ge=-500, le=9000)

    @model_validator(mode="after")
    def no_future_observations(self):
        if self.annual_rainfall and self.annual_rainfall.end >= self.as_of:
            raise ValueError("La precipitación histórica debe terminar antes de la consulta.")
        if self.temperature:
            if self.temperature.kind == "historical" and self.temperature.end >= self.as_of:
                raise ValueError("La temperatura histórica debe terminar antes de la consulta.")
            if self.temperature.kind == "forecast" and self.temperature.start < self.as_of:
                raise ValueError("El pronóstico debe comenzar a partir de la consulta.")
        return self


class RequirementCheck(Contract):
    variable: Literal["temperature", "annual_rainfall", "soil_ph", "altitude"]
    status: Literal["optimal", "within_absolute", "outside_absolute", "unknown"]
    value: FiniteFloat | None
    unit: str
    explanation: str


class CropScreening(Contract):
    crop_id: str
    crop_name: str
    chain: str
    ecocrop_code: int
    status: Literal["outside_checked_ranges", "insufficient_data", "within_checked_ranges"]
    checks: list[RequirementCheck]
    limitations: list[str]
    recommendation_ready: Literal[False] = False


class CropScreeningReport(Contract):
    catalog_version: str
    rule_version: str
    input_snapshot_id: str
    context: CropScreeningContext
    crops: list[CropScreening]
    rotations_evaluated: Literal[False] = False
