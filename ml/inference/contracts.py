"""Implementar estos puertos al disponer de modelos y reglas validados."""

from typing import Protocol
from datetime import date
from pathlib import Path
from uuid import UUID

from packages.contracts.api import AnalysisRequest, Forecast, Recommendations
from packages.contracts.farms import FarmFeatureBundle
from packages.contracts.training import ModelRelease


class ClimatePredictor(Protocol):
    def predict(self, request: AnalysisRequest, observations: list[dict]) -> Forecast: ...


class SoilPredictor(Protocol):
    def predict(self, request: AnalysisRequest, observations: list[dict], climate: Forecast) -> Forecast: ...


class RecommendationEngine(Protocol):
    def recommend(self, request: AnalysisRequest, climate: Forecast, soil: Forecast) -> Recommendations: ...


class PublishedPredictorFactory(Protocol):
    def create(self, release: ModelRelease, artifact_directory: Path) -> ClimatePredictor | SoilPredictor: ...


# El contexto local conserva su procedencia y requiere alineación/validación antes de su uso.
class FarmContextProvider(Protocol):
    def bundle(self, owner: UUID, farm_id: UUID, cutoff: date) -> FarmFeatureBundle: ...
