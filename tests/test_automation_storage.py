"""Contratos de lectura y persistencia ML. MongoDB real se habilita con TEST_MONGODB_URI."""

import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from apps.api.app.config import Settings
from apps.api.app.main import create_app
from apps.api.app.repositories.mongo import MongoResultsRepository
from packages.contracts.api import AnalysisRequest, AnalysisResult, Forecast, ForecastValue
from packages.contracts.training import ModelRelease


def fixture_release(version="a" * 32, kind="climate", horizon=7):
    return ModelRelease(
        slot=f"test-only:{kind}:{horizon}",
        version=version,
        model_kind=kind,
        region_id="test-only",
        horizon_days=horizon,
        dataset_id="test-only-dataset",
        training_fingerprint=version,
        recipe_version="test-only",
        policy_version="test-only",
        trained_through=date(2024, 1, 1),
        feature_names=["test-only"],
        target_units={"test-only": "unit"},
        artifact_sha256={},
        metrics={},
        created_at=datetime.now(UTC),
    )


class AutomationAPITests(unittest.TestCase):
    def test_api_reads_results_from_selected_store_and_never_invokes_models(self):
        operational, results, registry = Mock(), Mock(), Mock()
        operational.schedules.return_value = []
        registry.published_models.return_value = [fixture_release()]
        registry.recent_training.return_value = []
        request = AnalysisRequest(region_id="test-only", reference_date=date(2024, 1, 1))
        results.analysis_for.return_value = AnalysisResult(
            status="pending_recommendations", request=request, analysis_id="stored-fixture"
        ).model_dump(mode="json")
        client = TestClient(
            create_app(
                operational,
                settings=Settings(results_backend="mongodb"),
                results_repository=results,
                model_registry=registry,
            )
        )
        status = client.get("/api/v1/automation")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["results_backend"], "mongodb")
        self.assertEqual(
            client.post("/api/v1/analyses", json=request.model_dump(mode="json")).json()[
                "analysis_id"
            ],
            "stored-fixture",
        )
        operational.analysis_for.assert_not_called()
        results.save_analysis.assert_not_called()

    def test_unavailable_mongo_returns_503_without_postgres_fallback(self):
        from pymongo.errors import ServerSelectionTimeoutError

        operational = Mock()
        settings = Settings(results_backend="mongodb")
        with patch(
            "apps.api.app.repositories.mongo.mongo_client",
            side_effect=ServerSelectionTimeoutError("synthetic-test"),
        ):
            response = TestClient(create_app(operational, settings=settings)).post(
                "/api/v1/analyses", json={"region_id": "test-only", "reference_date": "2024-01-01"}
            )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("synthetic-test", response.text)
        operational.analysis_for.assert_not_called()

    def test_prediction_version_mismatch_never_persists(self):
        from pipelines.recommendations.job import CropRecommendationJob
        from tests.test_model_lifecycle import MemoryRegistry

        observations, results, factory, artifacts = Mock(), Mock(), Mock(), Mock()
        observations.regions.return_value = [{"region_id": "test-only"}]
        observations.latest_observation_date.return_value = date(2024, 1, 1)
        observations.observations.return_value = [
            {
                "date": "2024-01-01",
                "variable": "T2M",
                "value": 20.0,
                "quality": "provider_value_unvalidated",
            }
        ]
        registry = MemoryRegistry()
        registry.publish(fixture_release(), None)
        registry.publish(fixture_release(version="b" * 32, kind="soil"), None)

        def create(release, directory):
            predictor = Mock()

            def predict(request, *_):
                return Forecast(
                    model_kind=release.model_kind,
                    model_version="incorrect-fixture-version",
                    region_id=request.region_id,
                    reference_date=request.reference_date,
                    forecast_start_date=request.forecast_start_date,
                    horizon_days=request.horizon_days,
                    values=[
                        ForecastValue(
                            variable="test-only", value=1, unit="test-only", aggregation="test-only"
                        )
                    ],
                )

            predictor.predict.side_effect = predict
            return predictor

        factory.create.side_effect = create
        job = CropRecommendationJob(
            observations, results, registry, artifacts, predictor_factory=factory, horizons=(7,)
        )
        outcome = job.run()
        self.assertEqual(outcome["status"], "partial")
        self.assertEqual(outcome["outcomes"][0]["error_type"], "ValueError")
        self.assertEqual(outcome["failed_tasks"], [{"region_id": "test-only", "horizon_days": 7}])
        results.save_analysis.assert_not_called()

    def test_catalog_revision_changes_result_identity_and_missing_version_blocks_publication(self):
        from packages.contracts.api import Recommendations, Rotation
        from pipelines.recommendations.pipeline import CropRecommendationPipeline

        observations, results, climate, soil, engine = Mock(), Mock(), Mock(), Mock(), Mock()
        observations.observations.return_value = [
            {
                "date": "2024-01-01",
                "variable": "T2M",
                "value": 20.0,
                "quality": "provider_value_unvalidated",
            }
        ]
        request = AnalysisRequest(region_id="test-only", reference_date=date(2024, 1, 1))

        def forecast(kind):
            return Forecast(
                model_kind=kind,
                model_version="test-only-v1",
                validation_status="validated",
                region_id=request.region_id,
                reference_date=request.reference_date,
                horizon_days=7,
                values=[
                    ForecastValue(
                        variable="test-only", value=1, unit="test-only", aggregation="test-only"
                    )
                ],
            )

        climate.predict.return_value = forecast("climate")
        soil.predict.return_value = forecast("soil")
        recommendations = Recommendations(
            engine_version="test-only",
            catalog_version="catalog-test-v1",
            alternatives=[
                Rotation(name=str(index), crops=["test-only"], reasons=["synthetic-test"])
                for index in range(3)
            ],
        )
        engine.recommend.return_value = recommendations
        pipeline = CropRecommendationPipeline(
            observations,
            climate,
            soil,
            engine,
            results_repository=results,
            require_catalog_version=True,
        )
        first = pipeline.run(request)
        engine.recommend.return_value = recommendations.model_copy(
            update={"catalog_version": "catalog-test-v2"}
        )
        second = pipeline.run(request)
        self.assertNotEqual(first.analysis_id, second.analysis_id)
        results.save_analysis.reset_mock()
        engine.recommend.return_value = recommendations.model_copy(update={"catalog_version": None})
        with self.assertRaisesRegex(ValueError, "catálogo"):
            pipeline.run(request)
        results.save_analysis.assert_not_called()


