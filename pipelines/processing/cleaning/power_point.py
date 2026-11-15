"""Procesa respuestas puntuales POWER sin imputación ni ingeniería de features."""

import hashlib
import json
from datetime import datetime, timedelta
from math import isfinite

from packages.contracts import DateRange, GeoPoint
from packages.contracts.observations import PowerObservation, power_location_id
from pipelines.ingestion.http import IngestionError


def process_power_point(raw: dict) -> list[PowerObservation]:
    try:
        point = GeoPoint(raw["point"]["latitude"], raw["point"]["longitude"])
        period = DateRange.parse(raw["period"]["start"], raw["period"]["end"])
        responses = raw["raw_responses"]
        retrieved_at = raw["retrieved_at"]
    except (KeyError, TypeError, ValueError):
        raise IngestionError("El procesador puntual requiere point, period y respuestas originales válidas.") from None
    records = {}
    for item in responses:
        try:
            payload = item["response"]
            header = payload["header"]
            if header["time_standard"] != "UTC":
                raise IngestionError("La respuesta POWER no está en UTC.")
            lon, lat = payload["geometry"]["coordinates"][:2]
            GeoPoint(lat, lon)
            parameters = tuple(dict.fromkeys(item["query"]["parameters"].split(",")))
            series_by_variable = payload["properties"]["parameter"]
            metadata = payload["parameters"]
            api = header.get("api") or {}
            if not isinstance(series_by_variable, dict) or not isinstance(metadata, dict) or not isinstance(api, dict):
                raise TypeError
        except (KeyError, TypeError, ValueError, AttributeError):
            raise IngestionError("Respuesta puntual POWER mal formada o con geometría inválida.") from None
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        for variable in parameters:
            parameter_metadata = metadata.get(variable)
            unit = parameter_metadata.get("units") if isinstance(parameter_metadata, dict) else None
            if not isinstance(unit, str) or not unit:
                raise IngestionError(f"POWER no reportó unidades para {variable}.")
            series = series_by_variable.get(variable, {})
            if not isinstance(series, dict):
                raise IngestionError(f"La serie POWER de {variable} no es un objeto por fechas.")
            try:
                for day_key in series:
                    if not isinstance(day_key, str) or len(day_key) != 8:
                        raise ValueError
                    datetime.strptime(day_key, "%Y%m%d")
            except ValueError:
                raise IngestionError(f"La serie POWER de {variable} contiene fechas inválidas.") from None
            day = period.start
            while day <= period.end:
                value_raw = series.get(day.strftime("%Y%m%d"))
                value, quality = None, "missing"
                if value_raw is not None and value_raw != header.get("fill_value", -999):
                    if isinstance(value_raw, (int, float)) and not isinstance(value_raw, bool) and isfinite(value_raw):
                        value, quality = float(value_raw), "provider_value_unvalidated"
                        if ((variable == "RH2M" and unit == "%" and not 0 <= value <= 100)
                                or (variable in ("WS2M", "WS10M", "ALLSKY_SFC_SW_DWN") and value < 0)):
                            quality = "out_of_range"
                    else:
                        quality = "invalid_value"
                resolution = ("1 x 1 degree" if variable == "ALLSKY_SFC_SW_DWN" else
                              "0.5 x 0.625 degree" if variable in
                              ("T2M", "T2M_MIN", "T2M_MAX", "RH2M", "WS2M", "WS10M") else "provider-defined")
                record: PowerObservation = {
                    "source": "NASA_POWER", "product": "POWER_DAILY",
                    "product_version": header.get("product_version"),
                    "api_version": api.get("version"),
                    "location_id": power_location_id(point), "cell_id": None,
                    "latitude": float(point.latitude), "longitude": float(point.longitude),
                    "response_latitude": float(lat), "response_longitude": float(lon),
                    "date": day.isoformat(), "variable": variable, "value": value,
                    "raw_value": json.dumps(value_raw) if value_raw is not None else None,
                    "unit": unit, "quality": quality, "time_standard": "UTC", "resolution": resolution,
                    "retrieved_at": retrieved_at, "data_sources": json.dumps(header.get("sources", [])),
                    "response_sha256": digest, "raw_path": None,
                }
                key = (record["date"], variable)
                if key in records and records[key] != record:
                    raise IngestionError("Respuestas POWER contradictorias para la misma fecha y variable.")
                records[key] = record
                day += timedelta(days=1)
    return [records[key] for key in sorted(records)]
