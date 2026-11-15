"""Contrato de ubicación común y correlación entre las fuentes NASA."""

import io
import json
import unittest
from unittest.mock import patch

from scripts.ingest import main
from pipelines.ingestion.http import IngestionError
from packages.contracts.models import ANTIOQUIA_ORIENTE, DateRange, GeoPoint
from packages.contracts import DataQuery
from apps.api.app.services.nasa_data import NASADataService


class ProviderHTTP:
    """Simula proveedores y registra las peticiones HTTP efectivas."""

    def __init__(self, *, fail=None, empty=None):
        self.calls = []
        self.fail, self.empty = fail, empty

    def get(self, endpoint, params):
        self.calls.append((endpoint, params))
        if endpoint.endswith("collections.json"):
            if params["short_name"] == self.fail:
                raise IngestionError("Proveedor temporalmente no disponible")
            return {"feed": {"entry": [{"id": "C-" + params["short_name"]}]}}
        if endpoint.endswith("granules.json"):
            name = params["collection_concept_id"]
            entries = [] if self.empty and name == "C-" + self.empty else [{
                "id": "G-" + name, "time_start": "2026-01-01T00:00:00Z",
                "time_end": "2026-01-31T23:59:59Z", "boxes": ["-90 -180 90 180"],
                "links": [{"rel": "http://esipfed.org/ns/fedsearch/1.1/data#",
                           "href": "https://data.example.test/file.nc"}]}]
            return {"feed": {"entry": entries}}
        feature = {"geometry": {"coordinates": [-75, 6]}, "properties": {
            "parameter": {"T2M": {"20260101": -999}}}}
        payload = {"header": {"fill_value": -999, "api": {"version": "test"}},
                   "parameters": {"T2M": {"units": "C"}}}
        if endpoint.endswith("/point"):
            return {**payload, **feature}
        return {**payload, "features": [feature]}


class DataQueryTests(unittest.TestCase):
    def test_json_point_and_stable_correlation(self):
        payload = {"latitude": 6, "longitude": -75, "start": "2026-01-01", "end": "2026-01-31"}
        one = DataQuery.from_dict(payload)
        two = DataQuery.from_dict({**payload, "latitude": 6.0, "longitude": -75.0})
        self.assertEqual(one.query_id, two.query_id)
        self.assertEqual(one.point.cmr, "-75.0,6.0")
        different = DataQuery.from_dict({**payload, "latitude": 6.1})
        self.assertNotEqual(one.query_id, different.query_id)

    def test_json_bbox(self):
        query = DataQuery.from_dict({"bbox": [-75.583, 5.411, -74.6167, 6.5866],
                                     "start": "2026-01-01", "end": "2026-01-31"})
        self.assertEqual(query.bbox, ANTIOQUIA_ORIENTE)
        self.assertIsNone(query.point)

    def test_invalid_inputs_rejected(self):
        invalid = [{}, {"latitude": 6}, {"longitude": -75}, {"latitude": 91, "longitude": 0},
                   {"latitude": 0, "longitude": float("nan")}, {"bbox": [1, 2]},
                   {"latitude": 6, "longitude": -75, "bbox": [1, 2, 3, 4]},
                   {"bbox": [1, 2, 3, 4], "start": "2026-01-01"},
                   {"bbox": [1, 2, 3, 4], "limit": 0},
                   {"bbox": [1, 2, 3, 4], "limit": True},
                   {"bbox": [1, 2, 3, 4], "power_parameters": "T2M"},
                   {"bbox": [1, 2, 3, 4], "unsupported": 1}]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                DataQuery.from_dict(payload)


