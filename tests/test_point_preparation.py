"""Datos científicos sintéticos identificados; preparación nativa y cinco modelos reales."""

import copy
import hashlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import h5py
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform

from ml.features.expanded import ExpandedFeatureStore
from ml.inference.daily import DailyModelBundle
from packages.contracts.models import DateRange, GeoPoint
from pipelines.ingestion.flows.model_point import ModelPointPreparation
from pipelines.ingestion.http import IngestionError
from pipelines.ingestion.sources.nasa.harmony_point import HarmonyPointClient
from pipelines.ingestion.sources.nasa.model_inputs import POWER_FIELDS, ModelPointSources
from pipelines.processing.geospatial.model_point import NativePointReader, power_frame

ISSUE = date(2026, 11, 14)
REGION = {"region_id": "test-only-point", "latitude": 6.1, "longitude": -75.3}


def power_payload(region=REGION):
    units = ("C", "C", "C", "%", "g/kg", "m/s", "MJ/m^2/day")
    series = {}
    for field, value in zip(POWER_FIELDS, (20, 15, 25, 70, 10, 2, 18)):
        series[field] = {
            day.strftime("%Y%m%d"): value
            for day in pd.date_range(ISSUE - timedelta(days=60), ISSUE)
        }
    return {
        "point": {"latitude": region["latitude"], "longitude": region["longitude"]},
        "period": {"start": str(ISSUE - timedelta(days=60)), "end": str(ISSUE - timedelta(days=2))},
        "retrieved_at": "2026-11-15T12:00:00Z",
        "raw_responses": [
            {
                "query": {"time-standard": "LST", "parameters": ",".join(POWER_FIELDS)},
                "response": {
                    "geometry": {"coordinates": [region["longitude"], region["latitude"]]},
                    "header": {"time_standard": "LST"},
                    "parameters": {
                        field: {"units": unit} for field, unit in zip(POWER_FIELDS, units)
                    },
                    "properties": {"parameter": series},
                },
            }
        ],
    }


def native_files(root):
    """Small native-format test fixtures, never downloaded NASA measurements."""
    x, y = transform("EPSG:4326", "EPSG:6933", [REGION["longitude"]], [REGION["latitude"]])
    for day in pd.date_range(ISSUE - timedelta(days=60), ISSUE - timedelta(days=2)):
        gpm = root / "GPM" / f"3B-DAY-L.MS.MRG.3IMERG.{day:%Y%m%d}-S000000.3IMERGDL.07.nc4"
        smap = root / "SMAP" / f"SMAP_L3_SM_P_E_{day:%Y%m%d}_R19240_001.nc4"
        gpm.parent.mkdir(exist_ok=True)
        smap.parent.mkdir(exist_ok=True)
        with h5py.File(gpm, "w") as ds:
            ds["lon"] = [-75.4, -75.3, -75.2]
            ds["lat"] = [6.0, 6.1, 6.2]
            ds["time"] = [0.0]
            ds["time"].attrs["units"] = np.bytes_(f"days since {day:%Y-%m-%d} 00:00:00")
            ds["precipitation"] = np.full((1, 3, 3), 4.0)
            ds["precipitation"].attrs.update(
                units=np.bytes_("mm/day"), coordinates=np.bytes_("time lon lat"), _FillValue=-9999.0
            )
        with h5py.File(smap, "w") as ds:
            ds["x_global"] = [x[0] - 9008, x[0], x[0] + 9008]
            ds["y_global"] = [y[0] + 9008, y[0], y[0] - 9008]
            for period, suffix, flag, value in (("AM", "", 0, 0.2), ("PM", "_pm", 1, 0.3)):
                group = ds.create_group("Soil_Moisture_Retrieval_Data_" + period)
                group["soil_moisture" + suffix] = np.full((3, 3), value)
                group["soil_moisture" + suffix].attrs["units"] = np.bytes_("m3/m3")
                group["retrieval_qual_flag" + suffix] = np.full((3, 3), flag)
    terrain = {"elevation_m": 1000.0, "slope_degrees": 10.0}
    for prop in ("sand", "silt", "clay", "soc", "bdod", "wv0010", "wv0033", "wv1500"):
        for statistic in ("mean", "uncertainty"):
            terrain[f"soil_{prop}_{statistic}"] = 10.0
    for key, value in terrain.items():
        if key.startswith("soil_"):
            filename = (
                "soilgrids_v2_0_"
                + key.removeprefix("soil_")
                .replace("_mean", "_0-5cm_mean")
                .replace("_uncertainty", "_0-5cm_uncertainty")
                + ".tif"
            )
            folder = root / "SOILGRIDS"
        else:
            folder = root / "SRTM"
            filename = (
                "srtmgl1_dem_raw.tif" if key == "elevation_m" else "srtmgl1_slope_degrees.tif"
            )
        folder.mkdir(exist_ok=True)
        with rasterio.open(
            folder / filename,
            "w",
            driver="GTiff",
            height=3,
            width=3,
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=from_origin(-75.45, 6.25, 0.1, 0.1),
            nodata=-9999.0,
        ) as ds:
            ds.write(np.full((1, 3, 3), value, dtype="float32"))


class PointPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = ExpandedFeatureStore(self.root / "features")
        self.bundle = DailyModelBundle()

    def producer(self, payload=None):
        sources = Mock()
        sources.acquire.return_value = (
            payload or power_payload(),
            {"POWER": {"state": "downloaded"}},
        )
        return ModelPointPreparation(self.root, self.bundle, self.store, sources=sources)

    def test_observations_are_saved_even_when_other_model_inputs_are_missing(self):
        job = self.producer()
        job.observations = Mock()
        report = job.prepare(REGION, ISSUE)
        self.assertEqual(report["state"], "waiting_inputs")
        self.assertEqual(report["observation_archive"], "saved")
        args = job.observations.store_recent.call_args.args
        self.assertEqual(args[0], REGION["region_id"])
        self.assertEqual(len(args[1]), 59 * 7)
        self.assertEqual({row["time_standard"] for row in args[1]}, {"LST"})
        self.assertTrue(all(Path(row["raw_path"]).exists() for row in args[1]))
        self.assertIsNone(self.store.load(REGION, ISSUE))

    def test_verified_original_keeps_observations_available_if_parquet_is_temporarily_blocked(self):
        job = self.producer()
        job.observations, job.archive = Mock(), Mock()
        job.archive.upsert.side_effect = IngestionError("Bloqueo temporal de escritura de prueba")
        report = job.prepare(REGION, ISSUE)
        self.assertEqual(report["observation_archive"], "pending")
        job.observations.store_recent.assert_called_once()

    def test_native_point_builds_49_and_71_inputs_and_predicts_all_five_variables(self):
        native_files(self.root)
        job = self.producer()
        report = job.prepare(REGION, ISSUE)
        self.assertEqual(report["state"], "completed", report)
        snapshot = self.store.load(REGION, ISSUE)
        self.assertEqual((len(snapshot.climate), len(snapshot.soil)), (49, 71))
        self.assertEqual(snapshot.climate["gpm_late_sum_30d_mm"], 120)
        self.assertEqual(snapshot.climate["t2m_mean_30d"], 20)
        self.assertAlmostEqual(snapshot.soil["smap_mean_7d"], 0.25)
        self.assertEqual(snapshot.soil["smap_nonrecommended_retrievals_7d"], 7)
        self.assertEqual(snapshot.soil["soil_soc_mean"], 1)
        self.assertEqual(snapshot.soil["soil_soc_uncertainty"], 10)
        self.assertEqual((snapshot.latitude, snapshot.longitude), (6.1, -75.3))
        result = self.bundle.predict(snapshot, horizon_days=7)
        self.assertEqual(len(result.climate.daily), 7)
        self.assertEqual(len(result.soil.daily), 7)
        self.assertEqual(len(result.climate.values) + len(result.soil.values), 5)
        archives = list(
            (self.root / "point-inputs").glob(f"*/{ISSUE}/{snapshot.source_sha256}.json")
        )
        self.assertEqual(len(archives), 1)
        self.assertEqual(
            hashlib.sha256(archives[0].read_bytes()).hexdigest(), snapshot.source_sha256
        )

    def test_future_measurements_cannot_change_this_issue_and_missing_rain_is_not_zero(self):
        native_files(self.root)
        original = self.producer().prepare(REGION, ISSUE)
        first = self.store.load(REGION, ISSUE)
        payload = copy.deepcopy(power_payload())
        for field in POWER_FIELDS:
            cutoff = 7 if field == "ALLSKY_SFC_SW_DWN" else 2
            for day in pd.date_range(ISSUE - timedelta(days=cutoff - 1), ISSUE):
                payload["raw_responses"][0]["response"]["properties"]["parameter"][field][
                    day.strftime("%Y%m%d")
                ] = 50
        self.assertEqual(self.producer(payload).prepare(REGION, ISSUE)["state"], "completed")
        second = self.store.load(REGION, ISSUE)
        self.assertEqual(first.climate, second.climate)
        self.assertEqual(first.soil, second.soil)
        self.assertEqual(original["state"], "completed")
        for path in (self.root / "GPM").glob("*.nc4"):
            path.unlink()
        fresh = {**REGION, "region_id": "test-only-missing-rain"}
        report = self.producer().prepare(fresh, ISSUE)
        self.assertEqual(report["state"], "waiting_inputs")
        self.assertIn("gpm_late_sum_30d_mm", report["missing"])
        self.assertIsNone(self.store.load(fresh, ISSUE))

    def test_wrong_point_utc_units_and_missing_static_never_produce_a_snapshot(self):
        payload = power_payload({**REGION, "latitude": 6.2})
        self.assertIn(
            "punto solicitado", self.producer(payload).prepare(REGION, ISSUE)["preparation_error"]
        )
        payload = power_payload()
        payload["raw_responses"][0]["query"]["time-standard"] = "UTC"
        with self.assertRaisesRegex(ValueError, "LST"):
            power_frame(payload, pd.date_range(ISSUE - timedelta(days=60), ISSUE))
        payload = power_payload()
        payload["raw_responses"][0]["response"]["parameters"]["QV2M"]["units"] = "kg/kg"
        with self.assertRaisesRegex(ValueError, "Unidad"):
            power_frame(payload, pd.date_range(ISSUE - timedelta(days=60), ISSUE))
        report = self.producer().prepare(REGION, ISSUE)
        self.assertIn("SRTM", report["missing"][0])
        self.assertIsNone(self.store.load(REGION, ISSUE))

    def test_five_day_old_measurements_preserve_query_forecast_dates_and_causal_age_flags(self):
        native_files(self.root)
        last = ISSUE - timedelta(days=4)  # Consulta ISSUE+1: datos de hace cinco días.
        payload = power_payload()
        payload["period"]["end"] = last.isoformat()
        for series in payload["raw_responses"][0]["response"]["properties"]["parameter"].values():
            for key in list(series):
                if key > last.strftime("%Y%m%d"):
                    del series[key]
        for folder in ("GPM", "SMAP"):
            for path in (self.root / folder).glob("*.nc4"):
                if any(
                    day.strftime("%Y%m%d") in path.name
                    for day in pd.date_range(last + timedelta(days=1), ISSUE)
                ):
                    path.unlink()
        report = self.producer(payload).prepare(REGION, ISSUE)
        self.assertEqual(report["state"], "completed", report)
        snapshot = self.store.load(REGION, ISSUE)
        self.assertEqual(snapshot.climate["t2m_age_days"], 2)
        self.assertEqual(snapshot.climate["gpm_age_days"], 2)
        self.assertEqual(snapshot.soil["smap_age_days"], 2)
        self.assertEqual(snapshot.climate["input_rain_filled_days_30d"], 2)
        result = self.bundle.predict(snapshot, horizon_days=7)
        self.assertEqual(result.request.forecast_start_date, ISSUE + timedelta(days=1))
        self.assertEqual(result.climate.daily[-1].date, ISSUE + timedelta(days=7))

    def test_latest_complete_cut_is_built_from_all_sources_and_keeps_original_dates(self):
        native_files(self.root)
        last = ISSUE - timedelta(days=10)
        payload = power_payload()
        payload["period"]["end"] = last.isoformat()
        for series in payload["raw_responses"][0]["response"]["properties"]["parameter"].values():
            for key in list(series):
                if key > last.strftime("%Y%m%d"):
                    del series[key]
        for folder in ("GPM", "SMAP"):
            for path in (self.root / folder).glob("*.nc4"):
                if any(
                    day.strftime("%Y%m%d") in path.name
                    for day in pd.date_range(last + timedelta(days=1), ISSUE)
                ):
                    path.unlink()

        report = self.producer(payload).prepare(REGION, ISSUE)
        selected = ISSUE - timedelta(days=5)
        self.assertEqual(report["state"], "waiting_inputs")
        self.assertEqual(report["latest_complete_issue_date"], selected.isoformat())
        self.assertEqual(len(report["evaluated_issues"]), 6)
        self.assertIsNone(self.store.load(REGION, ISSUE))
        snapshot = self.store.load(REGION, selected)
        self.assertEqual((len(snapshot.climate), len(snapshot.soil)), (49, 71))
        self.assertEqual(
            (snapshot.latitude, snapshot.longitude), (REGION["latitude"], REGION["longitude"])
        )
        self.assertEqual(snapshot.observation_cutoff, selected - timedelta(days=2))
        result = self.bundle.predict(snapshot, horizon_days=7)
        self.assertEqual(result.request.forecast_start_date, selected + timedelta(days=1))
        self.assertEqual(len(result.climate.values) + len(result.soil.values), 5)
        self.assertNotEqual(result.request.forecast_start_date, ISSUE + timedelta(days=1))

    def test_smap_not_attempted_is_rejected_instead_of_becoming_a_target_or_zero(self):
        native_files(self.root)
        for path in (self.root / "SMAP").glob("*.nc4"):
            with h5py.File(path, "a") as ds:
                for period, suffix in (("AM", ""), ("PM", "_pm")):
                    ds["Soil_Moisture_Retrieval_Data_" + period]["retrieval_qual_flag" + suffix][
                        :
                    ] = 2
        report = self.producer().prepare(REGION, ISSUE)
        self.assertEqual(report["state"], "climate_ready", report)
        self.assertIsNone(self.store.load(REGION, ISSUE).soil)

    def test_native_cells_follow_the_selected_longitude(self):
        native_files(self.root)
        last = sorted((self.root / "GPM").glob("*.nc4"))[-1]
        with h5py.File(last, "a") as ds:
            ds["precipitation"][0, 2, 1] = 12.0
        index = pd.date_range(ISSUE - timedelta(days=60), ISSUE)
        reader = NativePointReader()
        original = reader.read(self.root, REGION, index)[0]
        nearby = reader.read(self.root, {**REGION, "longitude": -75.2}, index)[0]
        self.assertEqual(original.loc[pd.Timestamp(ISSUE - timedelta(days=2))], 4.0)
        self.assertEqual(nearby.loc[pd.Timestamp(ISSUE - timedelta(days=2))], 12.0)

    def test_original_global_smap_hdf5_samples_verified_native_grid(self):
        x, y = transform("EPSG:4326", "EPSG:6933", [-75.3], [6.1])
        col = int(np.floor((x[0] + 17367530.4451615) / 9008.055210146))
        row = int(np.floor((7314540.8306386 - y[0]) / 9008.055210146))
        lon, lat = transform(
            "EPSG:6933",
            "EPSG:4326",
            [-17367530.4451615 + (col + 0.5) * 9008.055210146],
            [7314540.8306386 - (row + 0.5) * 9008.055210146],
        )
        path = self.root / "SMAP_L3_SM_P_E_20261112_R19240_001.h5"
        with h5py.File(path, "w") as ds:
            for part, suffix in (("AM", ""), ("PM", "_pm")):
                group = ds.create_group("Soil_Moisture_Retrieval_Data_" + part)
                for field, value in (
                    ("soil_moisture", 0.3),
                    ("retrieval_qual_flag", 0),
                    ("longitude", lon[0]),
                    ("latitude", lat[0]),
                ):
                    var = group.create_dataset(
                        field + suffix,
                        shape=(1624, 3856),
                        chunks=(16, 16),
                        dtype="float64",
                        fillvalue=-9999.0,
                    )
                    var[row, col] = value
                    if field == "soil_moisture":
                        var.attrs["units"] = np.bytes_("cm**3/cm**3")
        values, counts, recommended = NativePointReader.moisture(
            self.root, (-75.3, 6.1), pd.date_range("2026-11-12", ISSUE), []
        )
        self.assertAlmostEqual(values.iloc[0], 0.3)
        self.assertEqual(counts.iloc[0], 2)
        self.assertEqual(recommended.iloc[0], 2)

    def test_harmony_resumes_native_subset_and_downloads_without_resubmitting(self):
        session, downloader = Mock(), Mock()
        bodies = [
            {"jobID": "test-job"},
            {"status": "running"},
            {"status": "successful"},
            {
                "assets": {
                    "native": {
                        "href": "https://example.invalid/SMAP_L3_SM_P_E_20261112_R19240_001.nc4"
                    }
                }
            },
        ]
        session.get.side_effect = [
            Mock(status_code=200, json=Mock(return_value=body)) for body in bodies
        ]
        downloader.download.return_value = {"files": [{"fixture": True}]}
        client = HarmonyPointClient(session=session, downloader=downloader)
        args = (
            {"collection": {"id": "C-test"}},
            GeoPoint(6.1, -75.3),
            DateRange(ISSUE - timedelta(days=60), ISSUE - timedelta(days=2)),
            self.root,
        )
        self.assertEqual(client.acquire(*args, max_bytes=1024)["state"], "subset_pending")
        self.assertEqual(client.acquire(*args, max_bytes=1024)["state"], "downloaded")
        coverage = [call for call in session.get.call_args_list if "rangeset" in call.args[0]]
        self.assertEqual(len(coverage), 1)
        params = dict(coverage[0].kwargs["params"])
        self.assertEqual(params["format"], "application/x-netcdf4")
        self.assertNotIn("outputCrs", params)
        downloader.download.assert_called_once()

    def test_harmony_preserves_rate_limit_without_including_provider_response(self):
        session = Mock()
        session.get.return_value = Mock(status_code=429, headers={"Retry-After": "7200"})
        with self.assertRaises(IngestionError) as error:
            HarmonyPointClient.get_json(session, "https://harmony.earthdata.nasa.gov/test")
        self.assertEqual(error.exception.retry_after_seconds, 7200)

    @patch.dict(os.environ, {}, clear=True)
    def test_public_acquisition_selects_exact_coordinates_products_and_preserves_retry_after(self):
        power, cmr, downloader = Mock(), Mock(), Mock()
        power.fetch_point_daily.side_effect = IngestionError("Limitado", retry_after_seconds=7200)
        cmr.search_product.return_value = {
            "granules": [{"id": "test-only", "data_urls": []}],
            "limit_reached": False,
        }
        sources = ModelPointSources(self.root, power=power, cmr=cmr, downloader=downloader)
        payload, report = sources.acquire(REGION, ISSUE, self.root)
        self.assertIsNone(payload)
        self.assertEqual(report["POWER"]["retry_after_seconds"], 7200)
        self.assertEqual(report["SMAP"]["state"], "requires_earthdata")
        downloader.download.assert_not_called()
        self.assertEqual(
            [call.args[0].short_name for call in cmr.search_product.call_args_list],
            ["GPM_3IMERGDL", "SPL3SMP_E"],
        )
        for call in cmr.search_product.call_args_list:
            self.assertEqual(call.kwargs["point"].longitude, REGION["longitude"])
        self.assertEqual(power.fetch_point_daily.call_args.kwargs["time_standard"], "LST")


if __name__ == "__main__":
    unittest.main()
