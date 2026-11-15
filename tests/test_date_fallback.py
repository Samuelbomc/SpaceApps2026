"""Búsqueda acotada por fecha: contratos sintéticos, sin llamadas externas."""

import tempfile
import unittest
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from packages.contracts.models import DateRange
from pipelines.ingestion.date_fallback import fetch_with_date_fallback
from pipelines.ingestion.flows.weekly import WeeklyIngestionJob
from pipelines.ingestion.http import IngestionError
from pipelines.ingestion.sources.nasa.model_inputs import ModelPointSources
from tests.test_point_preparation import ISSUE, REGION, power_payload

TODAY = date(2026, 11, 15)
PERIOD = DateRange(TODAY - timedelta(days=60), TODAY - timedelta(days=3))


class DateFallbackTests(unittest.TestCase):
    def test_date_error_and_empty_result_step_back_to_five_days_with_same_history_start(self):
        fetch = Mock(
            side_effect=[
                IngestionError("Fecha no publicada", http_status=422),
                {},
                {"available": True},
            ]
        )
        result, period, attempted = fetch_with_date_fallback(fetch, PERIOD, TODAY, usable=bool)
        self.assertTrue(result["available"])
        self.assertEqual(attempted, ["2026-11-12", "2026-11-11", "2026-11-10"])
        self.assertEqual(period.end, TODAY - timedelta(days=5))
        self.assertTrue(all(call.args[0].start == PERIOD.start for call in fetch.call_args_list))

    def test_auth_rate_limits_and_transport_failures_do_not_trigger_more_date_queries(self):
        for status, delay in ((401, 0), (403, 0), (429, 7200), (503, 0), (None, 0), (422, 3600)):
            with self.subTest(status=status, delay=delay):
                error = IngestionError(
                    "Fallo de prueba", http_status=status, retry_after_seconds=delay
                )
                fetch = Mock(side_effect=error)
                with self.assertRaises(IngestionError) as caught:
                    fetch_with_date_fallback(fetch, PERIOD, TODAY, usable=bool)
                self.assertIs(caught.exception, error)
                fetch.assert_called_once()

    def test_does_not_search_past_the_limit_or_repeat_an_already_older_configured_cutoff(self):
        fetch = Mock(return_value={})
        _, selected, dates = fetch_with_date_fallback(fetch, PERIOD, TODAY, usable=bool)
        self.assertEqual(len(dates), 3)
        self.assertEqual(selected.end, TODAY - timedelta(days=5))
        fetch.reset_mock()
        old = DateRange(PERIOD.start, TODAY - timedelta(days=7))
        _, selected, dates = fetch_with_date_fallback(fetch, old, TODAY, usable=bool)
        self.assertEqual(dates, [old.end.isoformat()])
        self.assertEqual(selected, old)

    @patch.dict("os.environ", {}, clear=True)
    def test_point_power_and_gpm_use_older_query_dates_and_keep_coordinates(self):
        power, cmr = Mock(), Mock()
        power.fetch_point_daily.side_effect = [
            IngestionError("Fecha no disponible", http_status=422),
            power_payload(),
        ]
        available = {"granules": [{"id": "test-only", "data_urls": []}], "limit_reached": False}

        def catalog(product, period, **kwargs):
            if product.short_name == "GPM_3IMERGDL" and period.end > TODAY - timedelta(days=5):
                return {"granules": [], "limit_reached": False}
            return available

        cmr.search_product.side_effect = catalog
        with tempfile.TemporaryDirectory() as folder:
            _, status = ModelPointSources(Path(folder), power=power, cmr=cmr).acquire(
                REGION, ISSUE, Path(folder)
            )
        self.assertEqual(status["POWER"]["query_end"], "2026-11-11")
        self.assertEqual(status["GPM"]["query_end"], "2026-11-10")
        self.assertEqual(len(status["GPM"]["attempted_end_dates"]), 3)
        for call in power.fetch_point_daily.call_args_list:
            self.assertEqual(call.args[1].latitude, REGION["latitude"])
            self.assertEqual(call.args[1].longitude, REGION["longitude"])

    @patch.dict(
        "os.environ", {"INGESTION_LAG_DAYS": "3", "SOURCE_FALLBACK_MAX_LAG_DAYS": "5"}, clear=True
    )
    def test_manual_ingestion_retries_older_cutoffs_without_redownloading_valid_history(self):
        repository, flow = Mock(), Mock()
        repository.region.return_value = REGION
        flow.repository.read.return_value = []
        flow.run.side_effect = [
            {"status": "incomplete"},
            {"status": "incomplete"},
            {"status": "ok"},
        ]
        with patch("pipelines.ingestion.flows.weekly.datetime") as clock:
            instant = datetime(2026, 11, 16, 1, tzinfo=UTC)
            clock.now.side_effect = lambda zone: instant.astimezone(zone)
            result = WeeklyIngestionJob(repository, flow, Mock()).run(sources=("power",))
        dates = [call.args[0].period.end for call in flow.run.call_args_list]
        self.assertEqual([(dates[0] - day).days for day in dates], [0, 1, 2])
        self.assertEqual(dates[-1], TODAY - timedelta(days=5))
        self.assertEqual(flow.run.call_args_list[1].kwargs, {"refresh_days": 0})
        self.assertEqual(flow.run.call_args_list[2].kwargs, {"refresh_days": 0})
        self.assertEqual(repository.store_recent.call_count, 3)
        self.assertEqual(result["status"], "ok")

    def test_last_partial_response_survives_later_date_errors(self):
        partial = {"status": "incomplete", "real_values": [20.0]}
        fetch = Mock(
            side_effect=[
                partial,
                IngestionError("Fecha", http_status=422),
                IngestionError("Fecha", http_status=422),
            ]
        )
        selected, period, _ = fetch_with_date_fallback(
            fetch, PERIOD, TODAY, usable=lambda value: value["status"] == "ok"
        )
        self.assertEqual(selected, partial)
        self.assertEqual(period, PERIOD)

    def test_invalid_limits_are_rejected(self):
        for maximum in (0, -1, 31, True):
            with self.assertRaises(ValueError):
                fetch_with_date_fallback(Mock(), PERIOD, TODAY, usable=bool, max_lag_days=maximum)


if __name__ == "__main__":
    unittest.main()
