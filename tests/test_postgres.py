"""Integración real PostgreSQL. TEST_DATABASE_URL debe apuntar a una base de pruebas."""

import os
import unittest
import uuid
from datetime import UTC, date, datetime, timedelta
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import psycopg
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb

from apps.api.app.db.postgres import Database
from apps.api.app.main import create_app
from apps.api.app.repositories.operational import OperationalRepository
from scripts.migrate import migrate
from scripts.weekly_ingestion import WeeklyIngestionJob
from scripts.worker import LOCK_ID, poll_once


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "Requiere TEST_DATABASE_URL (PostgreSQL real)")
class PostgreSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = os.environ["TEST_DATABASE_URL"]
        cls.schema = "fieldshift_test_" + uuid.uuid4().hex
        with psycopg.connect(cls.url, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(cls.schema)))
        cls.db = Database(make_conninfo(cls.url, options=f"-c search_path={cls.schema}"))
        migrate(cls.db)
        cls.repo = OperationalRepository(cls.db)

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(cls.url, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(cls.schema)))

    def setUp(self):
        with self.db.connect() as conn:
            conn.execute("DELETE FROM observations")
            conn.execute(
                "UPDATE job_schedules SET next_run_at=now()-interval '1 day',retry_at=NULL,last_error=NULL,consecutive_failures=0,pending_sources='[]'::jsonb"
            )

    def test_migrations_are_idempotent(self):
        migrate(self.db)
        with self.db.connect() as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) AS n FROM schema_migrations").fetchone()["n"], 5
            )
        self.assertEqual(len(self.repo.regions()), 1)

    def test_independent_ml_jobs_keep_retry_and_schedule_after_restart(self):
        from pipelines.scheduling.runner import LOCKS, poll_background

        failing = Mock()
        failing.run.side_effect = RuntimeError("test-only training interruption")
        self.assertEqual(poll_background(self.db, "model-training", failing), "retry_scheduled")
        self.assertEqual(self.repo.schedule("model-training")["consecutive_failures"], 1)
        self.assertEqual(self.repo.schedule()["consecutive_failures"], 0)
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE job_schedules SET retry_at=now()-interval '1 second' WHERE job_key='model-training'"
            )
        success = Mock()
        success.run.return_value = {"status": "ok", "published": 1}
        with self.db.connect(autocommit=True) as conn:
            conn.execute("SELECT pg_advisory_lock(%s)", (LOCKS["model-training"],))
            try:
                self.assertEqual(poll_background(self.db, "model-training", success), "locked")
            finally:
                conn.execute("SELECT pg_advisory_unlock(%s)", (LOCKS["model-training"],))
        self.assertEqual(poll_background(self.db, "model-training", success), "completed")
        self.assertEqual(poll_background(self.db, "model-training", success), "not_due")
        self.assertIsNone(self.repo.schedule("model-training")["retry_at"])
        self.assertEqual(self.repo.schedule("model-training")["last_result"]["published"], 1)

    def test_partial_recommendations_keep_failed_tasks_and_resume_after_restart(self):
        from pipelines.scheduling.runner import poll_background

        today = datetime.now(ZoneInfo("America/Bogota")).date().isoformat()
        tasks = [{"region_id": "fixture-only", "horizon_days": 7}]
        partial = Mock()
        partial.run.return_value = {
            "status": "partial",
            "forecast_start_date": today,
            "failed_tasks": tasks,
            "outcomes": [
                {"horizon_days": 7, "status": "failed"},
                {"horizon_days": 15, "status": "insufficient_data"},
            ],
        }
        self.assertEqual(
            poll_background(self.db, "crop-recommendations", partial), "retry_scheduled"
        )
        state = self.repo.schedule("crop-recommendations")
        self.assertEqual(state["last_result"]["failed_tasks"], tasks)
        self.assertIsNotNone(state["retry_at"])
        self.assertEqual(poll_background(self.db, "crop-recommendations", partial), "not_due")
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE job_schedules SET retry_at=now()-interval '1 second' WHERE job_key='crop-recommendations'"
            )
        restarted = Mock()
        restarted.run.return_value = {
            "status": "ok",
            "forecast_start_date": today,
            "failed_tasks": [],
            "outcomes": [],
        }
        self.assertEqual(poll_background(self.db, "crop-recommendations", restarted), "completed")
        restarted.run.assert_called_once_with(tasks=tasks)
        self.assertIsNone(self.repo.schedule("crop-recommendations")["retry_at"])

    def test_previous_day_retry_and_forced_run_refresh_all_recommendation_tasks(self):
        from pipelines.scheduling.runner import poll_background

        today = datetime.now(ZoneInfo("America/Bogota")).date()
        for previous_date, force in [(today - timedelta(days=1), False), (today, True)]:
            previous = {
                "status": "partial",
                "forecast_start_date": previous_date.isoformat(),
                "failed_tasks": [{"region_id": "fixture-only", "horizon_days": 7}],
            }
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE job_schedules SET retry_at=now()-interval '1 second',last_result=%s WHERE job_key='crop-recommendations'",
                    (Jsonb(previous),),
                )
            job = Mock()
            job.run.return_value = {"status": "ok"}
            self.assertEqual(
                poll_background(self.db, "crop-recommendations", job, force=force), "completed"
            )
            job.run.assert_called_once_with()

    def test_local_registry_keeps_champion_on_compare_and_swap_failure(self):
        from apps.api.app.repositories.model_registry import PostgreSQLModelRegistry
        from tests.test_automation_storage import fixture_release

        registry = PostgreSQLModelRegistry(self.db)
        with self.db.connect() as conn:
            conn.execute("DELETE FROM ml_records")
        original = fixture_release()
        self.assertTrue(registry.publish(original, None))
        self.assertFalse(registry.publish(fixture_release("b" * 32), "wrong-test-version"))
        self.assertEqual(registry.current(original.slot).version, original.version)
        self.assertTrue(registry.publish(fixture_release("b" * 32), original.version))
        registry.record_attempt("test-only", {"status": "rejected"})
        registry.record_attempt("test-only", {"status": "published"})
        self.assertEqual(registry.attempt("test-only"), {"status": "rejected"})

    def test_upsert_and_http_read_use_real_postgres(self):
        row = {
            "source": "NASA_POWER",
            "product": "POWER_DAILY",
            "date": "2024-01-01",
            "variable": "T2M",
            "time_standard": "UTC",
            "value": 20.0,
            "unit": "C",
            "quality": "provider_value_unvalidated",
            "resolution": "0.5 x 0.625 degree",
        }
        self.repo.store_recent("antioquia-reference", [row], date(2024, 1, 1))
        self.repo.store_recent("antioquia-reference", [{**row, "value": 21}], date(2024, 1, 1))
        client = TestClient(create_app(self.repo))
        response = client.get(
            "/api/v1/regions/antioquia-reference/observations?start=2024-01-01&end=2024-01-01"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 1)
        self.assertEqual(response.json()["items"][0]["value"], 21)

    def test_worker_persists_next_slot_and_restart_does_not_reexecute(self):
        job = Mock()
        job.run.return_value = {"status": "ok"}
        self.assertEqual(poll_once(self.db, job), "completed")
        self.assertEqual(poll_once(self.db, job), "not_due")
        job.run.assert_called_once()
        self.assertGreater(self.repo.schedule()["next_run_at"], datetime.now(UTC))

    def test_worker_does_not_overlap_another_database_lock(self):
        with self.db.connect(autocommit=True) as conn:
            conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
            job = Mock()
            try:
                self.assertEqual(poll_once(self.db, job), "locked")
                job.run.assert_not_called()
            finally:
                conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))

    def test_partial_job_is_retried_without_lying_about_success(self):
        job = Mock()
        job.run.return_value = {"status": "partial"}
        self.assertEqual(poll_once(self.db, job), "retry_scheduled")
        self.assertEqual(poll_once(self.db, job), "not_due")
        self.assertIsNotNone(self.repo.schedule()["last_error"])

    def test_api_status_serializes_database_timestamps(self):
        response = TestClient(create_app(self.repo)).get("/api/v1/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["schedule"]["interval_seconds"], 604800)

    def test_analysis_request_reads_existing_result_by_exact_context(self):
        from packages.contracts.api import AnalysisRequest, AnalysisResult, Forecast, ForecastValue

        request = AnalysisRequest(region_id="antioquia-reference", reference_date=date(2024, 1, 1))

        def forecast(kind):
            return Forecast(
                model_kind=kind,
                model_version="test-only",
                region_id=request.region_id,
                reference_date=request.reference_date,
                horizon_days=7,
                values=[
                    ForecastValue(variable="fixture", value=1, unit="test", aggregation="test")
                ],
            )

        result = AnalysisResult(
            status="pending_recommendations",
            request=request,
            analysis_id="test-only-result",
            input_snapshot_id="test-only-input",
            climate=forecast("climate"),
            soil=forecast("soil"),
        )
        self.repo.save_analysis(result)
        self.repo.save_analysis(result)
        response = TestClient(create_app(self.repo)).post(
            "/api/v1/analyses", json=request.model_dump(mode="json")
        )
        self.assertEqual(response.json()["analysis_id"], "test-only-result")
        self.assertEqual(len(self.repo.analyses(request.region_id)), 1)

    def test_weekly_job_stores_recent_observations_and_all_source_catalogs(self):
        from pipelines.ingestion.sources.nasa.catalog import PRODUCTS

        end = datetime.now(UTC).date() - timedelta(days=3)
        row = {
            "source": "NASA_POWER",
            "product": "POWER_DAILY",
            "date": end.isoformat(),
            "variable": "T2M",
            "time_standard": "UTC",
            "value": 20.0,
            "unit": "C",
            "quality": "provider_value_unvalidated",
            "resolution": "test-only",
        }
        flow, catalogs = Mock(), Mock()
        flow.run.return_value = {"status": "ok"}
        flow.repository.read.return_value = [row]
        catalogs.fetch.return_value = {
            "sources": {
                source: {
                    "status": "empty",
                    "data_kind": "granule_catalog",
                    "data": {"granules": []},
                }
                for source in PRODUCTS
            }
        }
        result = WeeklyIngestionJob(self.repo, flow, catalogs).run()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["summary"]["downstream"]["status"], "history_updated")
        self.assertEqual(len(self.repo.observations("antioquia-reference", end, end)), 1)
        with self.db.connect() as conn:
            count = conn.execute(
                "SELECT count(*) AS n FROM source_snapshots WHERE run_id=%s", (result["run_id"],)
            ).fetchone()["n"]
        self.assertEqual(count, len(PRODUCTS))

    def test_power_failure_does_not_discard_other_sources(self):
        from pipelines.ingestion.sources.nasa.catalog import PRODUCTS

        flow, catalogs = Mock(), Mock()
        flow.run.side_effect = RuntimeError("Fixture de fallo de red")
        catalogs.fetch.return_value = {
            "sources": {
                source: {
                    "status": "empty",
                    "data_kind": "granule_catalog",
                    "data": {"granules": []},
                }
                for source in PRODUCTS
            }
        }
        result = WeeklyIngestionJob(self.repo, flow, catalogs).run()
        self.assertEqual(result["status"], "partial")
        self.assertIn("power", result["summary"]["failed_sources"])
        self.assertIn("landsat", result["summary"])

    def test_restart_retries_only_failed_sources_and_clears_pending_state(self):
        job = Mock()
        job.run.return_value = {
            "status": "partial",
            "summary": {"failed_sources": ["smap"], "smap": {"retry_after_seconds": 7200}},
        }
        before = datetime.now(UTC)
        self.assertEqual(poll_once(self.db, job), "retry_scheduled")
        state = self.repo.schedule()
        self.assertEqual(state["pending_sources"], ["smap"])
        self.assertEqual(state["consecutive_failures"], 1)
        self.assertGreaterEqual(state["retry_at"], before + timedelta(hours=2))
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE job_schedules SET retry_at=now()-interval '1 second',next_run_at=now()+interval '6 days'"
            )
        restarted_job = Mock()
        restarted_job.run.return_value = {"status": "ok"}
        self.assertEqual(poll_once(self.db, restarted_job), "completed")
        restarted_job.run.assert_called_once_with(sources=("smap",))
        self.assertEqual(self.repo.schedule()["pending_sources"], [])
        self.assertEqual(self.repo.schedule()["consecutive_failures"], 0)
        self.assertIsNone(self.repo.schedule()["retry_at"])

    def test_persistent_failure_increases_wait_without_claiming_success(self):
        job = Mock()
        job.run.side_effect = RuntimeError("Fixture de caída del proveedor")
        self.assertEqual(poll_once(self.db, job), "retry_scheduled")
        with self.db.connect() as conn:
            conn.execute("UPDATE job_schedules SET retry_at=now()-interval '1 second'")
        before = datetime.now(UTC)
        self.assertEqual(poll_once(self.db, job), "retry_scheduled")
        state = self.repo.schedule()
        self.assertEqual(state["consecutive_failures"], 2)
        self.assertGreaterEqual(state["retry_at"], before + timedelta(hours=2))

    def test_targeted_retry_skips_healthy_power_and_other_catalogs(self):
        flow, catalogs = Mock(), Mock()
        catalogs.fetch.return_value = {
            "sources": {
                "smap": {
                    "status": "empty",
                    "data_kind": "granule_catalog",
                    "data": {"granules": []},
                }
            }
        }
        result = WeeklyIngestionJob(self.repo, flow, catalogs).run(sources=("smap",))
        self.assertEqual(result["status"], "ok")
        flow.run.assert_not_called()
        self.assertEqual(catalogs.fetch.call_args.kwargs["sources"], ("smap",))
        self.assertNotIn("power", result["summary"])

    def test_unexpected_catalog_failure_does_not_block_other_sources(self):
        flow, catalogs = Mock(), Mock()
        catalogs.fetch.side_effect = [
            RuntimeError("Fixture inesperada"),
            {
                "sources": {
                    "landsat": {
                        "status": "empty",
                        "data_kind": "granule_catalog",
                        "data": {"granules": []},
                    }
                }
            },
        ]
        result = WeeklyIngestionJob(self.repo, flow, catalogs).run(sources=("smap", "landsat"))
        self.assertEqual(result["summary"]["failed_sources"], ["smap"])
        self.assertEqual(result["summary"]["landsat"]["status"], "empty")

    def test_new_weekly_cycle_refreshes_healthy_sources_despite_pending_failure(self):
        job = Mock()
        job.run.return_value = {"status": "partial", "summary": {"failed_sources": ["smap"]}}
        self.assertEqual(poll_once(self.db, job), "retry_scheduled")
        self.assertGreater(self.repo.schedule()["next_run_at"], datetime.now(UTC))
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE job_schedules SET next_run_at=now()-interval '1 day',retry_at=now()-interval '1 second'"
            )
        job.reset_mock()
        self.assertEqual(poll_once(self.db, job), "retry_scheduled")
        job.run.assert_called_once_with()

    def test_latest_reference_ignores_missing_unvalidated_and_future_rows(self):
        today = datetime.now(UTC).date()
        base = {
            "source": "NASA_POWER",
            "product": "POWER_DAILY",
            "variable": "T2M",
            "time_standard": "UTC",
            "value": 20.0,
            "unit": "C",
            "quality": "provider_value_unvalidated",
            "resolution": "test-only",
        }
        rows = [
            {**base, "date": (today - timedelta(days=10)).isoformat()},
            {**base, "date": (today - timedelta(days=3)).isoformat(), "value": None},
            {**base, "date": (today - timedelta(days=2)).isoformat(), "quality": "out_of_range"},
            {**base, "date": today.isoformat()},
        ]
        self.repo.store_recent("antioquia-reference", rows, today - timedelta(days=30))
        self.assertEqual(
            self.repo.latest_observation_date("antioquia-reference", today),
            today - timedelta(days=10),
        )
        result = TestClient(create_app(self.repo)).get(
            "/api/v1/regions/antioquia-reference/latest-analysis"
        )
        self.assertEqual(
            result.json()["request"]["reference_date"], (today - timedelta(days=10)).isoformat()
        )
        self.assertIsNone(self.repo.latest_observation_date("unknown-region", today))

    def test_current_query_does_not_relabel_an_old_forecast_period(self):
        from packages.contracts.api import AnalysisRequest, AnalysisResult

        reference = date(2024, 1, 1)
        row = {
            "source": "NASA_POWER",
            "product": "POWER_DAILY",
            "date": reference.isoformat(),
            "variable": "T2M",
            "time_standard": "UTC",
            "value": 20.0,
            "unit": "C",
            "quality": "provider_value_unvalidated",
            "resolution": "test-only",
        }
        self.repo.store_recent("antioquia-reference", [row], reference)
        old_request = AnalysisRequest(
            region_id="antioquia-reference",
            reference_date=reference,
            horizon_days=7,
            forecast_start_date=date(2024, 1, 2),
        )
        self.repo.save_analysis(
            AnalysisResult(
                status="pending_recommendations",
                request=old_request,
                analysis_id="fixture-old-forecast-period",
                input_snapshot_id="fixture-inputs",
            )
        )
        current_request = AnalysisRequest(
            region_id="antioquia-reference",
            reference_date=reference,
            horizon_days=7,
            forecast_start_date=date(2026, 1, 5),
        )
        self.assertIsNone(self.repo.analysis_for(current_request))
        self.assertEqual(
            self.repo.analysis_for(old_request)["analysis_id"], "fixture-old-forecast-period"
        )
        response = TestClient(create_app(self.repo)).get(
            "/api/v1/regions/antioquia-reference/latest-analysis?as_of=2026-01-05"
        )
        self.assertEqual(response.json()["request"]["forecast_start_date"], "2026-01-05")
        self.assertEqual(response.json()["request"]["reference_date"], "2024-01-01")
        self.assertEqual(response.json()["status"], "pending_run")

    def test_pretrained_period_uses_feature_cutoff_and_never_prefers_later_missing_input_status(
        self,
    ):
        from packages.contracts.api import AnalysisRequest, AnalysisResult, Forecast, ForecastValue

        request = AnalysisRequest(
            region_id="antioquia-reference",
            reference_date=date(2022, 1, 6),
            forecast_start_date=date(2022, 1, 9),
            horizon_days=7,
        )
        forecast = Forecast(
            model_kind="climate",
            model_version="test-only",
            region_id=request.region_id,
            reference_date=request.reference_date,
            forecast_start_date=request.forecast_start_date,
            horizon_days=7,
            values=[ForecastValue(variable="test-only", value=20, unit="C", aggregation="mean")],
        )
        self.repo.save_analysis(
            AnalysisResult(
                status="insufficient_data",
                request=request,
                climate=forecast,
                analysis_id="test-only-real-partial-result",
            )
        )
        self.repo.save_analysis(
            AnalysisResult(
                status="insufficient_data", request=request, analysis_id="test-only-missing-later"
            )
        )
        self.assertEqual(
            self.repo.analysis_for_period(request.region_id, 7, date(2022, 1, 9))["analysis_id"],
            "test-only-real-partial-result",
        )
        self.assertIsNone(self.repo.analysis_for_period(request.region_id, 30, date(2022, 1, 9)))
        response = TestClient(create_app(self.repo)).get(
            "/api/v1/regions/antioquia-reference/latest-analysis?as_of=2022-01-09"
        )
        self.assertEqual(response.json()["request"]["reference_date"], "2022-01-06")
        self.assertEqual(response.json()["analysis_id"], "test-only-real-partial-result")

    def test_weekly_ingestion_uses_completed_days_and_never_runs_inference(self):
        from pipelines.ingestion.sources.nasa.catalog import PRODUCTS

        flow, catalogs = Mock(), Mock()
        flow.run.return_value = {"status": "ok"}
        flow.repository.read.return_value = []
        catalogs.fetch.return_value = {
            "sources": {
                source: {
                    "status": "empty",
                    "data_kind": "granule_catalog",
                    "data": {"granules": []},
                }
                for source in PRODUCTS
            }
        }
        instant = datetime(2026, 1, 2, 1, tzinfo=UTC)
        with (
            patch.dict(os.environ, {"INGESTION_LAG_DAYS": "1"}),
            patch("pipelines.ingestion.flows.weekly.datetime") as clock,
        ):
            clock.now.side_effect = lambda zone: instant.astimezone(zone)
            result = WeeklyIngestionJob(self.repo, flow, catalogs).run()
        self.assertEqual(result["status"], "ok")
        request = catalogs.fetch.call_args.args[0]
        self.assertEqual(request.period.end, date(2025, 12, 31))
        self.assertNotIn("analysis", result["summary"])

    def test_unfiltered_history_includes_old_rows_and_pages_without_losing_update_metadata(self):
        row = {
            "source": "NASA_POWER",
            "product": "POWER_DAILY",
            "date": "2020-01-01",
            "variable": "T2M",
            "time_standard": "UTC",
            "value": 20.0,
            "unit": "C",
            "quality": "provider_value_unvalidated",
            "resolution": "test-only",
        }
        self.repo.store_recent(
            "antioquia-reference", [row, {**row, "date": "2026-11-11"}], date(2020, 1, 1)
        )
        client = TestClient(create_app(self.repo))
        first = client.get("/api/v1/regions/antioquia-reference/observations?limit=1").json()
        second = client.get(
            "/api/v1/regions/antioquia-reference/observations?limit=1&offset=1"
        ).json()
        self.assertEqual(first["total"], 2)
        self.assertEqual(first["first_date"], "2020-01-01")
        self.assertEqual(first["last_date"], "2026-11-11")
        self.assertEqual(first["items"][0]["date"], "2026-11-11")
        self.assertEqual(second["items"][0]["date"], "2020-01-01")
        self.assertEqual(first["last_updated_at"], second["last_updated_at"])
        self.assertIsNotNone(first["last_updated_at"])
        empty = client.get(
            "/api/v1/regions/antioquia-reference/observations?limit=1&offset=2"
        ).json()
        self.assertEqual(empty["items"], [])
        self.assertEqual(empty["total"], 2)
