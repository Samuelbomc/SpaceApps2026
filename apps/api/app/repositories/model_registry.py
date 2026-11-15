"""Registro PostgreSQL de compatibilidad local; el despliegue puede usar MongoDB."""

from psycopg.types.json import Jsonb

from packages.contracts.training import ModelRelease


class PostgreSQLModelRegistry:
    def __init__(self, database):
        self.database = database

    def _get(self, kind, key):
        with self.database.connect() as conn:
            row = conn.execute("SELECT body FROM ml_records WHERE kind=%s AND record_key=%s", (kind, key)).fetchone()
            return row["body"] if row else None

    def _put(self, kind, key, body, *, immutable=False):
        with self.database.connect() as conn:
            conn.execute("""INSERT INTO ml_records(kind,record_key,body) VALUES (%s,%s,%s)
                ON CONFLICT(kind,record_key) """ + ("DO NOTHING" if immutable else "DO UPDATE SET body=EXCLUDED.body,updated_at=now()"),
                         (kind, key, Jsonb(body)))

    def current(self, slot):
        body = self._get("published", slot)
        return ModelRelease.model_validate(body) if body else None

    def published_models(self):
        with self.database.connect() as conn:
            return [ModelRelease.model_validate(row["body"]) for row in conn.execute(
                "SELECT body FROM ml_records WHERE kind='published' ORDER BY record_key").fetchall()]

    def attempt(self, fingerprint):
        return self._get("attempt", fingerprint)

    def record_attempt(self, fingerprint, body):
        self._put("attempt", fingerprint, body, immutable=True)

    def publish(self, release, expected_version):
        with self.database.connect() as conn:
            # El lock protege también la primera publicación, cuando todavía no existe fila.
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (release.slot,))
            row = conn.execute("SELECT body FROM ml_records WHERE kind='published' AND record_key=%s FOR UPDATE", (release.slot,)).fetchone()
            current_version = row["body"]["version"] if row else None
            if current_version != expected_version:
                return False
            body = Jsonb(release.model_dump(mode="json"))
            conn.execute("""INSERT INTO ml_records(kind,record_key,body) VALUES ('version',%s,%s)
                ON CONFLICT(kind,record_key) DO NOTHING""", (release.version, body))
            conn.execute("""INSERT INTO ml_records(kind,record_key,body) VALUES ('published',%s,%s)
                ON CONFLICT(kind,record_key) DO UPDATE SET body=EXCLUDED.body,updated_at=now()""", (release.slot, body))
            return True

    def record_outcomes(self, outcomes):
        self._put("training_status", "latest", {"outcomes": outcomes})

    def recent_training(self):
        return (self._get("training_status", "latest") or {}).get("outcomes", [])
