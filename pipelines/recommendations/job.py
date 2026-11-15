"""Usa versiones publicadas; no entrena ni ingiere dentro de la inferencia."""

from datetime import datetime
from zoneinfo import ZoneInfo

from packages.contracts.api import AnalysisRequest
from pipelines.recommendations.pipeline import CropRecommendationPipeline


class CropRecommendationJob:
    def __init__(self, observations, results, registry, artifacts, *, predictor_factory=None,
                 engine=None, horizons=(7, 15, 30, 60)):
        self.observations, self.results, self.registry, self.artifacts = observations, results, registry, artifacts
        self.predictor_factory, self.engine, self.horizons = predictor_factory, engine, horizons

    def run(self):
        today = datetime.now(ZoneInfo("America/Bogota")).date()
        outcomes = []
        for region in self.observations.regions():
            region_id = region["region_id"]
            reference = self.observations.latest_observation_date(region_id, today)
            for horizon in self.horizons:
                climate = self.registry.current(f"{region_id}:climate:{horizon}")
                soil = self.registry.current(f"{region_id}:soil:{horizon}")
                if reference is None or climate is None or soil is None:
                    outcomes.append({"region_id": region_id, "horizon_days": horizon, "status": "pending_model_or_data"})
                    continue
                if self.predictor_factory is None:
                    outcomes.append({"region_id": region_id, "horizon_days": horizon, "status": "pending_predictor_adapter"})
                    continue
                # Fijar versiones al comienzo de cada cálculo; no releer el campeón a mitad.
                climate_adapter = self.predictor_factory.create(climate, self.artifacts.verify(climate))
                soil_adapter = self.predictor_factory.create(soil, self.artifacts.verify(soil))
                request = AnalysisRequest(region_id=region_id, reference_date=reference,
                                          forecast_start_date=today, horizon_days=horizon)
                pipeline = CropRecommendationPipeline(self.observations, climate_adapter, soil_adapter,
                                                       self.engine, results_repository=self.results,
                                                       published_versions={"climate": climate.version, "soil": soil.version},
                                                       require_catalog_version=True)
                result = pipeline.run(request)
                outcomes.append({"region_id": region_id, "horizon_days": horizon, "status": result.status,
                                 "analysis_id": result.analysis_id})
        return {"status": "ok", "outcomes": outcomes}
