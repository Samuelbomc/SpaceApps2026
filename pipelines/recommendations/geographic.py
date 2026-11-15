"""Consumidor geográfico: entrada compatible, inferencia y persistencia fuera de HTTP."""

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from apps.api.app.repositories.geographic_analyses import RUN_LOCK, GeographicAnalysisRepository
from packages.contracts.geographic_analysis import RegionalReference

LOG = logging.getLogger("agrogeo.geographic")


class GeographicAnalysisJob:
    def __init__(
        self,
        database,
        observations,
        inputs,
        recommendations,
        ingestion,
        references=None,
        preparation=None,
    ):
        self.database, self.observations, self.inputs = database, observations, inputs
        self.recommendations, self.ingestion = recommendations, ingestion
        self.queue = GeographicAnalysisRepository(database)
        self.references = references
        self.preparation = preparation

    def _reference(self, region, task, today):
        available = self.references.resolve(region, today)
        if available is None:
            return None
        reference_region = {**region, "region_id": "geo-reference-" + task["area_id"]}
        self.queue.ensure_reference_region(reference_region)
        result = self.recommendations._bundled(
            reference_region,
            available.matched.snapshot.issue_date + timedelta(days=1),
            task["horizon_days"],
            matched=available.matched,
        )
        return RegionalReference(kind=available.kind, result=result)

    def run(self, *, now=None):
        fixed_now = now

        def clock():
            return fixed_now if fixed_now is not None else datetime.now(UTC)

        now = clock()
        today = now.astimezone(ZoneInfo("America/Bogota")).date()
        with self.database.connect(autocommit=True) as conn:
            if not conn.execute(
                "SELECT pg_try_advisory_lock(%s) AS locked", (RUN_LOCK,)
            ).fetchone()["locked"]:
                return "locked"
            try:
                task = self.queue.next_due(conn, now, today)
                if task is None:
                    return "not_due"
                identifier = task["request_id"]
                self.queue.running(identifier)
                try:
                    missing_delay = 3600
                    region = self.observations.region(task["region_id"])
                    matched = self.inputs.resolve(region, today - timedelta(days=1))
                    reference = None
                    try:
                        if (
                            matched is None
                            or matched.snapshot.soil is None
                            or matched.spatial.method != "exact"
                        ) and self.references is not None:
                            reference = self._reference(region, task, today)
                        if reference is not None:
                            # La referencia queda disponible durante las consultas externas.
                            self.queue.finish(
                                identifier, "running", [], now=clock(), reference=reference
                            )
                    except Exception as exc:
                        LOG.warning(
                            "Referencia no disponible (%s); continúa la adquisición del punto.",
                            type(exc).__name__,
                        )
                        reference = None
                    # Una referencia cercana no evita consultar las APIs para ESTE punto.
                    if self.preparation is not None and (
                        matched is None
                        or matched.snapshot.soil is None
                        or matched.spatial.method != "exact"
                    ):
                        preparation = self.preparation.prepare(region, today - timedelta(days=1))
                        # Cada proveedor conserva su espera. Otro proveedor listo
                        # puede avanzar sin esperar el Retry-After más largo.
                        missing_delay = (
                            max(1, preparation["next_attempt_seconds"])
                            if "next_attempt_seconds" in preparation
                            else max(missing_delay, preparation.get("retry_after_seconds", 0))
                        )
                        matched = self.inputs.resolve(region, today - timedelta(days=1))
                        if self.references is not None and (
                            matched is None
                            or matched.snapshot.soil is None
                            or matched.spatial.method != "exact"
                        ):
                            try:
                                # La adquisición puede publicar ahora un corte completo
                                # anterior de ESTE punto; usarlo en esta misma ejecución.
                                reference = self._reference(region, task, today) or reference
                            except Exception as exc:
                                LOG.warning("Referencia conservada (%s).", type(exc).__name__)
                    if (
                        self.preparation is None
                        and (matched is None or matched.snapshot.soil is None)
                        and reference is None
                    ):
                        # Descarga/publica observaciones de ESTA ubicación; consultar
                        # catálogos no equivale a extraer sus valores para XGBoost.
                        ingestion = self.ingestion.run(region_id=region["region_id"])
                        if isinstance(ingestion, dict):
                            missing_delay = max(
                                missing_delay,
                                max(
                                    (
                                        entry.get("retry_after_seconds", 0)
                                        for entry in ingestion.get("summary", {}).values()
                                        if isinstance(entry, dict)
                                    ),
                                    default=0,
                                ),
                            )
                        matched = self.inputs.resolve(region, today - timedelta(days=1))
                    result = self.recommendations._bundled(
                        region, today, task["horizon_days"], matched=matched
                    )
                    if (
                        result.request.region_id != region["region_id"]
                        or result.request.forecast_start_date != today
                        or result.request.horizon_days != task["horizon_days"]
                    ):
                        raise ValueError(
                            "El resultado no corresponde a la ubicación o periodo solicitados."
                        )
                    complete = result.climate is not None and result.soil is not None
                    if self.preparation is not None and (
                        matched is None or matched.spatial.method != "exact"
                    ):
                        # Mostrar la referencia no cancela la preparación del punto real.
                        complete = False
                    if complete:
                        reference = None
                    self.queue.finish(
                        identifier,
                        "completed" if complete else "waiting_inputs",
                        result.messages,
                        analysis_id=result.analysis_id,
                        delay=None if complete else missing_delay,
                        now=clock(),
                        reference=reference,
                    )
                    return "completed" if complete else "waiting_inputs"
                except Exception as exc:
                    LOG.error("Análisis geográfico pendiente (%s)", type(exc).__name__)
                    delay = max(
                        min(3600, 60 * 2 ** min(task["attempts"], 6)),
                        getattr(exc, "retry_after_seconds", 0),
                    )
                    self.queue.finish(
                        identifier,
                        "retry_scheduled",
                        ["La preparación no pudo completarse; se reintentará automáticamente."],
                        delay=delay,
                        now=clock(),
                    )
                    return "retry_scheduled"
            finally:
                conn.execute("SELECT pg_advisory_unlock(%s)", (RUN_LOCK,))
