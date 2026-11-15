"""Prueba el flujo real de procesamiento y Parquet, sin consumir la red."""

import importlib.util
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from packages.contracts import DataQuery, DateRange, GeoPoint
from packages.contracts.observations import power_location_id
from pipelines.ingestion.flows.power import PowerIngestionFlow
from pipelines.ingestion.http import IngestionError
from pipelines.ingestion.storage.power import LEGACY_SCHEMA_KEY, PowerParquetRepository
from pipelines.processing.cleaning.power_point import process_power_point

POINT = GeoPoint(6.2442, -75.5812)
TODAY = date(2026, 11, 14)


class FakePowerClient:
    def __init__(self):
        self.calls = []
        self.overrides = {}
        self.fail_at = None

    def fetch_point_daily(self, period, point, parameters):
        self.calls.append((period, point, parameters))
        if len(self.calls) == self.fail_at:
            raise IngestionError("Fallo de red simulado")
        series = {}
        for variable in parameters:
            values, day = {}, period.start
            while day <= period.end:
                values[day.strftime("%Y%m%d")] = self.overrides.get(
                    (day.isoformat(), variable), 20.5
                )
                day += timedelta(days=1)
            series[variable] = values
        units = {"T2M": "C", "RH2M": "%", "WS10M": "m/s", "ALLSKY_SFC_SW_DWN": "MJ/m^2/day"}
        return {
            "source": "power",
            "point": point.as_dict(),
            "period": period.as_dict(),
            "retrieved_at": "2026-11-14T00:00:00+00:00",
            "raw_responses": [
                {
                    "query": {"parameters": ",".join(parameters)},
                    "response": {
                        "geometry": {"coordinates": [point.longitude, point.latitude]},
                        "header": {
                            "time_standard": "UTC",
                            "fill_value": -999,
                            "api": {"version": "test"},
                            "sources": ["MERRA2", "SYN1DEG"],
                        },
                        "parameters": {v: {"units": units[v]} for v in parameters},
                        "properties": {"parameter": series},
                    },
                }
            ],
        }


def query(start="2024-01-01", end="2024-01-03", parameters=("T2M",)):
    return DataQuery(point=POINT, period=DateRange.parse(start, end), power_parameters=parameters)


class PowerProcessingTests(unittest.TestCase):
    def test_dates_units_identity_and_provenance(self):
        request = query(parameters=("T2M", "WS10M", "ALLSKY_SFC_SW_DWN"))
        raw = FakePowerClient().fetch_point_daily(request.period, POINT, request.power_parameters)
        records = process_power_point(raw)
        self.assertEqual(len(records), 9)
        self.assertEqual({r["unit"] for r in records}, {"C", "m/s", "MJ/m^2/day"})
        self.assertEqual({r["location_id"] for r in records}, {power_location_id(POINT)})
        self.assertTrue(all(r["cell_id"] is None and r["product_version"] is None for r in records))
        self.assertTrue(
            all(r["api_version"] == "test" and len(r["response_sha256"]) == 64 for r in records)
        )
        self.assertEqual(
            raw["raw_responses"][0]["response"]["properties"]["parameter"]["T2M"]["20240101"], 20.5
        )

    def test_missing_nonfinite_and_invalid_values_do_not_become_zero(self):
        for bad, quality in [
            (-999, "missing"),
            (None, "missing"),
            (float("nan"), "invalid_value"),
            ("23.1", "invalid_value"),
            (True, "invalid_value"),
        ]:
            with self.subTest(bad=bad):
                client = FakePowerClient()
                client.overrides[("2024-01-01", "T2M")] = bad
                request = query(end="2024-01-01")
                row = process_power_point(
                    client.fetch_point_daily(request.period, POINT, ("T2M",))
                )[0]
                self.assertIsNone(row["value"])
                self.assertEqual(row["quality"], quality)

    def test_absent_dates_and_variables_are_explicit_missing_rows(self):
        request = query(parameters=("T2M", "RH2M"))
        raw = FakePowerClient().fetch_point_daily(request.period, POINT, request.power_parameters)
        series = raw["raw_responses"][0]["response"]["properties"]["parameter"]
        del series["T2M"]["20240102"]
        del series["RH2M"]
        rows = process_power_point(raw)
        self.assertEqual(len(rows), 6)
        self.assertEqual(sum(row["quality"] == "missing" for row in rows), 4)

    def test_humidity_range_is_flagged_but_original_value_is_kept(self):
        client = FakePowerClient()
        client.overrides[("2024-01-01", "RH2M")] = 120
        request = query(end="2024-01-01", parameters=("RH2M",))
        row = process_power_point(client.fetch_point_daily(request.period, POINT, ("RH2M",)))[0]
        self.assertEqual((row["value"], row["quality"]), (120, "out_of_range"))

    def test_missing_units_bad_dates_and_time_standard_fail(self):
        for issue in ("units", "date", "time", "malformed_metadata"):
            with self.subTest(issue=issue):
                raw = FakePowerClient().fetch_point_daily(query().period, POINT, ("T2M",))
                payload = raw["raw_responses"][0]["response"]
                if issue == "units":
                    payload["parameters"]["T2M"] = {}
                elif issue == "date":
                    payload["properties"]["parameter"]["T2M"]["20249999"] = 20
                elif issue == "time":
                    payload["header"]["time_standard"] = "LST"
                else:
                    payload["parameters"] = None
                with self.assertRaises(IngestionError):
                    process_power_point(raw)


