"""Prueba el AOI métrico y evita confundir metadatos con observaciones raster."""

import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from packages.contracts import DateRange, GeoPoint
from pipelines.processing.geospatial.aoi import square_aoi
from scripts.probe_area import (
    normalize_catalog,
    probe_public_access,
    probe_public_sample,
    run_probe,
    science_url,
)


@unittest.skipUnless(importlib.util.find_spec("geographiclib"), "Requiere extra geospatial")
class SmallAOITests(unittest.TestCase):
    def test_ten_meter_dimensions_area_and_closed_lon_lat_geometry(self):
        area = square_aoi(GeoPoint(6.2442, -75.5812))
        props = area["properties"]
        self.assertAlmostEqual(props["east_west_center_m"], 10, places=5)
        self.assertAlmostEqual(props["north_south_center_m"], 10, places=5)
        self.assertAlmostEqual(props["area_geodesic_m2"], 100, places=2)
        ring = area["geometry"]["coordinates"][0]
        self.assertEqual(ring[0], ring[-1])
        self.assertLess(ring[0][0], -75)
        self.assertGreater(ring[0][1], 6)

    def test_area_id_is_stable_and_changes_with_size(self):
        center = GeoPoint(0, 0)
        self.assertEqual(
            square_aoi(center)["properties"]["aoi_id"], square_aoi(center)["properties"]["aoi_id"]
        )
        self.assertNotEqual(
            square_aoi(center)["properties"]["aoi_id"],
            square_aoi(center, 20)["properties"]["aoi_id"],
        )

    def test_invalid_size_rejected(self):
        for size in (0, -1, float("nan"), 1001):
            with self.subTest(size=size), self.assertRaises(ValueError):
                square_aoi(GeoPoint(6, -75), size)


class PublicAccessTests(unittest.TestCase):
    def test_head_probe_does_not_download_or_authenticate(self):
        seen = []

        def opener(request, timeout):
            seen.append(request)
            raise HTTPError(request.full_url, 401, "", {}, io.BytesIO())

        result = probe_public_access("https://data.nasa.gov/science.nc", opener=opener)
        self.assertEqual(result["status"], "authentication_required")
        self.assertFalse(result["science_values_read"])
        self.assertEqual(seen[0].get_method(), "HEAD")
        self.assertNotIn("Authorization", seen[0].headers)

    def test_selects_science_band_and_not_xml_or_preview(self):
        granules = [
            {"data_urls": ["https://x.nasa.gov/meta.xml", "https://x.nasa.gov/HLS.B04.tif"]}
        ]
        self.assertTrue(science_url("landsat", granules).endswith("B04.tif"))
        self.assertIsNone(science_url("smap", granules))

    def test_get_probe_distinguishes_download_denied_from_head_metadata(self):
        seen = []

        def opener(request, timeout):
            seen.append(request)
            raise HTTPError(request.full_url, 401, "", {}, io.BytesIO())

        result = probe_public_sample("https://data.nasa.gov/science.nc", opener=opener)
        self.assertEqual(result["http_status"], 401)
        self.assertEqual(result["bytes_read"], 0)
        self.assertEqual(seen[0].get_method(), "GET")
        self.assertEqual(seen[0].headers["Range"], "bytes=0-15")

    def test_get_probe_is_bounded_even_when_range_is_ignored(self):
        class Response(io.BytesIO):
            status = 200
            headers = {"Content-Type": "application/octet-stream"}

        response = Response(b"x" * 1000)
        result = probe_public_sample(
            "https://data.nasa.gov/science.nc", opener=lambda *a, **k: response
        )
        self.assertEqual(result["bytes_read"], 16)
        self.assertFalse(result["science_values_read"])

    def test_invalid_file_size_is_not_a_measurement(self):
        result = {
            "data": {
                "product": {"short_name": "TEST", "version": "1", "resolution": "30 m"},
                "granules": [
                    {
                        "id": "G1",
                        "start": "2026-01-01T00:00:00Z",
                        "end": None,
                        "size_mb_reported": "NaN",
                        "data_urls": [],
                        "raw_metadata": {},
                    }
                ],
            }
        }
        row = normalize_catalog("landsat", result, "aoi-test")[0]
        self.assertIsNone(row["file_size_reported_mb"])
        self.assertFalse(row["science_values_read"])
        self.assertEqual(row["observed_start"], "2026-01-01T00:00:00+00:00")


@unittest.skipUnless(
    importlib.util.find_spec("geographiclib") and importlib.util.find_spec("pyarrow"),
    "Requiere extras storage y geospatial",
)
class AreaProbeIntegrationTests(unittest.TestCase):
    def test_power_uses_center_and_catalog_uses_exact_area_without_fabricated_raster_values(self):
        class Service:
            def __init__(self):
                self.queries = []

            def fetch(self, query, *, sources):
                self.queries.append((query, sources))
                if sources == ("power",):
                    params = query.power_parameters
                    units = {
                        p: "%"
                        if p == "RH2M"
                        else "m/s"
                        if p == "WS10M"
                        else "MJ/m^2/day"
                        if p == "ALLSKY_SFC_SW_DWN"
                        else "C"
                        for p in params
                    }
                    raw = {
                        "point": query.point.as_dict(),
                        "period": query.period.as_dict(),
                        "retrieved_at": "2026-11-14T00:00:00Z",
                        "raw_responses": [
                            {
                                "query": {"parameters": ",".join(params)},
                                "response": {
                                    "header": {"time_standard": "UTC", "fill_value": -999},
                                    "geometry": {"coordinates": [-75.5812, 6.2442]},
                                    "parameters": {p: {"units": units[p]} for p in params},
                                    "properties": {
                                        "parameter": {p: {"20260101": 20} for p in params}
                                    },
                                },
                            }
                        ],
                    }
                    return {
                        "sources": {
                            "power": {
                                "data": raw,
                                "status": "ok",
                                "error": None,
                                "metadata": {"spatial_resolution": "native"},
                            }
                        }
                    }
                return {
                    "sources": {
                        s: {
                            "data": {"granules": []},
                            "status": "empty",
                            "error": None,
                            "metadata": {"spatial_resolution": "native"},
                        }
                        for s in sources
                    }
                }

        import pyarrow.parquet as pq

        service = Service()
        with tempfile.TemporaryDirectory() as folder, patch("sys.stdout", new_callable=io.StringIO):
            output = Path(folder) / "probe"
            result = run_probe(
                GeoPoint(6.2442, -75.5812),
                DateRange.parse("2026-01-01", "2026-01-01"),
                output,
                service=service,
                check_access=False,
            )
            self.assertIsNotNone(service.queries[0][0].point)
            self.assertIsNotNone(service.queries[1][0].bbox)
            self.assertIsNone(service.queries[1][0].point)
            self.assertEqual(result["sources"]["power"]["records"], 6)
            self.assertFalse(result["sources"]["smap"]["science_values_read"])
            rows = pq.read_table(output / "power-observations.parquet").to_pylist()
            self.assertEqual({r["aoi_id"] for r in rows}, {result["aoi"]["aoi_id"]})
            self.assertEqual(
                json.loads((output / "summary.json").read_text())["access_mode"], "public_only"
            )


if __name__ == "__main__":
    unittest.main()
