"""Schedulers durables de ingesta, entrenamiento y recomendaciones, fuera de HTTP."""

import argparse
import logging
import signal
import threading
from datetime import UTC, datetime, timedelta

from psycopg.types.json import Jsonb

from apps.api.app.config import Settings
from apps.api.app.db.postgres import Database
from pipelines.scheduling.runner import next_slot, poll_background
from scripts.migrate import migrate
from scripts.runtime import build_jobs

LOG = logging.getLogger("fieldshift.worker")
JOB_KEY = "nasa-weekly"
LOCK_ID = 1546052065


def poll_once(database: Database, job, *, force=False, now=None):
    now = now or datetime.now(UTC)
    with database.connect(autocommit=True) as conn:
        if not conn.execute("SELECT pg_try_advisory_lock(%s) AS locked", (LOCK_ID,)).fetchone()[
            "locked"
        ]:
            return "locked"
        try:
            schedule = conn.execute(
                "SELECT * FROM job_schedules WHERE job_key=%s", (JOB_KEY,)
            ).fetchone()
            if schedule is None:
                raise RuntimeError("Job sin registrar; ejecuta migraciones.")
            due_at = schedule["retry_at"] or schedule["next_run_at"]
            if not force and due_at > now:
                return "not_due"
            # Solo el worker dueño del bloqueo puede cerrar ejecuciones abandonadas.
            conn.execute("""UPDATE ingestion_runs SET status='failed',finished_at=now(),
                         summary='{"error":"Worker anterior interrumpido"}'::jsonb WHERE status='running'""")
            weekly_due = schedule["next_run_at"] <= now
            # Al llegar otro ciclo semanal se actualizan también las fuentes sanas.
            pending = schedule["pending_sources"] if not (force or weekly_due) else []
            result = None
            try:
                result = job.run(sources=tuple(pending)) if pending else job.run()
                failures = result.get("summary", {}).get("failed_sources", [])
                if result["status"] != "ok":
                    pending = failures or pending
                    raise RuntimeError(
                        "Ingesta parcial; se reintentará sin perder datos persistidos."
                    )
            except Exception as exc:
                attempts = schedule["consecutive_failures"] + 1
                # Backoff durable: 1, 2, 4, 8, 16 y luego 24 horas entre intentos.
                delay = min(86400, 3600 * 2 ** min(attempts - 1, 5))
                if result is not None:
                    delay = max(
                        delay,
                        max(
                            (
                                entry.get("retry_after_seconds", 0)
                                for entry in result.get("summary", {}).values()
                                if isinstance(entry, dict)
                            ),
                            default=0,
                        ),
                    )
                finished = datetime.now(UTC)
                following = (
                    next_slot(schedule["next_run_at"], finished, schedule["interval_seconds"])
                    if weekly_due
                    else schedule["next_run_at"]
                )
                conn.execute(
                    """UPDATE job_schedules SET last_error=%s,retry_at=%s,next_run_at=%s,
                             consecutive_failures=%s,pending_sources=%s WHERE job_key=%s""",
                    (
                        f"Ingesta incompleta ({type(exc).__name__}); revisar ejecución.",
                        finished + timedelta(seconds=delay),
                        following,
                        attempts,
                        Jsonb(list(pending)),
                        JOB_KEY,
                    ),
                )
                LOG.error(
                    "El job requiere reintento en %s segundos (%s)", delay, type(exc).__name__
                )
                return "retry_scheduled"
            finished = datetime.now(UTC)
            # Un disparo manual previo al próximo slot no cambia el calendario.
            due = schedule["next_run_at"]
            following = (
                next_slot(due, finished, schedule["interval_seconds"]) if due <= finished else due
            )
            conn.execute(
                """UPDATE job_schedules SET next_run_at=%s,last_success_at=%s,last_error=NULL,retry_at=NULL,
                         consecutive_failures=0,pending_sources='[]'::jsonb
                         WHERE job_key=%s""",
                (following, finished, JOB_KEY),
            )
            return "completed"
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--once", action="store_true", help="Ejecutar una vez ahora bajo el mismo bloqueo"
    )
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument(
        "--job", choices=("all", "ingestion", "training", "recommendations"), default="all"
    )
    args = parser.parse_args(argv)
    if args.poll_seconds < 1:
        parser.error("poll-seconds debe ser positivo")
    logging.basicConfig(level=logging.INFO)
    settings = Settings.from_env()
    database = Database(settings.database_url)
    migrate(database)
    jobs = build_jobs(database, settings)
    selected = list(jobs) if args.job == "all" else [args.job]

    def execute():
        states = []
        for name in selected:
            try:
                if name == "ingestion":
                    status = poll_once(database, jobs[name], force=args.once)
                    if status == "completed":
                        with database.connect() as conn:
                            conn.execute("""UPDATE job_schedules SET next_run_at=LEAST(next_run_at,now())
                                WHERE job_key IN ('model-training','crop-recommendations')""")
                else:
                    key = "model-training" if name == "training" else "crop-recommendations"
                    status = poll_background(database, key, jobs[name], force=args.once)
                states.append(status)
                LOG.info("%s: %s", name, status)
            except Exception as exc:
                states.append("failed")
                LOG.error("%s sin conexión o configuración válida (%s)", name, type(exc).__name__)
        return states

    if args.once:
        return 0 if all(status == "completed" for status in execute()) else 1
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        execute()
        stop.wait(args.poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
