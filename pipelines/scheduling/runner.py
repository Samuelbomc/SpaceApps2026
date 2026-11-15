"""Jobs ML con locks propios y backoff, separados del estado de las fuentes NASA."""

import logging
from datetime import UTC, datetime, timedelta

from psycopg.types.json import Jsonb

LOG = logging.getLogger("fieldshift.automation")
LOCKS = {"model-training": 1546052066, "crop-recommendations": 1546052067}


def next_slot(due, finished, interval_seconds):
    if interval_seconds <= 0:
        raise ValueError("El intervalo debe ser positivo.")
    missed = max(0, int((finished - due).total_seconds() // interval_seconds))
    return due + timedelta(seconds=(missed + 1) * interval_seconds)


def poll_background(database, key, job, *, force=False, now=None):
    lock = LOCKS[key]
    now = now or datetime.now(UTC)
    with database.connect(autocommit=True) as conn:
        if not conn.execute("SELECT pg_try_advisory_lock(%s) AS locked", (lock,)).fetchone()[
            "locked"
        ]:
            return "locked"
        try:
            state = conn.execute("SELECT * FROM job_schedules WHERE job_key=%s", (key,)).fetchone()
            if state is None:
                raise RuntimeError("Falta registrar el job de automatización; ejecuta migraciones.")
            if not force and (state["retry_at"] or state["next_run_at"]) > now:
                return "not_due"
            try:
                result = job.run()
                if result["status"] != "ok":
                    raise RuntimeError("El pipeline no completó su ejecución.")
            except Exception as exc:
                failures = state["consecutive_failures"] + 1
                delay = min(86400, 3600 * 2 ** min(failures - 1, 5))
                conn.execute(
                    """UPDATE job_schedules SET retry_at=%s,consecutive_failures=%s,last_error=%s
                    WHERE job_key=%s""",
                    (
                        datetime.now(UTC) + timedelta(seconds=delay),
                        failures,
                        f"{key} falló ({type(exc).__name__}); se conserva el estado anterior.",
                        key,
                    ),
                )
                LOG.error("%s requiere reintento (%s)", key, type(exc).__name__)
                return "retry_scheduled"
            finished = datetime.now(UTC)
            following = (
                next_slot(state["next_run_at"], finished, state["interval_seconds"])
                if state["next_run_at"] <= finished
                else state["next_run_at"]
            )
            conn.execute(
                """UPDATE job_schedules SET next_run_at=%s,last_success_at=%s,retry_at=NULL,
                last_error=NULL,consecutive_failures=0,last_result=%s WHERE job_key=%s""",
                (following, finished, Jsonb(result), key),
            )
            if key == "model-training" and result.get("published", 0):
                conn.execute(
                    "UPDATE job_schedules SET next_run_at=LEAST(next_run_at,now()) WHERE job_key='crop-recommendations'"
                )
            return "completed"
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (lock,))
