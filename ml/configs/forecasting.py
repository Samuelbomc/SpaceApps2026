"""Canonical forecast outputs, baseline inputs and default artifact location."""
from pathlib import Path

ARTIFACT_ROOT = Path("ml/artifacts/forecasts")
HORIZONS = (7,15,30,60)
BASELINES = {"temperature_mean":"t2m_mean_7d","temperature_min":"t2m_min_mean_7d",
             "temperature_max":"t2m_max_mean_7d","precipitation":"gpm_late_sum_7d_mm","moisture":"smap_mean_7d"}
UNITS = {"temperature_mean":"C","temperature_min":"C","temperature_max":"C","precipitation":"mm","moisture":"m3/m3"}
