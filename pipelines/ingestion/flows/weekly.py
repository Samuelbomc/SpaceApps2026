"""Job incremental: POWER procesado, catálogos del resto y persistencia operativa."""

import os
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apps.api.app.repositories.operational import OperationalRepository
from apps.api.app.services.nasa_data import NASADataService
from packages.contracts import DataQuery, DateRange, GeoPoint
from pipelines.ingestion.date_fallback import fetch_with_date_fallback
from pipelines.ingestion.flows.power import PowerIngestionFlow
from pipelines.ingestion.sources.nasa.catalog import PRODUCTS


class WeeklyIngestionJob:
    def __init__(
        self, repository: OperationalRepository, flow=None, catalogs=None, *, max_lag_days=None
    ):
        self.repository = repository
        self.flow = flow if flow is not None else PowerIngestionFlow()
        self.catalogs = catalogs if catalogs is not None else NASADataService()
        self.max_lag_days = (
            int(os.getenv("SOURCE_FALLBACK_MAX_LAG_DAYS", "5"))
            if max_lag_days is None
            else max_lag_days
        )
        if type(self.max_lag_days) is not int or not 1 <= self.max_lag_days <= 30:
            raise ValueError("El margen máximo de consulta debe estar entre 1 y 30 días.")

    def run(self, *, sources=None, region_id=None):
        selected = tuple(dict.fromkeys(sources)) if sources is not None else ("power", *PRODUCTS)
        if not selected or any(source not in ("power", *PRODUCTS) for source in selected):
            raise ValueError("Fuentes de ingesta inválidas.")
        region_id = region_id or os.getenv("REGION_ID", "antioquia-reference")
        region = self.repository.region(region_id)
        if region is None:
            raise RuntimeError("Región del job no registrada; ejecuta las migraciones.")
        lookback = int(os.getenv("RECENT_OBSERVATION_DAYS", "90"))
        lag = int(os.getenv("INGESTION_LAG_DAYS", "3"))
        if not 7 <= lookback <= 366 or not 1 <= lag <= 30:
            raise ValueError("Ventana reciente entre 7 y 366 días; latencia entre 1 y 30 días.")
        point = GeoPoint(region["latitude"], region["longitude"])
        requested_on = datetime.now(ZoneInfo("America/Bogota")).date()
        end = requested_on - timedelta(days=lag)
        period = DateRange(end - timedelta(days=lookback - 1), end)
        query = DataQuery(point=point, period=period, limit=3)
        run_id = str(uuid.uuid4())
        self.repository.start_run(run_id, region_id)
        summary, failures = {}, []
        try:
            if "power" in selected:
                try:

                    def fetch_power(selected):
                        selected_query = DataQuery(point=point, period=selected, limit=3)
                        result = (
                            self.flow.run(selected_query)
                            if selected.end == period.end
                            else self.flow.run(selected_query, refresh_days=0)
                        )
                        rows = self.flow.repository.read(point, selected)
                        self.repository.store_recent(region_id, rows, period.start)
                        return result

                    result, used_period, attempts = fetch_with_date_fallback(
                        fetch_power,
                        period,
                        requested_on,
                        usable=lambda body: body["status"] == "ok",
                        max_lag_days=self.max_lag_days,
                    )
                    summary["power"] = {
                        **result,
                        "query_end": used_period.end.isoformat(),
                        "attempted_end_dates": attempts,
                    }
                    if summary["power"]["status"] != "ok":
                        failures.append("power")
                except Exception as exc:
                    failures.append("power")
                    summary["power"] = {
                        "status": "failed",
                        "error_type": type(exc).__name__,
                        "retry_after_seconds": getattr(exc, "retry_after_seconds", 0),
                    }
            # Aislar cada fuente también ante errores inesperados o de persistencia.
            for source in selected:
                if source == "power":
                    continue
                try:
                    payload = self.catalogs.fetch(query, sources=(source,))["sources"][source]
                    self.repository.snapshot(run_id, source, payload)
                    summary[source] = {
                        "status": payload["status"],
                        "data_kind": payload["data_kind"],
                        "granules": len((payload.get("data") or {}).get("granules", [])),
                        "retry_after_seconds": payload.get("metadata", {}).get(
                            "retry_after_seconds", 0
                        ),
                    }
                    if payload["status"] == "error":
                        failures.append(source)
                except Exception as exc:
                    failures.append(source)
                    summary[source] = {"status": "failed", "error_type": type(exc).__name__}
            summary["downstream"] = {
                "status": "retry_sources" if failures else "history_updated",
                "message": "El entrenamiento y las recomendaciones se coordinan en jobs independientes.",
            }
            status = "partial" if failures else "ok"
            summary["failed_sources"] = failures
            self.repository.finish_run(run_id, status, summary)
            return {"run_id": run_id, "status": status, "summary": summary}
        except Exception:
            self.repository.finish_run(
                run_id, "failed", {"error": "La ejecución no pudo completarse."}
            )
            raise
