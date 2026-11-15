"""Canonical forecast outputs, baseline inputs and default artifact location."""
from pathlib import Path

ARTIFACT_ROOT = Path("ml/artifacts/forecasts")
HORIZONS = tuple(range(1,61))
BASELINES = {"temperature_mean":"t2m_last_daily","temperature_min":"t2m_min_last_daily",
             "temperature_max":"t2m_max_last_daily","precipitation":"gpm_late_sum_1d_mm","moisture":"smap_mean_7d"}
UNITS = {"temperature_mean":"C","temperature_min":"C","temperature_max":"C","precipitation":"mm","moisture":"m3/m3"}
