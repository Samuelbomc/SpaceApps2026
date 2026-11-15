"""Carga campeones del registro con su receta y un snapshot de entrada fijado."""

from datetime import timedelta
from types import SimpleNamespace

from packages.contracts.api import Forecast, ForecastValue


class RegisteredPredictorFactory:
    uses_feature_snapshots = True

    def __init__(self, trainer, feature_store):
        self.trainer, self.feature_store = trainer, feature_store

    def context(self, region, target_start, horizon):
        snapshot = self.feature_store.load(region, target_start - timedelta(days=1))
        return snapshot if snapshot is not None and snapshot.soil is not None else None

    def bind(self, snapshot):
        return BoundPredictors(self.trainer, snapshot.model_copy(deep=True))


class BoundPredictors:
    def __init__(self, trainer, snapshot):
        self.trainer, self.snapshot = trainer, snapshot

    def create(self, release, directory):
        if release.validation_status != "validated" or release.recipe_version != "expanded-v1":
            raise ValueError(
                "La inferencia operativa requiere una versión publicada y una receta compatible."
            )
        scope = release.spatial_scope
        if scope and (
            not scope["west"] <= self.snapshot.longitude <= scope["east"]
            or not scope["south"] <= self.snapshot.latitude <= scope["north"]
        ):
            raise ValueError("La región no pertenece al ámbito del campeón publicado.")
        model = self.trainer.load(release, directory)
        return RegisteredPredictor(release, model, self.snapshot)


class RegisteredPredictor:
    def __init__(self, release, model, snapshot):
        self.release, self.model, self.snapshot = release, model, snapshot

    def predict(self, request, observations, climate=None):
        release, snapshot = self.release, self.snapshot
        if (
            request.region_id != release.region_id
            or request.region_id != snapshot.region_id
            or request.horizon_days != release.horizon_days
            or request.reference_date != snapshot.observation_cutoff
            or request.forecast_start_date != snapshot.issue_date + timedelta(days=1)
        ):
            raise ValueError("La versión publicada y el snapshot no corresponden a la consulta.")
        if climate is not None and (
            climate.region_id != request.region_id or climate.horizon_days != request.horizon_days
        ):
            raise ValueError("El contexto climático corresponde a otra tarea.")
        # Los modelos existentes de suelo usan clima histórico; no se insertan
        # predicciones climáticas en columnas que no se entrenaron con ellas.
        features = snapshot.climate if release.model_kind == "climate" else snapshot.soil
        if features is None or not set(release.feature_names) <= set(features):
            raise ValueError("Faltan variables de la receta publicada.")
        prediction = self.model.predict([SimpleNamespace(features=features)])[0]
        return Forecast(
            model_kind=release.model_kind,
            model_version=release.version,
            validation_status="validated",
            region_id=request.region_id,
            reference_date=request.reference_date,
            forecast_start_date=request.forecast_start_date,
            horizon_days=request.horizon_days,
            values=[
                ForecastValue(
                    variable="surface_soil_moisture" if target == "moisture" else target,
                    value=value,
                    unit=release.target_units[target],
                    statistic="sum" if target == "precipitation" else "mean",
                    aggregation=f"acumulado de {request.horizon_days} días"
                    if target == "precipitation"
                    else f"media de observaciones válidas de {request.horizon_days} días",
                )
                for target, value in prediction.items()
            ],
            limitations=[
                "La resolución y ámbito corresponden a las fuentes y al registro de entrenamiento.",
                "Las medias de mínimas/máximas no son extremos absolutos ni una trayectoria diaria.",
            ],
        )
