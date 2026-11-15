"""Cola global persistida, coalescencia y enfriamiento para actualizaciones manuales."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from psycopg.types.json import Jsonb

from packages.contracts.manual_update import ManualUpdate, UpdateStage

ENQUEUE_LOCK = 1546052068
RUN_LOCK = 1546052069
ACTIVE = ("queued", "running", "retry_scheduled")
PHASES = ("ingestion", "training", "recommendations")


class UpdateCooldown(Exception):
    def __init__(self, seconds):
        self.seconds = seconds


class ManualUpdateRepository:
    def __init__(self, database):
        self.database = database

    @staticmethod
    def public(row):
        return (
            ManualUpdate.model_validate({key: row[key] for key in ManualUpdate.model_fields})
            if row
            else None
        )

    def latest(self):
        with self.database.connect() as conn:
            return self.public(
                conn.execute(
                    "SELECT * FROM manual_updates ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
            )

    def enqueue(self, user_id, *, now=None):
        now = now or datetime.now(UTC)
        with self.database.connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (ENQUEUE_LOCK,))
            active = conn.execute(
                "SELECT * FROM manual_updates WHERE status=ANY(%s)", (list(ACTIVE),)
            ).fetchone()
            if active:
                return self.public(active)
            latest = conn.execute(
                "SELECT created_at FROM manual_updates ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if latest and latest["created_at"] + timedelta(minutes=5) > now:
                raise UpdateCooldown(
                    max(1, int((latest["created_at"] + timedelta(minutes=5) - now).total_seconds()))
                )
            stages = [
                UpdateStage(phase=phase, status="pending", message="Pendiente.").model_dump(
                    mode="json"
                )
                for phase in PHASES
            ]
            row = conn.execute(
                """INSERT INTO manual_updates(request_id,requested_by,phase,status,message,stages,created_at,updated_at)
                VALUES (%s,%s,'ingestion','queued',%s,%s,%s,%s) RETURNING *""",
                (
                    uuid4(),
                    user_id,
                    "Encolada. Esperando al worker de actualización.",
                    Jsonb(stages),
                    now,
                    now,
                ),
            ).fetchone()
            return self.public(row)

    def active(self, conn):
        return conn.execute(
            "SELECT * FROM manual_updates WHERE status=ANY(%s) ORDER BY created_at LIMIT 1",
            (list(ACTIVE),),
        ).fetchone()

    def save(self, row):
        with self.database.connect() as conn:
            conn.execute(
                """UPDATE manual_updates SET phase=%s,status=%s,message=%s,stages=%s,
                attempts=%s,retry_at=%s,finished_at=%s,updated_at=now() WHERE request_id=%s""",
                (
                    row["phase"],
                    row["status"],
                    row["message"],
                    Jsonb(row["stages"]),
                    row["attempts"],
                    row["retry_at"],
                    row["finished_at"],
                    row["request_id"],
                ),
            )