@unittest.skipUnless(os.getenv("TEST_MONGODB_URI"), "Requiere TEST_MONGODB_URI (MongoDB real)")
class MongoIntegrationTests(unittest.TestCase):
    def setUp(self):
        from pymongo import MongoClient

        self.name = "fieldshift_test_" + uuid.uuid4().hex
        self.client = MongoClient(os.environ["TEST_MONGODB_URI"], serverSelectionTimeoutMS=3000)
        self.addCleanup(self.client.close)
        self.addCleanup(lambda: self.client.drop_database(self.name))
        self.store = MongoResultsRepository(os.environ["TEST_MONGODB_URI"], self.name)

    def test_model_publication_is_atomic_and_compares_expected_champion(self):
        first = fixture_release()
        self.assertTrue(self.store.publish(first, None))
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda version: self.store.publish(fixture_release(version), first.version),
                    ["b" * 32, "c" * 32],
                )
            )
        self.assertEqual(sum(results), 1)
        self.assertIn(self.store.current(first.slot).version, ("b" * 32, "c" * 32))
        self.assertEqual(self.client[self.name].model_versions.count_documents({}), 3)
        self.assertFalse(self.store.publish(fixture_release("d" * 32), None))
        self.assertEqual(len(self.store.published_models()), 1)

    def test_attempts_and_catalog_are_persistent_and_private_data_is_not_mixed(self):
        self.store.record_attempt("test-fingerprint", {"status": "rejected"})
        self.store.record_attempt("test-fingerprint", {"status": "published"})
        self.store.record_outcomes([])
        other = MongoResultsRepository(os.environ["TEST_MONGODB_URI"], self.name)
        self.assertEqual(other.attempt("test-fingerprint"), {"status": "rejected"})
        self.store.save_catalog_entry("fixture", {"version": "test-only"}, active=False)
        self.assertEqual(other.catalog(), [])
        self.store.save_catalog_entry("fixture", {"version": "test-only"}, active=True)
        self.assertEqual(other.catalog(), [{"version": "test-only"}])
        self.assertNotIn("farmer_users", self.client[self.name].list_collection_names())

    def test_analysis_is_idempotent_and_respects_exact_forecast_period(self):
        request = AnalysisRequest(
            region_id="test-only",
            reference_date=date(2024, 1, 1),
            forecast_start_date=date(2024, 1, 3),
        )
        result = AnalysisResult(
            status="pending_recommendations",
            request=request,
            analysis_id="test-id",
            input_snapshot_id="test-input",
        )
        self.store.save_analysis(result)
        self.store.save_analysis(result)
        self.assertEqual(len(self.store.analyses("test-only")), 1)
        self.assertEqual(self.store.analysis_for(request)["analysis_id"], "test-id")
        self.assertIsNone(
            self.store.analysis_for(
                request.model_copy(update={"forecast_start_date": date(2024, 1, 4)})
            )
        )

    def test_period_lookup_keeps_real_forecast_and_never_relabels_old_day_or_horizon(self):
        request = AnalysisRequest(
            region_id="test-only",
            reference_date=date(2024, 1, 1),
            forecast_start_date=date(2024, 1, 4),
        )
        forecast = Forecast(
            model_kind="climate",
            model_version="test-only",
            region_id="test-only",
            reference_date=request.reference_date,
            forecast_start_date=request.forecast_start_date,
            horizon_days=7,
            values=[ForecastValue(variable="test-only", value=20, unit="C", aggregation="mean")],
        )
        self.store.save_analysis(
            AnalysisResult(
                status="insufficient_data",
                request=request,
                climate=forecast,
                analysis_id="with-forecast",
            )
        )
        self.store.save_analysis(
            AnalysisResult(
                status="insufficient_data", request=request, analysis_id="without-forecast"
            )
        )
        self.assertEqual(
            self.store.analysis_for_period("test-only", 7, date(2024, 1, 4))["analysis_id"],
            "with-forecast",
        )
        self.assertIsNone(self.store.analysis_for_period("test-only", 30, date(2024, 1, 4)))
        self.assertIsNone(self.store.analysis_for_period("test-only", 7, date(2024, 1, 5)))
