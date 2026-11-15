"""Datos recientes y resultados operativos; el histórico completo sigue en Parquet."""

from datetime import date

from psycopg.types.json import Jsonb

from apps.api.app.db.postgres import Database


class OperationalRepository:
    def __init__(self, database: Database):
        self.database = database

    def regions(self):
        with self.database.connect() as conn:
            return conn.execute("SELECT * FROM regions ORDER BY name").fetchall()

    def region(self, region_id):
        with self.database.connect() as conn:
            return conn.execute("SELECT * FROM regions WHERE region_id = %s", (region_id,)).fetchone()

    def observations(self, region_id, start: date, end: date, limit=1000):
        with self.database.connect() as conn:
            rows = conn.execute("""SELECT body FROM observations WHERE region_id = %s
                AND observed_date BETWEEN %s AND %s ORDER BY observed_date DESC, variable LIMIT %s""",
                                (region_id, start, end, limit)).fetchall()
            return [row["body"] for row in rows]

    def latest_observation_date(self, region_id, before: date):
        with self.database.connect() as conn:
            row = conn.execute("""SELECT max(observed_date) AS latest FROM observations
                WHERE region_id=%s AND observed_date < %s
                AND body->>'quality'='provider_value_unvalidated'
                AND body->>'value' IS NOT NULL""", (region_id, before)).fetchone()
            return row["latest"]

    def observation_page(self, region_id, limit=1000, offset=0):
        """Histórico operativo completo, paginado y con metadatos en un mismo snapshot SQL."""
        with self.database.connect() as conn:
            return conn.execute("""WITH metadata AS (
                SELECT count(*) AS total, min(observed_date) AS first_date,
                       max(observed_date) AS last_date, max(updated_at) AS last_updated_at
                FROM observations WHERE region_id=%s
            ) SELECT metadata.*,
                COALESCE((SELECT jsonb_agg(body ORDER BY observed_date DESC,source,product,variable,time_standard)
                    FROM (SELECT body,observed_date,source,product,variable,time_standard
                          FROM observations WHERE region_id=%s
                          ORDER BY observed_date DESC,source,product,variable,time_standard
                          LIMIT %s OFFSET %s) AS page), '[]'::jsonb) AS items
            FROM metadata""", (region_id, region_id, limit, offset)).fetchone()

    def store_recent(self, region_id, observations, cutoff):
        with self.database.connect() as conn:
            with conn.cursor() as cursor:
                cursor.executemany("""INSERT INTO observations
                    (region_id,source,product,observed_date,variable,time_standard,body)
                    VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT
                    (region_id,source,product,observed_date,variable,time_standard)
                    DO UPDATE SET body=EXCLUDED.body,updated_at=now()""", [
                    (region_id, row["source"], row["product"], row["date"], row["variable"],
                     row["time_standard"], Jsonb(row)) for row in observations])
            # El caller solo invoca esto después de persistir/verificar Parquet.
            conn.execute("""DELETE FROM observations WHERE region_id=%s AND source='NASA_POWER'
                         AND product='POWER_DAILY' AND observed_date < %s""", (region_id, cutoff))

    def recent_runs(self, limit=10):
        with self.database.connect() as conn:
            return conn.execute("SELECT * FROM ingestion_runs ORDER BY started_at DESC LIMIT %s", (limit,)).fetchall()

    def schedule(self, job_key="nasa-weekly"):
        with self.database.connect() as conn:
            return conn.execute("SELECT * FROM job_schedules WHERE job_key=%s", (job_key,)).fetchone()

    def schedules(self):
        with self.database.connect() as conn:
            return conn.execute("SELECT * FROM job_schedules ORDER BY job_key").fetchall()

    def start_run(self, run_id, region_id):
        with self.database.connect() as conn:
            conn.execute("INSERT INTO ingestion_runs(run_id,region_id,status) VALUES (%s,%s,'running')", (run_id, region_id))

    def finish_run(self, run_id, status, summary):
        with self.database.connect() as conn:
            conn.execute("UPDATE ingestion_runs SET status=%s, summary=%s, finished_at=now() WHERE run_id=%s",
                         (status, Jsonb(summary), run_id))

    def snapshot(self, run_id, source, payload):
        with self.database.connect() as conn:
            conn.execute("INSERT INTO source_snapshots(run_id,source,body) VALUES (%s,%s,%s)", (run_id, source, Jsonb(payload)))

    def save_analysis(self, analysis):
        body = analysis.model_dump(mode="json")
        with self.database.connect() as conn:
            conn.execute("""INSERT INTO analyses(analysis_id,region_id,reference_date,horizon_days,input_snapshot_id,body)
                VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(analysis_id) DO NOTHING""",
                         (analysis.analysis_id, analysis.request.region_id, analysis.request.reference_date,
                          analysis.request.horizon_days, analysis.input_snapshot_id, Jsonb(body)))

    def analyses(self, region_id, limit=10):
        with self.database.connect() as conn:
            rows = conn.execute("SELECT body FROM analyses WHERE region_id=%s ORDER BY created_at DESC LIMIT %s",
                                (region_id, limit)).fetchall()
            return [row["body"] for row in rows]

    def analysis_for(self, request):
        with self.database.connect() as conn:
            row = conn.execute("""SELECT body FROM analyses WHERE region_id=%s AND reference_date=%s
                AND horizon_days=%s AND body->'request'->>'forecast_start_date' IS NOT DISTINCT FROM %s
                ORDER BY created_at DESC LIMIT 1""",
                               (request.region_id, request.reference_date, request.horizon_days,
                                request.forecast_start_date.isoformat() if request.forecast_start_date else None)).fetchone()
            return row["body"] if row else None

    def analysis_for_period(self, region_id, horizon, target_start):
        with self.database.connect() as conn:
            row = conn.execute("""SELECT body FROM analyses WHERE region_id=%s AND horizon_days=%s
                AND body->'request'->>'forecast_start_date'=%s
                ORDER BY (body->>'climate' IS NOT NULL) DESC, created_at DESC LIMIT 1""",
                (region_id, horizon, target_start.isoformat())).fetchone()
            return row['body'] if row else None
