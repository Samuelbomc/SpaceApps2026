"""Integración real de los artefactos del equipo; no publica modelos en producción."""

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
from ml.features.expanded import ExpandedFeatureStore, snapshot_from_csv
from ml.inference.expanded import CLIMATE, HORIZONS, ExpandedModelBundle
from packages.contracts.api import AnalysisResult
from packages.contracts.pretrained import ExpandedFeatures
from pipelines.recommendations.job import CropRecommendationJob

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples/xgboost/moisture_99_20220108.csv"


class PretrainedModelTests(unittest.TestCase):
    def setUp(self):
        self.bundle = ExpandedModelBundle(ROOT / "ml/artifacts")
        catalog = self.bundle.catalog()
        self.climate = next(m.features for m in catalog.models if m.model_kind == "climate")
        self.soil = next(m.features for m in catalog.models if m.model_kind == "soil")
        self.snapshot = snapshot_from_csv(
            SAMPLE,
            region_id="test-only",
            point_id="moisture_99",
            issue_date=date(2022, 1, 8),
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
        self.assertEqual(len(catalog.models), 20)
        soil = next(m for m in catalog.models if m.model_kind == "soil" and m.horizon_days == 7)
        self.assertIn("smap_mean_7d", soil.formula)
        self.assertEqual(len(soil.features), 52)
        self.assertAlmostEqual(soil.evaluation_mae, 0.03593788088985969)
        self.assertTrue(all(m.validation_status == "experimental" for m in catalog.models))

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
                    {**self.snapshot.model_dump(), "observation_cutoff": date(2022, 1, 7)}
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
        for point, day in [("wrong-point", date(2022, 1, 8)), ("moisture_99", date(2026, 11, 14))]:
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
            for horizon in HORIZONS:
                for name in (*CLIMATE, "moisture"):
                    source = self.bundle._directory(name, horizon)
                    destination = Path(folder) / source.relative_to(self.bundle.root)
                    destination.mkdir(parents=True)
                    for filename in ("model.json", "training.json"):
                        shutil.copyfile(source / filename, destination / filename)
            path = Path(folder) / "soil_moisture/model.json"
            path.write_text(path.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "no coincide"):
                ExpandedModelBundle(folder).catalog()

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
        self.assertEqual(result.request.forecast_start_date, date(2022, 1, 9))
        self.assertEqual(result.request.reference_date, date(2022, 1, 6))
        self.assertEqual(result.climate.validation_status, "experimental")
        booster = xgb.Booster(params={"nthread": 1})
        booster.load_model(ROOT / "ml/artifacts/soil_moisture/model.json")
        delta = float(
            booster.predict(
                xgb.DMatrix([[self.snapshot.soil[k] for k in self.soil]], feature_names=self.soil)
            )[0]
        )
        self.assertAlmostEqual(
            result.soil.values[0].value, self.snapshot.soil["smap_mean_7d"] + delta
        )
        self.assertNotAlmostEqual(result.soil.values[0].value, delta)
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
    def test_every_horizon_uses_its_own_real_boosters_and_residual_baseline(self):
        import xgboost as xgb

        versions, identities = set(), set()
        for horizon in HORIZONS:
            with self.subTest(horizon=horizon):
                result = self.bundle.predict(self.snapshot, horizon_days=horizon)
                self.assertEqual(result.request.horizon_days, horizon)
                self.assertEqual(result.climate.horizon_days, horizon)
                self.assertIn(str(horizon), result.climate.values[3].aggregation)
                versions.add(result.climate.model_version)
                identities.add(result.analysis_id)
                for name, expected in [
                    ("precipitation", result.climate.values[3].value),
                    ("moisture", result.soil.values[0].value),
                ]:
                    config = json.loads(
                        (self.bundle._directory(name, horizon) / "training.json").read_text()
                    )
                    features = self.snapshot.soil if name == "moisture" else self.snapshot.climate
                    booster = xgb.Booster(params={"nthread": 1})
                    booster.load_model(self.bundle._directory(name, horizon) / "model.json")
                    raw = float(
                        booster.predict(
                            xgb.DMatrix(
                                [[features[key] for key in config["features"]]],
                                feature_names=config["features"],
                            )
                        )[0]
                    )
                    if name == "moisture":
                        raw += features["smap_mean_7d"]
                    self.assertAlmostEqual(expected, raw)
        self.assertEqual(len(versions), 4)
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
            self.assertEqual(len(client.get("/api/v1/models").json()["models"]), 20)
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
            job.run(as_of=date(2022, 1, 9))
            saved = results.save_analysis.call_args.args[0]
            self.assertIsNotNone(saved.climate)
            self.assertIsNotNone(saved.soil)
            registry.publish.assert_not_called()