@unittest.skipUnless(importlib.util.find_spec("pyarrow"), "Requiere el extra storage (PyArrow)")
class PowerParquetFlowTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.client = FakePowerClient()
        self.repository = PowerParquetRepository(self.root / "observations")
        self.flow = PowerIngestionFlow(self.client, self.repository, self.root / "raw")

    def run_flow(self, request=None, **options):
        return self.flow.run(request or query(), today=TODAY, **options)

    def test_first_ingest_then_repeat_makes_no_http_request_or_duplicate(self):
        first = self.run_flow()
        second = self.run_flow()
        self.assertEqual((first["inserted"], first["remaining_gap_days"]), (3, 0))
        self.assertEqual(second["chunks"], [])
        self.assertEqual(len(self.client.calls), 1)
        rows = self.repository.read(POINT, query().period)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(Path(row["raw_path"]).exists() for row in rows))

    def test_incremental_extension_only_fetches_new_dates(self):
        self.run_flow()
        result = self.run_flow(query(end="2024-01-05"))
        self.assertEqual(result["inserted"], 2)
        self.assertEqual(self.client.calls[-1][0], DateRange.parse("2024-01-04", "2024-01-05"))
        self.assertEqual(len(self.repository.read(POINT, query(end="2024-01-05").period)), 5)

    def test_historical_partitions_remain_readable_and_new_writes_use_agrogeo_metadata(self):
        import pyarrow.parquet as pq

        self.run_flow()
        path = next(self.repository.root.rglob("*.parquet"))
        table = pq.ParquetFile(path).read()
        self.assertEqual(table.schema.metadata, {b"agrogeo_schema": b"power_observation_v1"})
        expected = self.repository.read(POINT, query().period)
        pq.write_table(
            table.replace_schema_metadata({LEGACY_SCHEMA_KEY: b"power_observation_v1"}), path
        )
        self.assertEqual(self.repository.read(POINT, query().period), expected)
        extended = query(end="2024-01-05")
        self.run_flow(extended)
        self.assertEqual(len(self.repository.read(POINT, extended.period)), 5)
        self.assertEqual(self.repository.read(POINT, query().period), expected)
        self.assertEqual(
            pq.ParquetFile(path).schema_arrow.metadata,
            {b"agrogeo_schema": b"power_observation_v1"},
        )

    def test_new_variable_backfills_instead_of_using_only_max_date(self):
        self.run_flow()
        result = self.run_flow(query(parameters=("T2M", "RH2M")))
        self.assertEqual(result["inserted"], 3)
        rows = self.repository.read(POINT, query().period)
        self.assertEqual(len(rows), 6)
        self.assertEqual({r["variable"] for r in rows}, {"T2M", "RH2M"})

    def test_nodata_remains_incomplete_and_is_retried(self):
        self.client.overrides[("2024-01-02", "T2M")] = -999
        first = self.run_flow()
        self.assertEqual((first["status"], first["remaining_gap_days"]), ("incomplete", 1))
        self.client.overrides.clear()
        second = self.run_flow()
        self.assertEqual(second["updated"], 1)
        self.assertEqual(self.client.calls[-1][0], DateRange.parse("2024-01-02", "2024-01-02"))
        self.assertEqual(len(self.repository.read(POINT, query().period)), 3)

    def test_force_updates_observation_in_place(self):
        self.run_flow()
        self.client.overrides[("2024-01-01", "T2M")] = 25
        self.run_flow(force=True)
        rows = self.repository.read(POINT, query().period)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["value"], 25)

    def test_recent_window_is_relative_to_today_not_historical_request_end(self):
        request = query("2026-11-10", "2026-11-14")
        self.run_flow(request)
        self.run_flow(request, refresh_days=2)
        self.assertEqual(self.client.calls[-1][0], DateRange.parse("2026-11-13", "2026-11-14"))
        calls = len(self.client.calls)
        self.run_flow(request, refresh_days=0)
        self.assertEqual(len(self.client.calls), calls)

    def test_failure_after_a_chunk_resumes_without_redownloading_committed_days(self):
        self.client.fail_at = 2
        with self.assertRaises(IngestionError):
            self.run_flow(chunk_days=1)
        self.assertEqual(len(self.repository.read(POINT, query().period)), 1)
        self.client.fail_at = None
        result = self.run_flow(chunk_days=1)
        self.assertEqual(result["inserted"], 2)
        self.assertEqual(result["chunks"][0]["start"], "2024-01-02")

    def test_upsert_is_idempotent_and_annual_partition_preserves_other_variables(self):
        request = query("2023-12-31", "2024-01-02", ("T2M", "RH2M"))
        self.run_flow(request)
        rows = self.repository.read(POINT, request.period)
        counts = self.repository.upsert(rows)
        self.assertEqual(counts, {"inserted": 0, "updated": 0, "unchanged": 6})
        self.assertEqual(len(list(self.repository.root.rglob("*.parquet"))), 2)
        self.assertEqual(len(self.repository.read(POINT, request.period, variables=("RH2M",))), 3)

    def test_atomic_write_failure_keeps_previous_partition_and_removes_temp_and_lock(self):
        self.run_flow()
        path = next(self.repository.root.rglob("*.parquet"))
        before = path.read_bytes()
        self.client.overrides[("2024-01-01", "T2M")] = 24
        with patch("pyarrow.parquet.write_table", side_effect=OSError("Disco lleno")):
            with self.assertRaises(OSError):
                self.run_flow(force=True)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((self.repository.root / ".write.lock").exists())
        self.assertEqual(list(self.repository.root.rglob("*.tmp")), [])

    def test_future_dates_fail_before_http(self):
        with self.assertRaises(ValueError):
            self.run_flow(query("2026-11-15", "2026-11-16"))
        self.assertEqual(self.client.calls, [])

    def test_another_location_does_not_share_checkpoint(self):
        self.run_flow()
        other = DataQuery(
            point=GeoPoint(6.25, -75.58), period=query().period, power_parameters=("T2M",)
        )
        result = self.run_flow(other)
        self.assertEqual(result["inserted"], 3)
        self.assertNotEqual(result["location_id"], power_location_id(POINT))
