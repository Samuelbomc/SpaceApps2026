"""Un modelo disponible no sustituye las entradas de una región y fecha."""

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pipelines.recommendations.job import CropRecommendationJob


class DailyInputDiagnosticsTests(unittest.TestCase):
    def test_missing_snapshot_reports_daily_recipe_without_running_model(self):
        bundle = SimpleNamespace(forecast_type="direct_daily", predict=Mock())
        store = Mock()
        store.load.return_value = None
        job = CropRecommendationJob(
            Mock(), Mock(), Mock(), Mock(), bundled_models=bundle, feature_store=store
        )
        with patch("pipelines.recommendations.job.CropRecommendationPipeline") as pipeline:
            pipeline.return_value.finalize.side_effect = lambda result: result
            result = job._bundled({"region_id": "test-only"}, date(2026, 11, 15), 7)
        self.assertEqual(result.status, "insufficient_data")
        self.assertIsNone(result.climate)
        self.assertIsNone(result.soil)
        self.assertIn("daily-direct-1-60-v1", result.messages[0])
        self.assertIn("2026-11-14", result.messages[0])
        self.assertIn("LST", result.messages[1])
        self.assertNotIn("expanded-v1", " ".join(result.messages))
        store.load.assert_called_once_with({"region_id": "test-only"}, date(2026, 11, 14))
        bundle.predict.assert_not_called()
