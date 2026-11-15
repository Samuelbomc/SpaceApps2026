"""Usa campeones publicados o el bundle experimental explícito; no entrena ni ingiere."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from packages.contracts.api import AnalysisRequest, AnalysisResult
from pipelines.recommendations.pipeline import CropRecommendationPipeline
from pipelines.training.snapshots import fingerprint


class CropRecommendationJob:
    def __init__(
        self,
        observations,
        results,
        registry,
        artifacts,
        *,
        predictor_factory=None,
        engine=None,
        horizons=(7, 15, 30, 60),
        bundled_models=None,
        feature_store=None,
        rotation_engine=None,
    ):
        self.observations, self.results, self.registry, self.artifacts = (
            observations,
            results,
            registry,
            artifacts,
        )
        self.predictor_factory, self.engine, self.horizons = predictor_factory, engine, horizons
        self.bundled_models, self.feature_store = bundled_models, feature_store
        self.rotation_engine = rotation_engine

    def run(self, *, as_of=None):
        today = as_of or datetime.now(ZoneInfo("America/Bogota")).date()
        if today > datetime.now(ZoneInfo("America/Bogota")).date():
            raise ValueError("No se puede ejecutar para una fecha futura.")
        outcomes = []
        bundled_horizons = (
            self.bundled_models.catalog().supported_horizons if self.bundled_models else []
        )
        for region in self.observations.regions():
            region_id = region["region_id"]
            reference = self.observations.latest_observation_date(region_id, today)
            for horizon in self.horizons:
                climate = self.registry.current(f"{region_id}:climate:{horizon}")
                soil = self.registry.current(f"{region_id}:soil:{horizon}")
                if climate is None and soil is None and horizon in bundled_horizons:
                    result = self._bundled(region, today, horizon)
                    if result is not None:
                        outcomes.append(
                            {
                                "region_id": region_id,
                                "horizon_days": horizon,
                                "status": result.status,
                                "analysis_id": result.analysis_id,
                                "messages": result.messages,
                            }
                        )
                        continue
                if climate is None or soil is None:
                    outcomes.append(
                        {
                            "region_id": region_id,
                            "horizon_days": horizon,
                            "status": "pending_model_or_data",
                        }
                    )
                    continue
                if self.predictor_factory is None:
                    outcomes.append(
                        {
                            "region_id": region_id,
                            "horizon_days": horizon,
                            "status": "pending_predictor_adapter",
                        }
                    )
                    continue
                context = None
                factory = self.predictor_factory
                prepared = getattr(factory, "uses_feature_snapshots", False) is True
                if prepared:
                    context = factory.context(region, today, horizon)
                    if context is None:
                        missing = AnalysisResult(
                            status="insufficient_data",
                            request=AnalysisRequest(
                                region_id=region_id,
                                reference_date=today - timedelta(days=3),
                                forecast_start_date=today,
                                horizon_days=horizon,
                            ),
                            messages=[
                                "Hay campeones publicados, pero faltan las variables de entrada recientes completas."
                            ],
                        )
                        CropRecommendationPipeline(
                            self.observations,
                            results_repository=self.results,
                            rotation_engine=self.rotation_engine,
                        ).finalize(missing)
                        outcomes.append(
                            {
                                "region_id": region_id,
                                "horizon_days": horizon,
                                "status": "insufficient_data",
                            }
                        )
                        continue
                    factory = factory.bind(context)
                elif reference is None:
                    outcomes.append(
                        {
                            "region_id": region_id,
                            "horizon_days": horizon,
                            "status": "insufficient_data",
                        }
                    )
                    continue
                # Fijar versiones al comienzo de cada cálculo; no releer el campeón a mitad.
                climate_adapter = factory.create(climate, self.artifacts.verify(climate))
                soil_adapter = factory.create(soil, self.artifacts.verify(soil))
                request = AnalysisRequest(
                    region_id=region_id,
                    reference_date=context.observation_cutoff if prepared else reference,
                    forecast_start_date=today,
                    horizon_days=horizon,
                )
                pipeline = CropRecommendationPipeline(
                    self.observations,
                    climate_adapter,
                    soil_adapter,
                    self.engine,
                    results_repository=self.results,
                    published_versions={"climate": climate.version, "soil": soil.version},
                    require_catalog_version=True,
                    rotation_engine=self.rotation_engine,
                )
                result = (
                    pipeline.run_prepared(request, fingerprint(context.model_dump(mode="json")))
                    if prepared
                    else pipeline.run(request)
                )
                outcomes.append(
                    {
                        "region_id": region_id,
                        "horizon_days": horizon,
                        "status": result.status,
                        "analysis_id": result.analysis_id,
                    }
                )
        return {"status": "ok", "outcomes": outcomes}

    def _bundled(self, region, target_start, horizon):
        snapshot = self.feature_store.load(region, target_start - timedelta(days=1))
        if snapshot is not None:
            result = self.bundled_models.predict(snapshot, horizon_days=horizon)
        else:
            request = AnalysisRequest(
                region_id=region["region_id"],
                reference_date=target_start - timedelta(days=3),
                forecast_start_date=target_start,
                horizon_days=horizon,
            )
            result = AnalysisResult(
                status="insufficient_data",
                request=request,
                analysis_id=fingerprint(
                    {"request": request.model_dump(mode="json"), "missing": "expanded-v1"}
                ),
                messages=[
                    "Los cinco modelos XGBoost están integrados. Faltan las variables procesadas expanded-v1 "
                    "para esta región y fecha: POWER, GPM Late, elevación y, para suelo, SMAP y SoilGrids. "
                    "No se usan filas de otras fechas o ubicaciones."
                ],
            )
        pipeline = CropRecommendationPipeline(
            self.observations, results_repository=self.results, rotation_engine=self.rotation_engine
        )
        return pipeline.finalize(result)
