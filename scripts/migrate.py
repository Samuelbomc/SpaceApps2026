"""Aplica migraciones versionadas y registra la región de desarrollo y el job."""

import hashlib
import os
from pathlib import Path

from apps.api.app.config import Settings
from apps.api.app.db.postgres import Database
from packages.contracts.api import Region


def migrate(database: Database):
    migrations = Path(__file__).resolve().parents[1] / "infra/database/migrations"
    region = Region(
        region_id=os.getenv("REGION_ID", "antioquia-reference"),
        name=os.getenv("REGION_NAME", "Medellín · referencia técnica"),
        latitude=float(os.getenv("REGION_LATITUDE", "6.2442")),
        longitude=float(os.getenv("REGION_LONGITUDE", "-75.5812")),
    )
    with database.connect() as conn:
        # Bloqueo de migración compartido entre API/worker al arrancar juntos.
        conn.execute("SELECT pg_advisory_xact_lock(1546052064)")
        conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations
            (version text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz DEFAULT now())""")
        for path in sorted(migrations.glob("*.sql")):
            sql = path.read_text(encoding="utf-8")
            digest = hashlib.sha256(sql.encode()).hexdigest()
            previous = conn.execute(
                "SELECT sha256 FROM schema_migrations WHERE version=%s", (path.name,)
            ).fetchone()
            if previous:
                if previous["sha256"] != digest:
                    raise RuntimeError(
                        "Una migración aplicada fue modificada; crea una nueva versión."
                    )
                continue
            conn.execute(sql, prepare=False)
            conn.execute(
                "INSERT INTO schema_migrations(version,sha256) VALUES (%s,%s)", (path.name, digest)
            )
        conn.execute(
            """INSERT INTO regions(region_id,name,latitude,longitude) VALUES (%s,%s,%s,%s)
                     ON CONFLICT(region_id) DO NOTHING""",
            (region.region_id, region.name, region.latitude, region.longitude),
        )
        conn.execute("""INSERT INTO job_schedules(job_key,interval_seconds)
                     VALUES ('nasa-weekly',604800) ON CONFLICT(job_key) DO NOTHING""")


if __name__ == "__main__":
    migrate(Database(Settings.from_env().database_url))
    print("Migraciones PostgreSQL aplicadas.")
