"""Fallos sintéticos aislados: construcción de jobs y continuidad por región/horizonte."""

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from apps.api.app.config import Settings
from packages.contracts.api import AnalysisRequest, AnalysisResult
from pipelines.recommendations.job import CropRecommendationJob
from scripts.runtime import build_job
from scripts.worker import main


class JobConstructionTests(unittest.TestCase):
    def test_ingestion_does_not_load_ml_configuration_or_results_backend(self):
        settings = Settings(
            training_config_path=Path("fixture-missing-training.json"),
            rotation_water_rules_path=Path("fixture-missing-water.json"),
            results_backend="fixture-invalid-results-backend",
        )
        with (
            patch("scripts.runtime.load_training_config") as config,
            patch("scripts.runtime.runtime_stores") as stores,
        ):
            job = build_job("ingestion", Mock(), settings)
        self.assertIsNotNone(job.flow)
        config.assert_not_called()
        stores.assert_not_called()

    def test_training_does_not_require_recommendation_rules(self):
        job = build_job(
            "training", Mock(), Settings(rotation_water_rules_path=Path("fixture-missing.json"))
        )
        self.assertEqual(len(job.pipeline.policies), 8)

    def test_recommendations_load_published_recipe_without_training_override(self):
        job = build_job(
            "recommendations", Mock(), Settings(training_config_path=Path("fixture-missing.json"))
        )
        self.assertTrue(job.predictor_factory.uses_feature_snapshots)

    def test_worker_constructs_only_selected_job(self):
        with (
            patch("scripts.worker.Database", return_value=MagicMock()),
            patch("scripts.worker.migrate"),
            patch("scripts.worker.build_job", return_value=Mock()) as build,
            patch("scripts.worker.poll_once", return_value="completed"),
        ):
            self.assertEqual(main(["--job", "ingestion", "--once"]), 0)
        self.assertEqual([call.args[0] for call in build.call_args_list], ["ingestion"])

    def test_all_jobs_continue_after_one_configuration_failure(self):
        def build(name, *args):
            if name == "training":
                raise FileNotFoundError("fixture-only configuration unavailable")
            return Mock()

        with (
            patch("scripts.worker.Database", return_value=MagicMock()),
            patch("scripts.worker.migrate"),
            patch("scripts.worker.build_job", side_effect=build) as factory,
            patch("scripts.worker.poll_once", return_value="completed"),
            patch("scripts.worker.poll_background", return_value="completed") as background,
        ):
            self.assertEqual(main(["--job", "all", "--once"]), 1)
        self.assertEqual(
            [call.args[0] for call in factory.call_args_list],
            ["ingestion", "training", "recommendations"],
        )
        self.assertEqual(background.call_args.args[1], "crop-recommendations")


class RecommendationResilienceTests(unittest.TestCase):
    def test_failed_horizon_keeps_other_regions_and_retries_only_failed_task(self):
        observations, results, registry, bundle, features = [Mock() for _ in range(5)]
        observations.regions.return_value = [{"region_id": "fixture-a"}, {"region_id": "fixture-b"}]
        registry.current.return_value = None
        bundle.supports.return_value = True
        # Metadata from unrelated horizons must never block the selected task.
        bundle.catalog.side_effect = AssertionError("Do not validate all horizons at once")
        start = date(2024, 1, 8)
        features.load.side_effect = lambda region, issue: SimpleNamespace(
            region_id=region["region_id"], issue_date=issue
        )
        failures = {("fixture-a", 7)}

        def predict(snapshot, *, horizon_days):
            if (snapshot.region_id, horizon_days) in failures:
                raise ValueError("fixture-secret-must-not-appear-in-results")
            return AnalysisResult(
                status="insufficient_data",
                request=AnalysisRequest(
                    region_id=snapshot.region_id,
                    reference_date=start - timedelta(days=3),
                    forecast_start_date=start,
                    horizon_days=horizon_days,
                ),
            )

        bundle.predict.side_effect = predict
        job = CropRecommendationJob(
            observations,
            results,
            registry,
            Mock(),
            horizons=(7, 15),
            bundled_models=bundle,
            feature_store=features,
        )
        first = job.run(as_of=start)
        self.assertEqual(first["status"], "partial")
        self.assertEqual(len(first["outcomes"]), 4)
        self.assertEqual(first["failed_tasks"], [{"region_id": "fixture-a", "horizon_days": 7}])
        self.assertEqual(results.save_analysis.call_count, 3)
        self.assertNotIn("fixture-secret", json.dumps(first))
        self.assertEqual(first["outcomes"][0]["error_type"], "ValueError")
        bundle.catalog.assert_not_called()
        failures.clear()
        bundle.predict.reset_mock()
        second = job.run(as_of=start, tasks=first["failed_tasks"])
        self.assertEqual(second["status"], "ok")
        self.assertEqual(second["failed_tasks"], [])
        self.assertEqual(len(second["outcomes"]), 1)
        self.assertEqual(bundle.predict.call_count, 1)
        self.assertEqual(results.save_analysis.call_count, 4)

    def test_bundle_support_check_does_not_read_other_horizon_metadata(self):
        from ml.inference.expanded import ExpandedModelBundle

        with tempfile.TemporaryDirectory() as directory:
            bundle = ExpandedModelBundle(Path(directory))
            with patch.object(bundle, "_metadata", side_effect=ValueError("fixture-corrupt-7d")):
                self.assertTrue(bundle.supports(15))
                self.assertFalse(bundle.supports(90))
