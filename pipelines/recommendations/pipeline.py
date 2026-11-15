"""Conecta los puertos futuros sin inventar salidas cuando no hay modelos."""

import hashlib
import json
from datetime import timedelta

from ml.inference.contracts import ClimatePredictor, RecommendationEngine, SoilPredictor
from packages.contracts.api import AnalysisRequest, AnalysisResult


class CropRecommendationPipeline:
    def __init__(self, repository, climate: ClimatePredictor | None = None,
                 soil: SoilPredictor | None = None, recommendations: RecommendationEngine | None = None,
                 results_repository=None, published_versions=None, require_catalog_version=False):
        self.repository, self.climate, self.soil, self.recommendations = repository, climate, soil, recommendations
        self.results = results_repository if results_repository is not None else repository
        self.published_versions = published_versions or {}
        self.require_catalog_version = require_catalog_version

    @staticmethod
    def _validate_forecast(forecast, request, kind):
        if (forecast.model_kind != kind or forecast.region_id != request.region_id or
                forecast.reference_date != request.reference_date or forecast.horizon_days != request.horizon_days):
            raise ValueError("El modelo devolvió una predicción que no corresponde a la consulta.")
        if (forecast.forecast_start_date or forecast.reference_date + timedelta(days=1)) != (request.forecast_start_date or request.reference_date + timedelta(days=1)):
            raise ValueError("El modelo devolvió un periodo objetivo distinto del solicitado.")

    def run(self, request: AnalysisRequest) -> AnalysisResult:
        result = AnalysisResult(status="pending_model", request=request)
        if self.climate is None or self.soil is None:
            result.messages = ["Los modelos climático y de suelo aún no están configurados."]
            return result
        # Ventana de contrato inicial; cada futuro modelo debe declarar sus lags.
        observations = self.repository.observations(request.region_id,
                                                    request.reference_date - timedelta(days=89), request.reference_date, 10000)
        observations = [r for r in observations if r.get("value") is not None and r.get("quality") == "provider_value_unvalidated"]
        observations.sort(key=lambda r: (r.get("source", ""), r.get("product", ""), r["date"], r["variable"]))
        if not observations:
            result.status, result.messages = "insufficient_data", ["No hay observaciones válidas para el periodo de entrada."]
            return result
        result.input_snapshot_id = hashlib.sha256(json.dumps(observations, sort_keys=True, default=str).encode()).hexdigest()
        result.climate = self.climate.predict(request, observations)
        self._validate_forecast(result.climate, request, "climate")
        self._validate_version(result.climate)
        result.soil = self.soil.predict(request, observations, result.climate)
        self._validate_forecast(result.soil, request, "soil")
        self._validate_version(result.soil)
        result.status = "pending_recommendations"
        if self.recommendations is not None:
            result.recommendations = self.recommendations.recommend(request, result.climate, result.soil)
            if self.require_catalog_version and not result.recommendations.catalog_version:
                raise ValueError("El motor debe identificar la versión del catálogo agronómico utilizado.")
            result.status = "ready"
        identity = {"request": request.model_dump(mode="json"), "inputs": result.input_snapshot_id,
                    "climate": result.climate.model_version, "soil": result.soil.model_version,
                    "engine": result.recommendations.engine_version if result.recommendations else None,
                    "catalog": result.recommendations.catalog_version if result.recommendations else None}
        result.analysis_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        self.results.save_analysis(result)
        return result

    def _validate_version(self, forecast):
        expected = self.published_versions.get(forecast.model_kind)
        if expected is not None and forecast.model_version != expected:
            raise ValueError("El adapter no usó la versión publicada fijada al iniciar el cálculo.")
