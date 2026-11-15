"""Procesa la cola manual fuera de HTTP y comparte los locks/reintentos de los jobs."""

import logging
from collections import Counter
from datetime import UTC, datetime, timedelta

from apps.api.app.repositories.manual_updates import PHASES, RUN_LOCK, ManualUpdateRepository
from apps.api.app.repositories.operational import OperationalRepository
from packages.contracts.manual_update import UpdateStage

LOG = logging.getLogger("agrogeo.manual")
JOB_KEYS = {
    "ingestion": "nasa-weekly",
    "training": "model-training",
    "recommendations": "crop-recommendations",
}
RUNNING_MESSAGES = {
    "ingestion": "Consultando NASA y actualizando observaciones.",
    "training": "Evaluando datos y versiones candidatas de los modelos.",
    "recommendations": "Recalculando análisis con los modelos disponibles.",
}


class CaptureJob:
    def __init__(self, job):
        self.job, self.result, self.calls = job, None, 0

    def run(self, **kwargs):
        self.calls += 1
        self.result = self.job.run(**kwargs)
        return self.result


def stage_summary(phase, result):
    stage = UpdateStage(phase=phase, status="completed", message="Etapa completada.")
    if phase == "ingestion":
        stage.message = "Consultas NASA completadas; se conservaron las observaciones disponibles."
        stage.limitations = [
            "La ingesta procesa POWER y consulta catálogos de otras fuentes. El procesamiento multifuente de entradas XGBoost aún debe completarse."
        ]
    else:
        stage.counts = dict(Counter(item["status"] for item in result.get("outcomes", [])))
        if phase == "training":
            published = result.get("published", 0)
            stage.message = f"Versiones nuevas publicadas: {published}."
            if any(key not in ("published", "unchanged") for key in stage.counts):
                stage.limitations = [
                    "Algunas tareas no publicaron modelos: faltan datos, revisión o criterios de validación. Se conserva la versión vigente."
                ]
        else:
            ready = stage.counts.get("ready", 0)
            stage.message = f"Análisis revisados: {sum(stage.counts.values())}. Recomendaciones aprobadas: {ready}."
            if any(key != "ready" for key in stage.counts):
                stage.limitations = [
                    "Hay periodos sin predicción completa o con evaluación agronómica pendiente. Consulta su estado en los resultados."
                ]
    return stage.model_dump(mode="json")


def poll_manual_updates(
    database, factory, *, ingestion_runner=None, background_runner=None, now=None
):
    if ingestion_runner is None:
        from scripts.worker import poll_once

        ingestion_runner = poll_once
    if background_runner is None:
        from pipelines.scheduling.runner import poll_background

        background_runner = poll_background
    repository = ManualUpdateRepository(database)
    operational = OperationalRepository(database)
    now = now or datetime.now(UTC)
    with database.connect(autocommit=True) as conn:
        if not conn.execute("SELECT pg_try_advisory_lock(%s) AS locked", (RUN_LOCK,)).fetchone()[
            "locked"
        ]:
            return "locked"
        try:
            row = repository.active(conn)
            if row is None or (row["retry_at"] and row["retry_at"] > now):
                return "not_due"
            for phase in PHASES[PHASES.index(row["phase"]) :]:
                index = PHASES.index(phase)
                schedule = operational.schedule(JOB_KEYS[phase])
                if schedule and schedule["retry_at"] and schedule["retry_at"] > now:
                    row.update(
                        status="retry_scheduled",
                        retry_at=schedule["retry_at"],
                        message="Se respeta el reintento programado del job.",
                    )
                    row["stages"][index].update(status="retry_scheduled", message=row["message"])
                    repository.save(row)
                    return "retry_scheduled"
                row.update(
                    phase=phase, status="running", retry_at=None, message=RUNNING_MESSAGES[phase]
                )
                row["stages"][index].update(status="running", message=row["message"])
                repository.save(row)
                captured = None
                try:
                    captured = CaptureJob(factory(phase))
                    status = (
                        ingestion_runner(database, captured, force=True)
                        if phase == "ingestion"
                        else background_runner(database, JOB_KEYS[phase], captured, force=True)
                    )
                    summary = (
                        stage_summary(phase, captured.result or {})
                        if status == "completed"
                        else None
                    )
                except Exception as exc:
                    LOG.error("Actualización manual: fallo en %s (%s)", phase, type(exc).__name__)
                    status = "failed"
                if status != "completed":
                    waiting = status in ("locked", "not_due")
                    row["attempts"] += 0 if waiting else 1
                    latest = operational.schedule(JOB_KEYS[phase])
                    retry_at = (
                        latest["retry_at"]
                        if latest and latest["retry_at"] and latest["retry_at"] > datetime.now(UTC)
                        else datetime.now(UTC) + timedelta(seconds=10 if waiting else 3600)
                    )
                    exhausted = row["attempts"] >= 3
                    message = "La etapa no pudo completarse; se conserva la información anterior."
                    row.update(
                        status="failed" if exhausted else "retry_scheduled",
                        retry_at=None if exhausted else retry_at,
                        finished_at=datetime.now(UTC) if exhausted else None,
                        message=message,
                    )
                    row["stages"][index].update(
                        status="failed" if exhausted else "retry_scheduled", message=message
                    )
                    repository.save(row)
                    return row["status"]
                row["stages"][index] = summary
                row["attempts"] = 0
                if index < len(PHASES) - 1:
                    row["phase"] = PHASES[index + 1]
                    repository.save(row)
            limited = any(stage["limitations"] for stage in row["stages"])
            row.update(
                status="completed_with_limitations" if limited else "completed",
                finished_at=datetime.now(UTC),
                retry_at=None,
                message="Actualización completada con información pendiente. Revisa el detalle."
                if limited
                else "Datos, modelos y análisis actualizados.",
            )
            repository.save(row)
            return "completed"
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (RUN_LOCK,))
