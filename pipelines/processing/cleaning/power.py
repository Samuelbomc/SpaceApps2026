"""Normalización opcional de POWER, separada de sus clientes de acceso."""

from packages.contracts import BoundingBox, DateRange
from pipelines.ingestion.http import IngestionError


def normalize_power_daily(raw: dict) -> dict:
    """Filtra puntos al bbox solicitado y transforma sentinelas; no modifica el original."""
    period = DateRange.parse(raw["period"]["start"], raw["period"]["end"])
    bounds = raw["bbox"]
    bbox = BoundingBox(*(bounds[key] for key in ("west", "south", "east", "north")))
    records = []
    for item in raw["raw_responses"]:
        payload = item["response"]
        parameter = item["query"]["parameters"]
        header = payload["header"]
        missing = header.get("fill_value", -999)
        metadata = payload.get("parameters", {}).get(parameter, {})
        for feature in payload["features"]:
            try:
                lon, lat = feature["geometry"]["coordinates"][:2]
                series = feature["properties"]["parameter"][parameter]
            except (KeyError, TypeError, ValueError):
                raise IngestionError("Estructura regional POWER inesperada.") from None
            if not (bbox.west <= lon <= bbox.east and bbox.south <= lat <= bbox.north):
                continue
            for day, value in sorted(series.items()):
                if not period.start.strftime("%Y%m%d") <= day <= period.end.strftime("%Y%m%d"):
                    continue
                is_missing = value is None or value == missing
                records.append({
                    "source": "NASA_POWER", "date": f"{day[:4]}-{day[4:6]}-{day[6:]}",
                    "longitude": lon, "latitude": lat, "variable": parameter,
                    "value": None if is_missing else value, "unit": metadata.get("units"),
                    "quality": "missing" if is_missing else "provider_value_unvalidated",
                    "time_standard": "UTC", "data_kind": "historical",
                    "resolution": (
                        "1 x 1 degree" if parameter == "ALLSKY_SFC_SW_DWN" else
                        "0.5 x 0.625 degree" if parameter in
                        ("T2M", "T2M_MIN", "T2M_MAX", "RH2M", "WS2M") else
                        "parameter-dependent; see provider documentation"
                    ),
                    "source_version": header.get("api", {}).get("version"),
                })
    return {**raw, "records": records,
            "notes": "Ventana de consulta ampliada al mínimo de POWER (2 grados por eje); "
                     "solo se conservan puntos devueltos dentro del bbox original. "
                     "No es un promedio regional ni un recorte de píxeles. Meteorología "
                     "0.5 x 0.625 grados, solar 1 x 1 grado: la malla de respuesta no "
                     "aumenta la resolución de origen. Metadatos en raw_responses."}