class UnifiedQueryTests(unittest.TestCase):
    def query(self, **options):
        return DataQuery(period=DateRange.parse("2026-01-01", "2026-01-31"),
                         limit=1, power_parameters=("T2M",), **options)

    def test_one_point_reaches_every_source_without_artificial_bbox(self):
        http = ProviderHTTP()
        query = self.query(point=GeoPoint(6, -75))
        result = NASADataService(http).fetch(query)
        self.assertEqual(set(result["sources"]), {"power", "gpm", "smap", "srtm", "grace",
                                                   "ecostress", "ecostress-lst", "landsat"})
        self.assertEqual(result["status"], "ok")
        for key, source in result["sources"].items():
            with self.subTest(source=key):
                self.assertEqual(source["query_id"], result["query_id"])
                self.assertEqual(source["requested"], query.as_dict())
                self.assertEqual(source["status"], "ok")
                self.assertFalse(source["metadata"]["spatial_alignment_applied"])
                self.assertFalse(source["metadata"]["temporal_alignment_applied"])
        granule_calls = [params for endpoint, params in http.calls if endpoint.endswith("granules.json")]
        self.assertEqual(len(granule_calls), 7)
        for params in granule_calls:
            self.assertEqual(params["point"], "-75,6")
            self.assertNotIn("bounding_box", params)
            self.assertEqual("temporal" in params, params["collection_concept_id"] != "C-SRTMGL1")
        point_calls = [(url, p) for url, p in http.calls if url.endswith("/point")]
        self.assertEqual(len(point_calls), 1)
        self.assertEqual((point_calls[0][1]["latitude"], point_calls[0][1]["longitude"]), (6, -75))
        # Se conserva el sentinel original; no se inventa un dato disponible para ML.
        raw = result["sources"]["power"]["data"]["raw_responses"][0]["response"]
        self.assertEqual(raw["properties"]["parameter"]["T2M"]["20260101"], -999)
        granule = result["sources"]["grace"]["data"]["granules"][0]
        self.assertEqual(granule["raw_metadata"]["boxes"], ["-90 -180 90 180"])

    def test_same_bbox_across_sources_with_explicit_power_expansion(self):
        http = ProviderHTTP()
        result = NASADataService(http).fetch(self.query(bbox=ANTIOQUIA_ORIENTE))
        for endpoint, params in http.calls:
            if endpoint.endswith("granules.json"):
                self.assertEqual(params["bounding_box"], ANTIOQUIA_ORIENTE.cmr)
                self.assertNotIn("point", params)
        power = result["sources"]["power"]["data"]
        self.assertEqual(power["bbox"], ANTIOQUIA_ORIENTE.as_dict())
        self.assertNotEqual(power["query_bbox"], power["bbox"])

    def test_errors_and_empty_sources_do_not_discard_successes(self):
        http = ProviderHTTP(fail="SPL4SMGP", empty="HLSL30")
        result = NASADataService(http).fetch(self.query(point=GeoPoint(6, -75)))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["sources"]["smap"]["status"], "error")
        self.assertIsNone(result["sources"]["smap"]["data"])
        self.assertEqual(result["sources"]["landsat"]["status"], "empty")
        self.assertEqual(result["sources"]["power"]["status"], "ok")

    def test_missing_period_and_invalid_sources_fail_before_requests(self):
        http = ProviderHTTP()
        repository = NASADataService(http)
        with self.assertRaises(ValueError):
            repository.fetch(DataQuery(point=GeoPoint(6, -75)))
        for sources in [(), ("unknown",)]:
            with self.assertRaises(ValueError):
                repository.fetch(self.query(point=GeoPoint(6, -75)), sources=sources)
        self.assertEqual(http.calls, [])

    def test_srtm_can_be_requested_alone_without_period(self):
        result = NASADataService(ProviderHTTP()).fetch(DataQuery(point=GeoPoint(6, -75)), sources=("srtm",))
        self.assertFalse(result["sources"]["srtm"]["metadata"]["temporal_filter_applied"])


class CollectCLITests(unittest.TestCase):
    def test_point_cli_preserves_partial_result_and_returns_failure_code(self):
        with patch("scripts.ingest.JsonHTTPClient", return_value=ProviderHTTP(fail="SPL4SMGP")), \
                patch("sys.stdout", new_callable=io.StringIO) as stdout:
            code = main(["collect", "--latitude", "6", "--longitude", "-75",
                         "--start", "2026-01-01", "--end", "2026-01-31", "--limit", "1"])
            result = json.loads(stdout.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(result["requested"]["location"]["latitude"], 6)
        self.assertEqual(result["status"], "partial")

    def test_collect_rejects_ambiguous_or_missing_location_before_network(self):
        common = ["collect", "--start", "2026-01-01", "--end", "2026-01-31"]
        for flags in [[], ["--latitude", "6"],
                      ["--latitude", "6", "--longitude", "-75", "--bbox", "1", "2", "3", "4"]]:
            with self.subTest(flags=flags), patch("scripts.ingest.JsonHTTPClient") as http, \
                    patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(main(common + flags), 1)
                http.assert_not_called()


if __name__ == "__main__":
    unittest.main()
