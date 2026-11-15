"""Integración real de los artefactos del equipo; no publica modelos en producción."""

import csv
import importlib.util
import json
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.app.main import create_app
from ml.features.daily import daily_snapshot_from_csv as snapshot_from_csv
from ml.features.expanded import ExpandedFeatureStore
from ml.inference.expanded import CLIMATE, HORIZONS, ExpandedModelBundle
from packages.contracts.api import AnalysisResult
from packages.contracts.pretrained import DailyFeatures as ExpandedFeatures
from pipelines.recommendations.job import CropRecommendationJob

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "ml/examples/inputs/moisture.csv"


class PretrainedModelTests(unittest.TestCase):
    def setUp(self):
        self.bundle = ExpandedModelBundle(ROOT / "ml/artifacts")
        catalog = self.bundle.catalog()
        self.climate = catalog.input_contract.climate_features
        self.soil = catalog.input_contract.soil_features
        self.snapshot = snapshot_from_csv(
            SAMPLE,
            region_id="test-only",
            point_id="smap_0",
            issue_date=date(2026, 11, 15),
            climate_features=self.climate,
            soil_features=self.soil,
        )
        self.region = {
            "region_id": "test-only",
            "longitude": self.snapshot.longitude,
            "latitude": self.snapshot.latitude,
            "name": "Solo test",
        }

    def test_catalog_exposes_real_versions_semantics_and_evaluation_metrics(self):
        catalog = self.bundle.catalog()
        self.assertEqual(catalog.supported_horizons, [7, 15, 30, 60])
        self.assertEqual(len(catalog.models), 5)
        soil = next(m for m in catalog.models if m.model_kind == "soil")
        self.assertIn("smap_mean_7d", soil.formula)
        self.assertEqual(len(soil.features), 75)
        self.assertAlmostEqual(soil.evaluation_mae, 0.04584025573013225)
        self.assertEqual(len(catalog.input_contract.climate_features), 49)
        self.assertEqual(len(catalog.input_contract.soil_features), 71)
        self.assertTrue(all(m.validation_status == "experimental" for m in catalog.models))

    def test_http_input_contract_exposes_ordered_columns_without_running_models(self):
        with patch.object(
            self.bundle, "predict", side_effect=AssertionError("HTTP no debe inferir")
        ):
            response = TestClient(create_app(Mock(), pretrained_models=self.bundle)).get(
                "/api/v1/models/input-contract"
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["climate_features"], self.climate)
        self.assertEqual(response.json()["soil_features"], self.soil)
        self.assertEqual(response.json()["input_lag_days"], 2)

    def test_exact_date_geometry_and_cutoff_are_required(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ExpandedFeatureStore(folder)
            store.save(self.snapshot)
            self.assertEqual(store.load(self.region, self.snapshot.issue_date), self.snapshot)
            self.assertEqual(len(list((Path(folder) / "versions").glob("*.json"))), 1)
            revised = self.snapshot.model_copy(update={"source_sha256": "b" * 64})
            store.save(revised)
            self.assertEqual(len(list((Path(folder) / "versions").glob("*.json"))), 2)
            self.assertEqual(store.load(self.region, self.snapshot.issue_date), revised)
            self.assertIsNone(store.load(self.region, self.snapshot.issue_date + timedelta(days=1)))
            with self.assertRaisesRegex(ValueError, "coordenadas"):
                store.load({**self.region, "longitude": -75}, self.snapshot.issue_date)
            with self.assertRaises(ValidationError):
                ExpandedFeatures.model_validate(
                    {**self.snapshot.model_dump(), "observation_cutoff": date(2026, 11, 14)}
                )
            with self.assertRaises(ValidationError):
                ExpandedFeatures.model_validate(
                    {**self.snapshot.model_dump(), "climate": {"T2M": float("nan")}}
                )
            with self.assertRaisesRegex(ValidationError, "mismas variables"):
                ExpandedFeatures.model_validate(
                    {**self.snapshot.model_dump(), "climate": {"t2m_last": 999}}
                )

    def test_import_does_not_select_nearest_date_or_cell(self):
        for point, day in [("wrong-point", date(2026, 11, 15)), ("smap_0", date(2026, 11, 14))]:
            with self.assertRaisesRegex(ValueError, "celda y fecha exactas"):
                snapshot_from_csv(
                    SAMPLE,
                    region_id="test-only",
                    point_id=point,
                    issue_date=day,
                    climate_features=self.climate,
                    soil_features=self.soil,
                )
        self.assertNotIn("target", self.snapshot.climate)
        self.assertNotIn("target", self.snapshot.soil)

    def test_altered_artifact_is_rejected_before_loading_xgboost(self):
        with tempfile.TemporaryDirectory() as folder:
            for horizon in (7,):
                for name in (*CLIMATE, "moisture"):
                    source = self.bundle._directory(name, horizon)
                    destination = Path(folder) / source.relative_to(self.bundle.root)
                    destination.mkdir(parents=True)
                    for filename in ("model.json", "training.json"):
                        shutil.copyfile(source / filename, destination / filename)
            path = Path(folder) / "forecasts/moisture/model.json"
            path.write_text(path.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "no coincide"):
                ExpandedModelBundle(folder).catalog()

    def test_feature_only_csv_is_received_without_future_labels_and_keeps_soil_optional(self):
        with SAMPLE.open() as handle:
            row = next(csv.DictReader(handle))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inputs.csv"
            for include_soil in (True, False):
                columns = [
                    "point_id",
                    "issue_date",
                    "observation_cutoff",
                    "radiation_observation_cutoff",
                    "latitude",
                    "longitude",
                ]
                columns += self.soil if include_soil else self.climate
                with path.open("w", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=columns)
                    writer.writeheader()
                    writer.writerow({key: row[key] for key in columns})
                received = snapshot_from_csv(
                    path,
                    region_id="test-only",
                    point_id="smap_0",
                    issue_date=date(2026, 11, 15),
                    climate_features=self.climate,
                    soil_features=self.soil,
                )
                self.bundle.validate_inputs(received)
                self.assertEqual(received.climate, self.snapshot.climate)
                self.assertEqual(received.soil, self.snapshot.soil if include_soil else None)
                self.assertNotIn("target", received.climate)

    def test_partial_soil_duplicate_headers_and_future_availability_are_rejected(self):
        with SAMPLE.open() as handle:
            original = next(csv.DictReader(handle))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inputs.csv"
            for mistake in ("partial_soil", "duplicate", "future_availability"):
                with self.subTest(mistake=mistake):
                    row = dict(original)
                    if mistake == "partial_soil":
                        del row["smap_mean_7d"]
                    if mistake == "future_availability":
                        row["features_available_on"] = "2026-11-16"
                    columns = list(row)
                    if mistake == "duplicate":
                        columns.append("t2m_last")
                    with path.open("w", newline="") as handle:
                        writer = csv.DictWriter(handle, fieldnames=columns)
                        writer.writeheader()
                        writer.writerow(row)
                    with self.assertRaises(ValueError):
                        snapshot_from_csv(
                            path,
                            region_id="test-only",
                            point_id="smap_0",
                            issue_date=date(2026, 11, 15),
                            climate_features=self.climate,
                            soil_features=self.soil,
                        )

    def test_unexpected_input_columns_are_rejected_before_any_inference(self):
        altered = self.snapshot.model_copy(deep=True)
        altered.climate["target"] = 100
        with patch("ml.inference.forecast.ForecastPredictor") as inference:
            with self.assertRaisesRegex(ValueError, "sobran.*target"):
                self.bundle.predict(altered)
            inference.assert_not_called()

    @unittest.skipUnless(importlib.util.find_spec("xgboost"), "Requiere el extra ml")
    def test_real_models_preserve_feature_order_and_add_moisture_baseline_once(self):
        import xgboost as xgb

        result = self.bundle.predict(self.snapshot)
        reversed_input = self.snapshot.model_copy(
            update={"climate": dict(reversed(list(self.snapshot.climate.items())))}
        )
        self.assertEqual(self.bundle.predict(reversed_input).climate.values, result.climate.values)
        self.assertEqual(result.status, "pending_recommendations")
        self.assertIsNone(result.recommendations)
        self.assertEqual(len(result.climate.values), 4)
        self.assertEqual(result.request.forecast_start_date, date(2026, 11, 16))
        self.assertEqual(result.request.reference_date, date(2026, 11, 13))
        self.assertEqual(result.climate.validation_status, "experimental")
        import pandas as pd

        from ml.datasets.calendar import target_calendar

        config = json.loads((self.bundle._directory("moisture") / "training.json").read_text())
        booster = xgb.Booster(params={"nthread": 1})
        booster.load_model(self.bundle._directory("moisture") / "model.json")
        frame = pd.DataFrame([{**self.snapshot.soil, "lead_days": lead} for lead in range(1, 8)])
        dates = pd.to_datetime(
            [self.snapshot.issue_date + timedelta(days=lead) for lead in range(1, 8)]
        )
        for name, values in target_calendar(dates).items():
            frame[name] = values
        delta = booster.predict(
            xgb.DMatrix(frame[config["features"]], feature_names=config["features"])
        )
        self.assertAlmostEqual(
            result.soil.values[0].value,
            float(delta.mean()) + self.snapshot.soil["smap_mean_7d"],
            places=6,
        )
        self.assertNotAlmostEqual(result.soil.values[0].value, float(delta.mean()))
        broken = self.snapshot.model_copy(deep=True)
        del broken.climate["t2m_last"]
        with self.assertRaisesRegex(ValueError, "t2m_last"):
            self.bundle.predict(broken)

    @unittest.skipUnless(importlib.util.find_spec("xgboost"), "Requiere el extra ml")
    def test_climate_can_be_available_without_inventing_soil_inputs(self):
        result = self.bundle.predict(self.snapshot.model_copy(update={"soil": None}))
        self.assertEqual(result.status, "insufficient_data")
        self.assertIsNotNone(result.climate)
        self.assertIsNone(result.soil)

    @unittest.skipUnless(importlib.util.find_spec("xgboost"), "Requiere el extra ml")
    def test_period_summaries_aggregate_the_same_real_daily_models(self):
        identities = set()
        versions = set()
        for horizon in HORIZONS:
            result = self.bundle.predict(self.snapshot, horizon_days=horizon)
            self.assertEqual(len(result.climate.daily), horizon)
            self.assertEqual(len(result.soil.daily), horizon)
            versions.add(result.climate.model_version)
            identities.add(result.analysis_id)
            for forecast in (result.climate, result.soil):
                for index, value in enumerate(forecast.values):
                    total = sum(day.values[index].value for day in forecast.daily)
                    self.assertAlmostEqual(
                        value.value, total / (1 if value.variable == "precipitation" else horizon)
                    )
        self.assertEqual(len(versions), 1)
        self.assertEqual(len(identities), 4)
        with self.assertRaisesRegex(ValueError, "Horizonte no soportado"):
            self.bundle.predict(self.snapshot, horizon_days=90)

    def test_http_reads_catalog_and_stored_exact_period_without_running_inference(self):
        repo = Mock()
        repo.region.return_value = self.region
        request = {
            "region_id": "test-only",
            "reference_date": "2022-01-06",
            "forecast_start_date": "2022-01-09",
            "horizon_days": 7,
        }
        stored = AnalysisResult(
            status="insufficient_data", request=request, analysis_id="historical-test"
        ).model_dump(mode="json")
        repo.analysis_for_period.side_effect = lambda _, h, day: (
            stored if h == 7 and day == date(2022, 1, 9) else None
        )
        repo.latest_observation_date.return_value = None
        with patch.object(
            self.bundle, "predict", side_effect=AssertionError("HTTP no debe inferir")
        ):
            client = TestClient(create_app(repo, pretrained_models=self.bundle))
            self.assertEqual(len(client.get("/api/v1/models").json()["models"]), 5)
            response = client.get("/api/v1/regions/test-only/latest-analysis?as_of=2022-01-09")
            self.assertEqual(response.json()["analysis_id"], "historical-test")
            self.assertIsNone(
                client.get("/api/v1/regions/test-only/latest-analysis?as_of=2026-11-14").json()
            )
            self.assertIsNone(
                client.get(
                    "/api/v1/regions/test-only/latest-analysis?as_of=2022-01-09&horizon_days=30"
                ).json()
            )

    def test_worker_records_missing_inputs_without_reusing_old_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ExpandedFeatureStore(folder)
            store.save(self.snapshot)
            observations, results, registry = Mock(), Mock(), Mock()
            observations.regions.return_value = [self.region]
            observations.latest_observation_date.return_value = None
            registry.current.return_value = None
            job = CropRecommendationJob(
                observations,
                results,
                registry,
                Mock(),
                bundled_models=self.bundle,
                feature_store=store,
            )
            outcome = job.run(as_of=date(2026, 11, 14))
            saved = results.save_analysis.call_args.args[0]
            self.assertEqual(saved.status, "insufficient_data")
            self.assertIsNone(saved.climate)
            self.assertEqual(saved.request.forecast_start_date, date(2026, 11, 14))
            self.assertEqual(results.save_analysis.call_count, 4)
            self.assertEqual([o["horizon_days"] for o in outcome["outcomes"]], [7, 15, 30, 60])

    @unittest.skipUnless(importlib.util.find_spec("xgboost"), "Requiere el extra ml")
    def test_worker_saves_real_historical_output_without_publishing_experimental_models(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ExpandedFeatureStore(folder)
            store.save(self.snapshot)
            observations, results, registry = Mock(), Mock(), Mock()
            observations.regions.return_value = [self.region]
            registry.current.return_value = None
            job = CropRecommendationJob(
                observations,
                results,
                registry,
                Mock(),
                bundled_models=self.bundle,
                feature_store=store,
                horizons=(7,),
            )
            with patch("pipelines.recommendations.job.datetime") as clock:
                clock.now.return_value.date.return_value = date(2026, 11, 16)
                job.run(as_of=date(2026, 11, 16))
            saved = results.save_analysis.call_args.args[0]
            self.assertIsNotNone(saved.climate)
            self.assertIsNotNone(saved.soil)
            registry.publish.assert_not_called()
