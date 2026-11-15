"""Cola y autorización contra PostgreSQL aislado; jobs/datos NASA sintéticos explícitos."""

import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import psycopg
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo

from apps.api.app.config import Settings
from apps.api.app.db.postgres import Database
from apps.api.app.main import create_app
from apps.api.app.repositories.manual_updates import (
    RUN_LOCK,
    ManualUpdateRepository,
    UpdateCooldown,
)
from apps.api.app.repositories.operational import OperationalRepository
from pipelines.scheduling.manual import poll_manual_updates
from scripts.migrate import migrate
from scripts.worker import LOCK_ID


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "Requiere PostgreSQL de pruebas")
class ManualUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = os.environ["TEST_DATABASE_URL"]
        cls.schema = "manual_tests_" + uuid.uuid4().hex
        with psycopg.connect(cls.url, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(cls.schema)))
        cls.db = Database(make_conninfo(cls.url, options=f"-c search_path={cls.schema}"))
        migrate(cls.db)

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(cls.url, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(cls.schema)))

    def setUp(self):
        with self.db.connect() as conn:
            conn.execute("TRUNCATE manual_updates,farmer_users,auth_rate_limits CASCADE")
            conn.execute(
                "UPDATE job_schedules SET next_run_at=now()+interval '7 days',retry_at=NULL,consecutive_failures=0,last_error=NULL,last_result='{}'"
            )
        self.client = TestClient(
            create_app(OperationalRepository(self.db), settings=Settings(database_url=self.db.url))
        )
        self.repository = ManualUpdateRepository(self.db)
        self.addCleanup(self.client.close)
        self.order = []
        self.jobs = {phase: Mock() for phase in ("ingestion", "training", "recommendations")}
        for phase in self.jobs:

            def run(phase=phase, **kwargs):
                self.order.append(phase)
                if phase == "ingestion":
                    return {"status": "ok", "summary": {"failed_sources": []}}
                if phase == "training":
                    return {
                        "status": "ok",
                        "published": 0,
                        "outcomes": [{"status": "insufficient_labels"}],
                    }
                return {"status": "ok", "outcomes": [{"status": "insufficient_data"}]}

            self.jobs[phase].run.side_effect = run

    def register(self):
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "display_name": "Fixture manual",
                "email": "manual@example.com",
                "password": "Una clave sintetica de pruebas 2026",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def enqueue(self):
        session = self.register()
        response = self.client.post(
            "/api/v1/automation/refresh", headers={"X-CSRF-Token": session["csrf_token"]}
        )
        self.assertEqual(response.status_code, 202, response.text)
        return session, response.json()

    def test_api_requires_session_and_csrf_but_never_starts_jobs_in_http(self):
        self.assertEqual(self.client.post("/api/v1/automation/refresh").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/automation/refresh").status_code, 401)
        session = self.register()
        self.assertEqual(self.client.post("/api/v1/automation/refresh").status_code, 403)
        headers = {"X-CSRF-Token": session["csrf_token"]}
        denied = self.client.post(
            "/api/v1/automation/refresh", headers={**headers, "Origin": "https://example.invalid"}
        )
        self.assertEqual(denied.status_code, 403)
        response = self.client.post("/api/v1/automation/refresh", headers=headers)
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json()["status"], "queued")
        repeated = self.client.post("/api/v1/automation/refresh", headers=headers)
        self.assertEqual(repeated.json()["request_id"], response.json()["request_id"])
        state = self.client.get("/api/v1/automation/refresh")
        self.assertEqual(state.headers["cache-control"], "no-store")
        self.assertNotIn("requested_by", state.json())
        self.assertEqual(self.order, [])

    def test_simultaneous_clicks_coalesce_into_one_update(self):
        session = self.register()
        owner = session["user"]["user_id"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            updates = list(pool.map(lambda _: self.repository.enqueue(owner), range(4)))
        self.assertEqual(len({item.request_id for item in updates}), 1)

    def test_worker_runs_stages_in_order_and_reports_missing_inputs_honestly(self):
        self.enqueue()
        before = OperationalRepository(self.db).schedules()
        self.assertEqual(poll_manual_updates(self.db, self.jobs.__getitem__), "completed")
        update = self.repository.latest()
        self.assertEqual(self.order, ["ingestion", "training", "recommendations"])
        self.assertEqual(update.status, "completed_with_limitations")
        self.assertTrue(all(stage.status == "completed" for stage in update.stages))
        self.assertTrue(update.stages[0].limitations)
        self.assertEqual(update.stages[1].counts, {"insufficient_labels": 1})
        self.assertEqual(update.stages[2].counts, {"insufficient_data": 1})
        after = OperationalRepository(self.db).schedules()
        self.assertEqual([s["next_run_at"] for s in before], [s["next_run_at"] for s in after])
        self.assertEqual(poll_manual_updates(self.db, self.jobs.__getitem__), "not_due")

    def test_partial_download_keeps_retry_and_does_not_run_training_prematurely(self):
        self.enqueue()
        self.jobs["ingestion"].run.side_effect = None
        self.jobs["ingestion"].run.return_value = {
            "status": "partial",
            "summary": {"failed_sources": ["gpm"]},
        }
        self.assertEqual(poll_manual_updates(self.db, self.jobs.__getitem__), "retry_scheduled")
        update = self.repository.latest()
        self.assertEqual(update.phase, "ingestion")
        self.assertIsNotNone(update.retry_at)
        self.jobs["training"].run.assert_not_called()
        self.assertEqual(poll_manual_updates(self.db, self.jobs.__getitem__), "not_due")
        self.jobs["ingestion"].run.return_value = {
            "status": "ok",
            "summary": {"failed_sources": []},
        }
        self.assertEqual(
            poll_manual_updates(
                self.db, self.jobs.__getitem__, now=datetime.now(UTC) + timedelta(days=1)
            ),
            "completed",
        )
        self.assertEqual(self.repository.latest().status, "completed_with_limitations")
        self.jobs["training"].run.assert_called_once()

    def test_existing_scheduler_lock_prevents_duplicate_ingestion(self):
        self.enqueue()
        with self.db.connect(autocommit=True) as conn:
            conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
            self.assertEqual(poll_manual_updates(self.db, self.jobs.__getitem__), "retry_scheduled")
        self.jobs["ingestion"].run.assert_not_called()
        self.assertEqual(self.repository.latest().stages[0].status, "retry_scheduled")

    def test_three_failed_attempts_end_the_manual_request_without_exposing_errors(self):
        self.enqueue()
        self.jobs["ingestion"].run.side_effect = RuntimeError("synthetic-secret-do-not-return")
        for expected in ("retry_scheduled", "retry_scheduled", "failed"):
            self.assertEqual(
                poll_manual_updates(
                    self.db, self.jobs.__getitem__, now=datetime.now(UTC) + timedelta(days=2)
                ),
                expected,
            )
        update = self.repository.latest()
        self.assertEqual(update.status, "failed")
        self.assertNotIn("synthetic-secret", update.model_dump_json())
        self.jobs["training"].run.assert_not_called()

    def test_worker_resumes_after_an_interruption_without_repeating_completed_stages(self):
        self.enqueue()
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM manual_updates").fetchone()
        row.update(phase="training", status="running")
        row["stages"][0].update(status="completed", message="Fixture ya procesado.")
        self.repository.save(row)
        self.assertEqual(poll_manual_updates(self.db, self.jobs.__getitem__), "completed")
        self.assertEqual(self.order, ["training", "recommendations"])
        self.jobs["ingestion"].run.assert_not_called()

    def test_only_one_manual_consumer_can_process_the_active_request(self):
        self.enqueue()
        with self.db.connect(autocommit=True) as conn:
            conn.execute("SELECT pg_advisory_lock(%s)", (RUN_LOCK,))
            self.assertEqual(poll_manual_updates(self.db, self.jobs.__getitem__), "locked")
        self.assertEqual(self.repository.latest().status, "queued")
        self.assertEqual(self.order, [])

    def test_construction_failure_does_not_reuse_an_expired_retry_time(self):
        self.enqueue()
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE job_schedules SET retry_at=now()-interval '1 minute' WHERE job_key='nasa-weekly'"
            )
        factory = Mock(side_effect=RuntimeError("fixture-only construction failure"))
        self.assertEqual(poll_manual_updates(self.db, factory), "retry_scheduled")
        self.assertGreater(
            self.repository.latest().retry_at, datetime.now(UTC) + timedelta(minutes=59)
        )

    def test_completed_requests_have_a_global_cooldown(self):
        session, _ = self.enqueue()
        poll_manual_updates(self.db, self.jobs.__getitem__)
        with self.assertRaises(UpdateCooldown):
            self.repository.enqueue(session["user"]["user_id"])
        response = self.client.post(
            "/api/v1/automation/refresh", headers={"X-CSRF-Token": session["csrf_token"]}
        )
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response.headers["retry-after"]), 0)

    def test_malformed_stage_summary_is_retried_instead_of_leaving_an_eternal_running_state(self):
        self.enqueue()
        self.jobs["training"].run.side_effect = None
        self.jobs["training"].run.return_value = {
            "status": "ok",
            "outcomes": [{"fixture": "missing-status"}],
        }
        self.assertEqual(poll_manual_updates(self.db, self.jobs.__getitem__), "retry_scheduled")
        self.assertEqual(self.repository.latest().phase, "training")
        self.assertIsNotNone(self.repository.latest().retry_at)
        self.jobs["recommendations"].run.assert_not_called()
