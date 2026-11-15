"""Importación compatible del bundle actual; la receta se valida explícitamente."""

from ml.inference.daily import CLIMATE, HORIZONS, LIMITATIONS, DailyModelBundle

ExpandedModelBundle = DailyModelBundle

__all__ = ["CLIMATE", "HORIZONS", "LIMITATIONS", "ExpandedModelBundle"]
