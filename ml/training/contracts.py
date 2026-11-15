"""Puertos de features, entrenamiento y registro para los pipelines autónomos."""

from pathlib import Path
from typing import Protocol

from packages.contracts.training import DatasetSnapshot, LabeledSample, ModelRelease, PreparedDataset


class TrainingDatasetBuilder(Protocol):
    # Cambiar esta versión cuando cambien features, targets o controles de calidad.
    version: str

    def build(self, snapshot: DatasetSnapshot, observations_path: Path,
              model_kind: str, horizon_days: int) -> PreparedDataset: ...


class FittedRegressor(Protocol):
    def predict(self, samples: list[LabeledSample]) -> list[dict[str, float]]: ...

    def save(self, directory: Path) -> None: ...


class CandidateTrainer(Protocol):
    version: str

    def fit(self, dataset: PreparedDataset, samples: list[LabeledSample]) -> FittedRegressor: ...

    def load(self, release: ModelRelease, directory: Path) -> FittedRegressor: ...


class ModelRegistry(Protocol):
    def current(self, slot: str) -> ModelRelease | None: ...

    def published_models(self) -> list[ModelRelease]: ...

    def attempt(self, fingerprint: str) -> dict | None: ...

    def record_attempt(self, fingerprint: str, body: dict) -> None: ...

    def publish(self, release: ModelRelease, expected_version: str | None) -> bool: ...

    def record_outcomes(self, outcomes: list[dict]) -> None: ...

    def recent_training(self) -> list[dict]: ...
