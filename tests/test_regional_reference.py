"""Referencia pública real con su fecha original, sin promoverla a datos operativos."""

import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from ml.features.expanded import ExpandedFeatureStore
from ml.features.prepared_daily import PreparedDailyInputs
from ml.features.regional_reference import RegionalReferenceInputs
from ml.inference.daily import DailyModelBundle
from packages.contracts.pretrained import DailyFeatures

ROOT = Path(__file__).resolve().parents[1]


class RegionalReferenceTests(unittest.TestCase):
    def test_latest_complete_same_point_precedes_newer_nearby_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = DailyModelBundle(ROOT / "ml/artifacts")
            store = ExpandedFeatureStore(root / "features")
            inputs = PreparedDailyInputs(root / "prepared", bundle, store)
            contract = bundle.input_contract()
            today = date(2026, 11, 15)
            region = {"region_id": "test-only", "longitude": -75.3, "latitude": 6.1}
            for name, age, lon in (
                ("near-new", 1, -75.31),
                ("same-old", 4, -75.3),
                ("same-new", 3, -75.3),
            ):
                issue = today - timedelta(days=age)
                store.save(
                    DailyFeatures(
                        region_id=name,
                        point_id=name,
                        longitude=lon,
                        latitude=6.1,
                        issue_date=issue,
                        observation_cutoff=issue - timedelta(days=2),
                        radiation_observation_cutoff=issue - timedelta(days=7),
                        source_sha256="a" * 64,
                        climate={key: 1 for key in contract.climate_features},
                        soil={key: 1 for key in contract.soil_features},
                    )
                )
            reference = RegionalReferenceInputs(inputs, root / "no-examples").resolve(region, today)
            self.assertEqual(reference.matched.spatial.method, "exact")
            self.assertEqual(reference.matched.snapshot.point_id, "same-new")
            self.assertEqual(reference.matched.snapshot.issue_date, today - timedelta(days=3))

    def test_climate_only_reference_is_available_when_soil_inputs_are_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "ml/examples", root / "examples")
            (root / "examples/inputs/moisture.csv").unlink()
            bundle = DailyModelBundle(ROOT / "ml/artifacts")
            inputs = PreparedDailyInputs(
                root / "prepared", bundle, ExpandedFeatureStore(root / "features")
            )
            reference = RegionalReferenceInputs(inputs, root / "examples").resolve(
                {"region_id": "test-only", "longitude": -74.80365, "latitude": 5.80966},
                date(2026, 11, 15),
            )
            self.assertIsNotNone(reference)
            self.assertIsNone(reference.matched.snapshot.soil)
            result = bundle.predict(reference.matched.snapshot, horizon_days=7)
            self.assertEqual(len(result.climate.values), 4)
            self.assertIsNone(result.soil)

    def test_public_snapshot_retains_date_coordinates_and_is_not_imported_as_live_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = PreparedDailyInputs(
                root / "prepared",
                DailyModelBundle(ROOT / "ml/artifacts"),
                ExpandedFeatureStore(root / "features"),
            )
            references = RegionalReferenceInputs(inputs, ROOT / "ml/examples")
            region = {"region_id": "test-only", "longitude": -74.80365, "latitude": 5.80966}
            selected = references.resolve(region, date(2026, 11, 15))
            self.assertEqual(selected.kind, "bundled_public_snapshot")
            self.assertEqual(selected.matched.snapshot.issue_date, date(2026, 11, 15))
            self.assertEqual(selected.matched.spatial.method, "nearest")
            self.assertGreater(selected.matched.spatial.distance_km, 100)
            self.assertEqual(
                selected.matched.spatial.used_latitude, selected.matched.snapshot.latitude
            )
            self.assertEqual(len(selected.matched.snapshot.climate), 49)
            self.assertEqual(len(selected.matched.snapshot.soil), 71)
            self.assertIsNone(inputs.resolve(region, date(2026, 11, 14)))
            self.assertFalse(list((root / "features").glob("**/*.json")))
            self.assertIsNone(references.resolve(region, date(2026, 11, 14)))
            self.assertIsNone(references.resolve(region, date(2026, 11, 23)))
            inputs.max_distance_km = 1
            self.assertIsNone(references.resolve(region, date(2026, 11, 15)))
