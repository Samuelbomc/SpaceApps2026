"""Pruebas de contratos y errores de ingesta, sin conexión a internet."""

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from http.client import IncompleteRead
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from packages.contracts.models import ANTIOQUIA_ORIENTE, BoundingBox, DateRange
from pipelines.ingestion.sources.nasa._cmr import CMRClient
from pipelines.ingestion.sources.nasa.power import PowerClient
from pipelines.ingestion.sources.nasa.catalog import PRODUCTS
from pipelines.processing.cleaning.power import normalize_power_daily
from pipelines.ingestion.sources.nasa._cmr import data_links
from pipelines.ingestion.download import GranuleDownloader, earthdata_session
from pipelines.ingestion.http import IngestionError, JsonHTTPClient, retry_delay

PERIOD = DateRange.parse("2024-01-01", "2024-01-02")


class GeographyTests(unittest.TestCase):
    def test_longitudes_and_invalid_boxes(self):
        self.assertEqual(ANTIOQUIA_ORIENTE.cmr, "-75.583,5.411,-74.6167,6.5866")
        for box in [(-74, 5, -75, 6), (-181, 5, -74, 6), (-75, 6, -74, 5), (-75, 5, float("nan"), 6)]:
            with self.subTest(box=box), self.assertRaises(ValueError):
                BoundingBox(*box)

    def test_dates(self):
        self.assertEqual(PERIOD.cmr, "2024-01-01T00:00:00Z,2024-01-02T23:59:59Z")
        with self.assertRaises(ValueError):
            DateRange.parse("2024-02-01", "2024-01-01")


class HTTPTests(unittest.TestCase):
    def test_cache_and_refresh(self):
        with tempfile.TemporaryDirectory() as folder:
            opener = Mock(side_effect=lambda *a, **kw: io.BytesIO(b'{"value": 1}'))
            client = JsonHTTPClient(Path(folder), opener=opener)
            self.assertEqual(client.get("https://example.test", {"b": 2, "a": 1}), {"value": 1})
            client.get("https://example.test", {"a": 1, "b": 2})
            self.assertEqual(opener.call_count, 1)
            JsonHTTPClient(Path(folder), opener=opener, cache_ttl=0).get("https://example.test", {"a": 1, "b": 2})
            self.assertEqual(opener.call_count, 2)

    def test_rate_limit_retry(self):
        opener = Mock(side_effect=[HTTPError("https://example.test", 429, "", {"Retry-After": "2"}, None),
                                   io.BytesIO(b'{"ok": true}')])
        sleeper = Mock()
        self.assertEqual(JsonHTTPClient(None, opener=opener, sleeper=sleeper).get("https://example.test", {}), {"ok": True})
        sleeper.assert_called_once_with(2)

    def test_permanent_error_not_retried(self):
        opener = Mock(side_effect=HTTPError("https://example.test", 422, "", {}, None))
        with self.assertRaisesRegex(IngestionError, "HTTP 422"):
            JsonHTTPClient(None, opener=opener).get("https://example.test", {})
        self.assertEqual(opener.call_count, 1)

    def test_network_failure_bounded(self):
        opener, sleeper = Mock(side_effect=URLError("offline")), Mock()
        with self.assertRaises(IngestionError):
            JsonHTTPClient(None, opener=opener, sleeper=sleeper).get("https://example.test", {})
        self.assertEqual(opener.call_count, 3)

    def test_bad_json(self):
        with self.assertRaises(IngestionError):
            JsonHTTPClient(None, opener=Mock(side_effect=lambda *a, **kw: io.BytesIO(b"<html>")), sleeper=Mock()).get("https://example.test", {})

    def test_retry_after_http_date(self):
        now = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)
        self.assertEqual(retry_delay("Sat, 14 Nov 2026 12:00:45 GMT", now=now), 45)
        self.assertEqual(retry_delay("Sat, 14 Nov 2026 11:59:00 GMT", now=now), 0)
        self.assertIsNone(retry_delay("invalid"))

    def test_long_server_wait_is_deferred_without_early_request(self):
        opener = Mock(side_effect=HTTPError("https://example.test", 503, "", {"Retry-After": "7200"}, None))
        sleeper = Mock()
        with self.assertRaises(IngestionError) as caught:
            JsonHTTPClient(None, opener=opener, sleeper=sleeper).get("https://example.test", {})
        self.assertEqual(caught.exception.retry_after_seconds, 7200)
        self.assertEqual(opener.call_count, 1)
        sleeper.assert_not_called()

    def test_truncated_json_and_disconnected_stream_recover(self):
        opener = Mock(side_effect=[io.BytesIO(b'{"value":'), IncompleteRead(b"partial"),
                                   io.BytesIO(b'{"value": 1}')])
        sleeper = Mock()
        result = JsonHTTPClient(None, opener=opener, sleeper=sleeper, jitter=lambda a, b: b).get(
            "https://example.test", {})
        self.assertEqual(result, {"value": 1})
        self.assertEqual([call.args[0] for call in sleeper.call_args_list], [1.25, 2.5])

    def test_authentication_failure_not_retried(self):
        for code in (401, 403):
            opener, sleeper = Mock(side_effect=HTTPError("https://example.test", code, "", {}, None)), Mock()
            with self.assertRaises(IngestionError):
                JsonHTTPClient(None, opener=opener, sleeper=sleeper).get("https://example.test", {})
            self.assertEqual(opener.call_count, 1)
            sleeper.assert_not_called()


