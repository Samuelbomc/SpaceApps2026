"""Compatibilidad del servicio; las ejecuciones pertenecen al pipeline del worker."""

from pipelines.recommendations.pipeline import CropRecommendationPipeline

AnalysisService = CropRecommendationPipeline
