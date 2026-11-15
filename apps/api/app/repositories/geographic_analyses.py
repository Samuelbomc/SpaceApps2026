"""Cola pública por geometría, periodo y fecha; coalescencia transaccional."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from psycopg.types.json import Jsonb

from apps.api.app.repositories.mongo import DocumentStoreUnavailable
from apps.api.app.services.geographic_selection import selection
from packages.contracts.api import AnalysisResult
from packages.contracts.geographic_analysis import (
    GeographicAnalysis,
    GeographicObservation,
    RegionalReference,
)

RUN_LOCK = 1546052070


class GeographicAnalysisRepository:
    def __init__(self, database):
        self.database = database

    def enqueue(self, request, today):
        area_id, geometry, point, method = selection(request.geometry)
        region_id = "geo-" + area_id
        lon, lat = point["coordinates"]
        with self.database.connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(1546052071)")
            # Límite de presión global; las solicitudes repetidas se reutilizan.
            previous = conn.execute(
                "SELECT request_id FROM geographic_analyses WHERE area_id=%s AND horizon_days=%s AND forecast_start_date=%s",
                (area_id, request.horizon_days, today),
            ).fetchone()
            if previous:
                return previous["request_id"]
            count = conn.execute(
                "SELECT count(*) AS n FROM geographic_analyses WHERE status IN ('queued','running','waiting_inputs','retry_scheduled') AND forecast_start_date >= %s",
                (today,),
            ).fetchone()["n"]
            if count >= 1000:
                raise OverflowError("La cola está ocupada; intenta más tarde.")
            conn.execute(
                "INSERT INTO regions(region_id,name,latitude,longitude) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (region_id, "Área seleccionada", lat, lon),
            )
            conn.execute(
                "INSERT INTO geographic_areas(area_id,region_id,geometry,sampling_point,sampling_method) VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (area_id, region_id, Jsonb(geometry), Jsonb(point), method),
            )
            identifier = uuid4()
            conn.execute(
                "INSERT INTO geographic_analyses(request_id,area_id,horizon_days,forecast_start_date,status,messages) VALUES(%s,%s,%s,%s,'queued',%s)",
                (
                    identifier,
                    area_id,
                    request.horizon_days,
                    today,
                    Jsonb(["Solicitud en cola para el área seleccionada."]),
                ),
            )
            return identifier

    def get(self, identifier, results=None):
        with self.database.connect() as conn:
            row = conn.execute(
                "SELECT q.*,a.geometry,a.sampling_point,a.sampling_method,a.region_id FROM geographic_analyses q JOIN geographic_areas a USING(area_id) WHERE request_id=%s",
                (identifier,),
            ).fetchone()
            observed = (
                conn.execute(
                    """SELECT DISTINCT ON (source,product,variable) body FROM observations
                WHERE region_id=%s AND observed_date<=%s AND source='NASA_POWER'
                AND product='POWER_DAILY' AND body->>'quality'='provider_value_unvalidated'
                AND body->>'value' IS NOT NULL
                ORDER BY source,product,variable,observed_date DESC,(time_standard='LST') DESC""",
                    (row["region_id"], row["forecast_start_date"]),
                ).fetchall()
                if row is not None
                else []
            )
        if row is None:
            return None
        result = None
        if row["analysis_id"] and results is not None:
            result = results.analysis_by_id(row["analysis_id"])
            if result is None:
                raise DocumentStoreUnavailable("El resultado asociado no está disponible.")
            result = AnalysisResult.model_validate(result)
            if (
                result.analysis_id != row["analysis_id"]
                or result.request.region_id != row["region_id"]
                or result.request.horizon_days != row["horizon_days"]
                or result.request.forecast_start_date != row["forecast_start_date"]
            ):
                raise DocumentStoreUnavailable("El resultado no corresponde a la selección.")
        reference = None
        if row["reference_analysis_id"] and results is not None:
            body = results.analysis_by_id(row["reference_analysis_id"])
            if body is None:
                raise DocumentStoreUnavailable("La referencia asociada no está disponible.")
            body = AnalysisResult.model_validate(body)
            if (
                body.analysis_id != row["reference_analysis_id"]
                or body.request.region_id != row["reference_region_id"]
                or body.request.horizon_days != row["horizon_days"]
                or body.request.forecast_start_date != row["reference_start_date"]
            ):
                raise DocumentStoreUnavailable("La referencia no corresponde a la selección.")
            reference = RegionalReference(kind=row["reference_kind"], result=body)
        observations = []
        for entry in observed:
            try:
                observation = GeographicObservation.model_validate(
                    {key: entry["body"].get(key) for key in GeographicObservation.model_fields}
                )
                lon, lat = row["sampling_point"]["coordinates"]
                if (
                    abs(observation.longitude - lon) <= 1e-7
                    and abs(observation.latitude - lat) <= 1e-7
                ):
                    observations.append(observation)
            except (ValueError, TypeError, AttributeError):
                continue
        return GeographicAnalysis(
            **{
                key: row[key]
                for key in GeographicAnalysis.model_fields
                if key not in ("result", "reference", "observations")
            },
            result=result,
            reference=reference,
            observations=observations,
        )

    def next_due(self, conn, now, today):
        # No convertir una emisión histórica pendiente en un pronóstico actual.
        conn.execute(
            "UPDATE geographic_analyses SET status='failed',retry_at=NULL,updated_at=%s,messages=%s WHERE forecast_start_date<%s AND status IN ('queued','running','waiting_inputs','retry_scheduled')",
            (
                now,
                Jsonb(
                    ["La solicitud venció sin entradas completas. Solicita un análisis para hoy."]
                ),
                today,
            ),
        )
        return conn.execute(
            "SELECT q.*,a.region_id FROM geographic_analyses q JOIN geographic_areas a USING(area_id) WHERE forecast_start_date=%s AND status IN ('queued','running','waiting_inputs','retry_scheduled') AND (retry_at IS NULL OR retry_at<=%s) ORDER BY created_at LIMIT 1",
            (today, now),
        ).fetchone()

    def running(self, identifier):
        with self.database.connect() as conn:
            conn.execute(
                "UPDATE geographic_analyses SET status='running',attempts=attempts+1,updated_at=now() WHERE request_id=%s",
                (identifier,),
            )

    def ensure_reference_region(self, region):
        with self.database.connect() as conn:
            conn.execute(
                "INSERT INTO regions(region_id,name,latitude,longitude) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (
                    region["region_id"],
                    "Referencia regional",
                    region["latitude"],
                    region["longitude"],
                ),
            )

    def finish(
        self,
        identifier,
        status,
        messages,
        *,
        analysis_id=None,
        delay=None,
        now=None,
        reference=None,
    ):
        now = now or datetime.now(UTC)
        with self.database.connect() as conn:
            conn.execute(
                "UPDATE geographic_analyses SET status=%s,messages=%s,analysis_id=COALESCE(%s,analysis_id),retry_at=%s,updated_at=%s WHERE request_id=%s",
                (
                    status,
                    Jsonb(messages),
                    analysis_id,
                    now + timedelta(seconds=delay) if delay else None,
                    now,
                    identifier,
                ),
            )
            if reference is not None:
                conn.execute(
                    "UPDATE geographic_analyses SET reference_start_date=%s,reference_analysis_id=%s,reference_kind=%s,reference_region_id=%s WHERE request_id=%s",
                    (
                        reference.result.request.forecast_start_date,
                        reference.result.analysis_id,
                        reference.kind,
                        reference.result.request.region_id,
                        identifier,
                    ),
                )
            elif status == "completed":
                conn.execute(
                    "UPDATE geographic_analyses SET reference_start_date=NULL,reference_analysis_id=NULL,reference_kind=NULL,reference_region_id=NULL WHERE request_id=%s",
                    (identifier,),
                )