class PowerTests(unittest.TestCase):
    def test_minimum_window_bbox_filter_units_and_missing(self):
        def response(endpoint, query):
            parameter = query["parameters"]
            self.assertNotIn(",", parameter)
            self.assertGreaterEqual(query["latitude-max"] - query["latitude-min"], 2)
            self.assertGreaterEqual(query["longitude-max"] - query["longitude-min"], 2)
            self.assertEqual(query["time-standard"], "UTC")
            def feature(lon):
                return {"geometry": {"coordinates": [lon, 6]}, "properties": {"parameter": {
                    parameter: {"20240101": 21, "20240102": -999, "20240103": 99}}}}
            return {"header": {"fill_value": -999, "api": {"version": "v2"}},
                    "parameters": {parameter: {"units": "C"}}, "features": [feature(-75), feature(-76)]}
        http = Mock()
        http.get.side_effect = response
        output = normalize_power_daily(PowerClient(http).fetch_daily(PERIOD, parameters=("T2M", "T2M_MAX", "T2M")))
        self.assertEqual(http.get.call_count, 2)
        self.assertEqual(len(output["records"]), 4)
        self.assertEqual(output["records"][0]["unit"], "C")
        self.assertIsNone(output["records"][1]["value"])
        self.assertEqual(output["records"][1]["quality"], "missing")
        self.assertTrue(all(row["longitude"] == -75 for row in output["records"]))
        self.assertEqual(output["bbox"], ANTIOQUIA_ORIENTE.as_dict())

    def test_expansion_at_world_boundary(self):
        http = Mock()
        http.get.return_value = {"features": [], "header": {}}
        PowerClient(http).fetch_daily(PERIOD, BoundingBox(179.5, 89.5, 180, 90), ("T2M",))
        query = http.get.call_args.args[1]
        self.assertEqual((query["longitude-min"], query["longitude-max"]), (178, 180))
        self.assertEqual((query["latitude-min"], query["latitude-max"]), (88, 90))

    def test_invalid_provider_structure(self):
        http = Mock()
        http.get.return_value = {"messages": ["invalid"]}
        with self.assertRaises(IngestionError):
            PowerClient(http).fetch_daily(PERIOD)


