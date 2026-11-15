"""Fallos y reinicios simulados; ningún test consulta proveedores externos."""

import copy
import json
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from packages.contracts.models import DateRange, GeoPoint
from pipelines.ingestion.http import IngestionError
from pipelines.ingestion.recovery import SourceRecovery
from pipelines.ingestion.sources.nasa.harmony_point import HarmonyPointClient
from pipelines.ingestion.sources.nasa.model_inputs import ModelPointSources
from tests.test_point_preparation import ISSUE, REGION, power_payload

NOW = datetime(2026, 11, 15, 12, tzinfo=UTC)


@patch.dict(os.environ, {}, clear=True)
class PointResilienceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.power, self.cmr, self.download, self.harmony = Mock(), Mock(), Mock(), Mock()
        self.power.fetch_point_daily.return_value = power_payload()
        self.cmr.search_product.return_value = {
            "granules": [{"id": "test-only", "data_urls": []}],
            "limit_reached": False,
        }
        self.download.download.return_value = {"files": [], "downloaded_bytes": 0}
        self.harmony.acquire.return_value = {"state": "subset_pending", "retry_after_seconds": 300}

    def sources(self):
        return ModelPointSources(
            self.root,
            power=self.power,
            cmr=self.cmr,
            downloader=self.download,
            harmony=self.harmony,
        )

    def test_last_valid_power_survives_failure_and_process_restart_then_recovers(self):
        first, _ = self.sources().acquire(REGION, ISSUE, self.root, now=NOW)
        self.power.fetch_point_daily.side_effect = IngestionError("Timeout simulado")
        later = NOW + timedelta(minutes=16)
        cached, status = self.sources().acquire(REGION, ISSUE, self.root, now=later)
        self.assertEqual(cached, first)
        self.assertTrue(status["POWER"]["cached"])
        self.assertEqual(status["POWER"]["attempts"], 1)
        calls = self.power.fetch_point_daily.call_count
        recovered, deferred = self.sources().acquire(
            REGION, ISSUE, self.root, now=later + timedelta(seconds=1)
        )
        self.assertEqual(recovered, first)
        self.assertEqual(self.power.fetch_point_daily.call_count, calls)
        due = datetime.fromisoformat(deferred["POWER"]["next_attempt_at"])
        self.power.fetch_point_daily.side_effect = None
        _, successful = self.sources().acquire(
            REGION, ISSUE, self.root, now=due + timedelta(seconds=1)
        )
        self.assertEqual(successful["POWER"]["attempts"], 0)
        self.assertEqual(successful["POWER"]["state"], "downloaded")

    def test_empty_weather_on_all_backdated_requests_does_not_replace_last_good_cache(self):
        initial, _ = self.sources().acquire(REGION, ISSUE, self.root, now=NOW)
        empty = copy.deepcopy(initial)
        for series in empty["raw_responses"][0]["response"]["properties"]["parameter"].values():
            for day in series:
                series[day] = -999
        self.power.fetch_point_daily.return_value = empty
        cached, status = self.sources().acquire(
            REGION, ISSUE, self.root, now=NOW + timedelta(minutes=16)
        )
        self.assertEqual(cached, initial)
        self.assertEqual(self.power.fetch_point_daily.call_count, 4)
        self.assertEqual(status["POWER"]["state"], "unavailable")
        self.assertTrue(status["POWER"]["cached"])
        self.assertEqual(json.loads((self.root / "power.json").read_text()), initial)

    def test_rate_limited_source_does_not_block_other_provider_after_restart(self):
        self.power.fetch_point_daily.side_effect = IngestionError(
            "Limitado", retry_after_seconds=7200
        )
        self.cmr.search_product.side_effect = [
            IngestionError("Fallo temporal GPM"),
            {"granules": [{"id": "test-only", "data_urls": []}], "limit_reached": False},
        ]
        _, status = self.sources().acquire(REGION, ISSUE, self.root, now=NOW)
        self.assertEqual(status["POWER"]["retry_after_seconds"], 7200)
        self.cmr.search_product.side_effect = None
        self.cmr.reset_mock()
        self.sources().acquire(REGION, ISSUE, self.root, now=NOW + timedelta(seconds=76))
        self.power.fetch_point_daily.assert_called_once()
        self.cmr.search_product.assert_called_once()
        self.assertEqual(self.cmr.search_product.call_args.args[0].short_name, "GPM_3IMERGDL")

    def test_partial_progress_is_checkpointed_before_an_interruption(self):
        self.cmr.search_product.side_effect = RuntimeError("Interrupción simulada")
        with self.assertRaises(RuntimeError):
            self.sources().acquire(REGION, ISSUE, self.root, now=NOW)
        self.cmr.search_product.side_effect = None
        payload, status = self.sources().acquire(
            REGION, ISSUE, self.root, now=NOW + timedelta(seconds=1)
        )
        self.assertIsNotNone(payload)
        self.assertTrue(status["POWER"]["cached"])
        self.power.fetch_point_daily.assert_called_once()

    def test_cached_power_is_not_reassigned_to_another_coordinate_or_used_if_corrupt(self):
        self.sources().acquire(REGION, ISSUE, self.root, now=NOW)
        (self.root / "power.json").write_text("{}")
        self.power.fetch_point_daily.side_effect = IngestionError("Proveedor caído")
        payload, _ = self.sources().acquire(
            REGION, ISSUE, self.root, now=NOW + timedelta(seconds=1)
        )
        self.assertIsNone(payload)
        other = {**REGION, "latitude": REGION["latitude"] + 0.1}
        payload, _ = self.sources().acquire(other, ISSUE, self.root, now=NOW + timedelta(seconds=2))
        self.assertIsNone(payload)
        self.assertEqual(self.power.fetch_point_daily.call_count, 3)

    def test_configuring_access_releases_auth_wait_without_storing_credentials(self):
        self.sources().acquire(REGION, ISSUE, self.root, now=NOW)
        with patch.dict(os.environ, {"EARTHDATA_TOKEN": "test-only-secret"}):
            _, status = self.sources().acquire(
                REGION, ISSUE, self.root, now=NOW + timedelta(seconds=1)
            )
        self.assertEqual(status["SMAP"]["state"], "subset_pending")
        self.harmony.acquire.assert_called_once()
        self.assertNotIn("test-only-secret", (self.root / "source-recovery.json").read_text())

    def test_source_backoff_grows_caps_and_resets_on_success(self):
        path = self.root / "retry.json"
        now, delays = NOW, []
        for _ in range(10):
            recovery = SourceRecovery(path, "test-context", now, jitter=lambda *_: 0)
            status = recovery.record("GPM", {"state": "unavailable"})
            delays.append(status["retry_after_seconds"])
            now += timedelta(seconds=status["retry_after_seconds"])
        self.assertEqual(delays[:3], [60, 120, 240])
        self.assertEqual(max(delays), 3600)
        final = SourceRecovery(path, "test-context", now).record("GPM", {"state": "downloaded"})
        self.assertEqual(final["attempts"], 0)
        for entry in (
            None,
            {"attempts": 0, "status": {}, "next_attempt_at": (now + timedelta(days=1)).isoformat()},
        ):
            path.write_text(json.dumps({"context": "test-context", "sources": {"GPM": entry}}))
            self.assertTrue(SourceRecovery(path, "test-context", now).due("GPM"))

    def test_harmony_rejects_malformed_json_with_retryable_error(self):
        session = Mock()
        session.get.return_value = Mock(status_code=200, json=Mock(return_value=[]))
        with self.assertRaisesRegex(IngestionError, "JSON incompatible"):
            HarmonyPointClient.get_json(session, "https://harmony.earthdata.nasa.gov/test")

    def test_backoff_starts_when_a_slow_attempt_finishes(self):
        current = [NOW]
        recovery = SourceRecovery(
            self.root / "retry.json",
            "test-context",
            NOW,
            clock=lambda: current[0],
            jitter=lambda *_: 0,
        )
        current[0] += timedelta(minutes=10)
        status = recovery.record("GPM", {"state": "unavailable"})
        self.assertEqual(
            datetime.fromisoformat(status["next_attempt_at"]), current[0] + timedelta(seconds=60)
        )

    def harmony_args(self):
        return (
            {"collection": {"id": "C-test"}},
            GeoPoint(6.1, -75.3),
            DateRange(ISSUE - timedelta(days=60), ISSUE - timedelta(days=2)),
            self.root,
        )

    def test_missing_remote_job_is_recreated_on_next_attempt_without_deleting_files(self):
        (self.root / "harmony-job.json").write_text(json.dumps({"job_id": "old-job"}))
        (self.root / "already-downloaded.nc4").write_bytes(b"test-only-complete-file")
        session = Mock()
        session.get.side_effect = [
            Mock(status_code=404, headers={}),
            Mock(status_code=200, json=Mock(return_value={"jobID": "new-job"})),
            Mock(status_code=200, json=Mock(return_value={"status": "running"})),
        ]
        client = HarmonyPointClient(session=session)
        with self.assertRaises(IngestionError):
            client.acquire(*self.harmony_args(), max_bytes=1024, now=NOW)
        self.assertEqual(
            client.acquire(*self.harmony_args(), max_bytes=1024, now=NOW)["state"], "subset_pending"
        )
        self.assertEqual(
            json.loads((self.root / "harmony-job.json").read_text())["job_id"], "new-job"
        )
        self.assertTrue((self.root / "already-downloaded.nc4").is_file())

    def test_rate_limit_does_not_discard_remote_job(self):
        original = {"job_id": "kept-job"}
        (self.root / "harmony-job.json").write_text(json.dumps(original))
        session = Mock()
        session.get.return_value = Mock(status_code=429, headers={"Retry-After": "7200"})
        with self.assertRaises(IngestionError) as error:
            HarmonyPointClient(session=session).acquire(
                *self.harmony_args(), max_bytes=1024, now=NOW
            )
        self.assertEqual(error.exception.retry_after_seconds, 7200)
        self.assertEqual(json.loads((self.root / "harmony-job.json").read_text()), original)

    def test_expired_results_are_replaced_and_paused_job_is_resumed(self):
        (self.root / "harmony-job.json").write_text(json.dumps({"job_id": "expired-job"}))
        session = Mock()
        session.get.return_value = Mock(
            status_code=200,
            json=Mock(
                return_value={
                    "status": "successful",
                    "dataExpiration": (NOW - timedelta(seconds=1)).isoformat(),
                }
            ),
        )
        with self.assertRaisesRegex(IngestionError, "vencieron"):
            HarmonyPointClient(session=session).acquire(
                *self.harmony_args(), max_bytes=1024, now=NOW
            )
        self.assertNotIn("job_id", json.loads((self.root / "harmony-job.json").read_text()))
        (self.root / "harmony-job.json").write_text(json.dumps({"job_id": "paused-job"}))
        session.get.side_effect = [
            Mock(status_code=200, json=Mock(return_value={"status": state}))
            for state in ("paused", "running")
        ]
        result = HarmonyPointClient(session=session).acquire(
            *self.harmony_args(), max_bytes=1024, now=NOW
        )
        self.assertEqual(result["state"], "subset_pending")
        self.assertTrue(session.get.call_args.args[0].endswith("/paused-job/resume"))

    def test_harmony_asset_identity_survives_signed_link_refresh(self):
        (self.root / "harmony-job.json").write_text(json.dumps({"job_id": "same-job"}))
        session, downloader = Mock(), Mock()
        downloader.download.return_value = {"files": [{"test": True}]}
        client = HarmonyPointClient(session=session, downloader=downloader)
        for token in ("first", "renewed"):
            session.get.side_effect = [
                Mock(status_code=200, json=Mock(return_value={"status": "successful"})),
                Mock(
                    status_code=200,
                    json=Mock(
                        return_value={
                            "id": "same-item",
                            "assets": {
                                "moisture": {
                                    "href": f"https://example.invalid/SMAP_E_20261112_file.nc4?signature={token}"
                                }
                            },
                        }
                    ),
                ),
            ]
            client.acquire(*self.harmony_args(), max_bytes=1024, now=NOW)
        manifests = [call.args[0] for call in downloader.download.call_args_list]
        first, second = [item["granules"][0] for item in manifests]
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["asset_identity"], second["asset_identity"])
        self.assertNotEqual(first["data_urls"], second["data_urls"])


if __name__ == "__main__":
    unittest.main()
