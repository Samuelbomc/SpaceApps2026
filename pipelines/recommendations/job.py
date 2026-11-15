"""Usa campeones publicados o el bundle experimental explícito; no entrena ni ingiere."""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from packages.contracts.api import AnalysisRequest, AnalysisResult
from pipelines.recommendations.pipeline import CropRecommendationPipeline
from pipelines.training.snapshots import fingerprint

LOG = logging.getLogger("agrogeo.recommendations")


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

    def run(self, *, as_of=None, tasks=None):
        today = as_of or datetime.now(ZoneInfo("America/Bogota")).date()
        if today > datetime.now(ZoneInfo("America/Bogota")).date():
            raise ValueError("No se puede ejecutar para una fecha futura.")
        selected = (
            {(task["region_id"], task["horizon_days"]) for task in tasks}
            if tasks is not None
            else None
        )
        outcomes, failures = [], []
        for region in self.observations.regions():
            region_id = region["region_id"]
            for horizon in self.horizons:
                if selected is not None and (region_id, horizon) not in selected:
                    continue
                try:
                    outcome = self._run_task(region, today, horizon)
                except Exception as exc:
                    # No persistir un análisis incompleto ni exponer el mensaje externo.
                    # El scheduler conserva las tareas fallidas para su reintento durable.
                    failures.append({"region_id": region_id, "horizon_days": horizon})
                    outcome = {
                        "status": "failed",
                        "error_type": type(exc).__name__,
                        "message": "La tarea falló; se conserva el resultado anterior.",
                    }
                    LOG.error(
                        "Falló la región %s, horizonte %s (%s)",
                        region_id,
                        horizon,
                        type(exc).__name__,
                    )
                outcomes.append({"region_id": region_id, "horizon_days": horizon, **outcome})
        return {
            "status": "partial" if failures else "ok",
            "forecast_start_date": today.isoformat(),
            "failed_tasks": failures,
            "outcomes": outcomes,
        }

    def _run_task(self, region, today, horizon):
        region_id = region["region_id"]
        if getattr(self.bundled_models, "forecast_type", None) == "direct_daily":
            result = self._bundled(region, today, horizon)
            return {
                "status": result.status,
                "analysis_id": result.analysis_id,
                "messages": result.messages,
            }
        climate = self.registry.current(f"{region_id}:climate:{horizon}")
        soil = self.registry.current(f"{region_id}:soil:{horizon}")
        if (
            climate is None
            and soil is None
            and self.bundled_models is not None
            and self.bundled_models.supports(horizon)
        ):
            result = self._bundled(region, today, horizon)
            return {
                "status": result.status,
                "analysis_id": result.analysis_id,
                "messages": result.messages,
            }
        if climate is None or soil is None:
            return {"status": "pending_model_or_data"}
        if self.predictor_factory is None:
            return {"status": "pending_predictor_adapter"}
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
                return {"status": "insufficient_data"}
            factory = factory.bind(context)
            reference = context.observation_cutoff
        else:
            reference = self.observations.latest_observation_date(region_id, today)
            if reference is None:
                return {"status": "insufficient_data"}
        # Fijar versiones al comienzo de cada cálculo; no releer el campeón a mitad.
        climate_adapter = factory.create(climate, self.artifacts.verify(climate))
        soil_adapter = factory.create(soil, self.artifacts.verify(soil))
        request = AnalysisRequest(
            region_id=region_id,
            reference_date=reference,
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
        return {"status": result.status, "analysis_id": result.analysis_id}

    def _bundled(self, region, target_start, horizon, *, matched=None):
        snapshot = (
            matched.snapshot
            if matched is not None
            else self.feature_store.load(region, target_start - timedelta(days=1))
        )
        if snapshot is not None:
            if matched is not None:
                if matched.spatial.issue_date != target_start - timedelta(days=1):
                    raise ValueError(
                        "La referencia cercana debe conservar la fecha de emisión requerida."
                    )
                if (
                    matched.spatial.source_sha256 != snapshot.source_sha256
                    or matched.spatial.issue_date != snapshot.issue_date
                    or matched.spatial.source_point_id != snapshot.point_id
                    or matched.spatial.used_longitude != snapshot.longitude
                    or matched.spatial.used_latitude != snapshot.latitude
                    or matched.spatial.requested_longitude != region["longitude"]
                    or matched.spatial.requested_latitude != region["latitude"]
                ):
                    raise ValueError(
                        "La referencia espacial no coincide con las entradas y la selección."
                    )
                result = self.bundled_models.predict(
                    snapshot, horizon_days=horizon, analysis_region_id=region["region_id"]
                )
                result.spatial_match = matched.spatial
                if matched.spatial.method == "nearest":
                    result.messages.insert(
                        0,
                        f"Estimación con datos del punto disponible más cercano, a {matched.spatial.distance_km:.1f} km de tu selección.",
                    )
            else:
                result = self.bundled_models.predict(snapshot, horizon_days=horizon)
        else:
            daily = getattr(self.bundled_models, "forecast_type", None) == "direct_daily"
            recipe = "daily-direct-1-60-v1" if daily else "expanded-v1"
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
                    {"request": request.model_dump(mode="json"), "missing": recipe}
                ),
                messages=[
                    f"Los modelos XGBoost están disponibles, pero no hay una entrada procesada {recipe} "
                    f"para {region['region_id']} con emisión {(target_start - timedelta(days=1)).isoformat()}. "
                    "El histórico de entrenamiento y los valores observados de la pantalla no sustituyen esta entrada.",
                    "La receta diaria requiere POWER en LST, lluvia GPM Late y elevación; "
                    "para suelo también SMAP y SoilGrids. Meteorología hasta emisión menos 2 días "
                    "y radiación hasta emisión menos 7 días. Los ejemplos incluidos corresponden "
                    "a sus propias coordenadas y fechas; no se reasignan a esta ubicación."
                    if daily
                    else "Se requieren POWER, GPM Late, elevación y, para suelo, SMAP y SoilGrids.",
                ],
            )
        pipeline = CropRecommendationPipeline(
            self.observations, results_repository=self.results, rotation_engine=self.rotation_engine
        )
        return pipeline.finalize(result)