class CMRTests(unittest.TestCase):
    def test_all_products_pinned_and_spatial_temporal_queries(self):
        for source, product in PRODUCTS.items():
            with self.subTest(source=source):
                http = Mock()
                http.get.side_effect = [{"feed": {"entry": [{"id": "C1"}]}}, {"feed": {"entry": []}}]
                result = CMRClient(http).search(source, PERIOD)
                query = http.get.call_args_list[0].args[1]
                self.assertEqual((query["short_name"], query["version"], query["provider"]),
                                 (product.short_name, product.version, product.provider))
                self.assertEqual(result["query"]["bounding_box"], ANTIOQUIA_ORIENTE.cmr)
                self.assertEqual("temporal" in result["query"], not product.static)

    def test_pagination_limit(self):
        http = Mock()
        http.get.side_effect = [{"feed": {"entry": [{"id": "C1"}]}},
                                {"feed": {"entry": [{"id": "G1"}, {"id": "G2"}]}},
                                {"feed": {"entry": [{"id": "G3"}, {"id": "G4"}]}}]
        result = CMRClient(http).search("gpm", PERIOD, limit=3, page_size=2)
        self.assertEqual([g["id"] for g in result["granules"]], ["G1", "G2", "G3"])
        self.assertTrue(result["limit_reached"])
        self.assertEqual(http.get.call_args_list[-1].args[1]["page_num"], 2)

    def test_static_srtm_without_dates(self):
        http = Mock()
        http.get.side_effect = [{"feed": {"entry": [{"id": "C1"}]}}, {"feed": {"entry": []}}]
        self.assertFalse(CMRClient(http).search("srtm")["temporal_filter_applied"])
        with self.assertRaises(ValueError):
            CMRClient(http).search("smap")

    def test_ambiguous_collection_rejected(self):
        http = Mock()
        http.get.return_value = {"feed": {"entry": [{"id": "C1"}, {"id": "C2"}]}}
        with self.assertRaises(IngestionError):
            CMRClient(http).search("gpm", PERIOD)

    def test_link_filter(self):
        relation = "http://esipfed.org/ns/fedsearch/1.1/"
        links = [{"href": "https://example.test/data.nc", "rel": relation + "data#"},
                 {"href": "https://example.test/data.nc", "rel": relation + "data#"},
                 {"href": "https://example.test/preview.png", "rel": relation + "browse#"},
                 {"href": "https://example.test/inherited", "rel": relation + "data#", "inherited": True}]
        self.assertEqual(data_links({"links": links}), ["https://example.test/data.nc"])


class DownloadTests(unittest.TestCase):
    def manifest(self):
        return {"product": PRODUCTS["landsat"].as_dict(), "bbox": ANTIOQUIA_ORIENTE.as_dict(),
                "granules": [{"id": "G1", "data_urls": ["https://example.test/scene.B04.tif",
                                                          "https://example.test/scene.B05.tif"]}]}

    def session(self, chunks=(b"raster",), length="6", content_type="image/tiff"):
        response = Mock(status_code=200, headers={"Content-Length": length, "Content-Type": content_type})
        response.iter_content.return_value = iter(chunks)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        session = Mock()
        session.get.return_value = response
        return session

    def test_selection_download_checksum_and_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            session = self.session()
            downloader = GranuleDownloader(session)
            result = downloader.download(self.manifest(), Path(folder), patterns=("*B04.tif",))
            self.assertEqual(Path(result["files"][0]["path"]).read_bytes(), b"raster")
            self.assertFalse(result["files"][0]["subset_applied"])
            cached = downloader.download(self.manifest(), Path(folder), patterns=("*B04.tif",))
            self.assertTrue(cached["files"][0]["cached"])
            self.assertEqual(session.get.call_count, 1)

    def test_stream_limit_cleans_partial_file(self):
        with tempfile.TemporaryDirectory() as folder:
            downloader = GranuleDownloader(self.session((b"a" * 5, b"b" * 5), length=""))
            with self.assertRaisesRegex(IngestionError, "límite de bytes"):
                downloader.download(self.manifest(), Path(folder), max_bytes=7)
            self.assertEqual(list(Path(folder).rglob("*.part")), [])
            self.assertEqual(list(Path(folder).rglob("*.tif")), [])

    def test_oversize_html_and_incomplete(self):
        for kwargs, budget in [({"length": "1000"}, 10), ({"content_type": "text/html"}, 100), ({"length": "8"}, 100)]:
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(IngestionError):
                    GranuleDownloader(self.session(**kwargs)).download(self.manifest(), Path(folder), max_bytes=budget)
                self.assertEqual(list(Path(folder).rglob("*.tif")), [])

    def test_missing_credentials_no_prompt(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(IngestionError, "EARTHDATA_TOKEN"):
            earthdata_session()

    def test_empty_selection_needs_no_login(self):
        self.assertEqual(GranuleDownloader().download(self.manifest(), Path("unused"), patterns=("*.h5",))["files"], [])



if __name__ == "__main__":
    unittest.main()
