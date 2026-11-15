"""Selección espacial con entradas sintéticas aisladas; nunca datos operativos."""

import csv
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from ml.features.expanded import ExpandedFeatureStore
from ml.features.prepared_daily import PreparedDailyInputs
from ml.features.spatial import distance_km
from ml.inference.daily import DailyModelBundle
from packages.contracts.pretrained import DailyFeatures

ISSUE = date(2026, 11, 14)


class NearestInputsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.bundle = DailyModelBundle()
        self.contract = self.bundle.input_contract()
        self.store = ExpandedFeatureStore(self.root / "features")
        self.inputs = PreparedDailyInputs(
            self.root / "prepared", self.bundle, self.store, max_distance_km=200
        )
        self.region = {"region_id": "synthetic-selected", "latitude": 6.0, "longitude": -75.2}

    def snapshot(self, name, longitude=-75.19, latitude=6.0, issue=ISSUE, soil=True):
        return DailyFeatures(
            region_id="synthetic-" + name,
            point_id=name,
            longitude=longitude,
            latitude=latitude,
            issue_date=issue,
            observation_cutoff=issue - timedelta(days=2),
            radiation_observation_cutoff=issue - timedelta(days=7),
            source_sha256="a" * 64,
            climate={name: 1 for name in self.contract.climate_features},
            soil={name: 1 for name in self.contract.soil_features} if soil else None,
        )

    def test_exact_snapshot_precedes_nearest_without_changing_coordinates(self):
        exact = self.snapshot("exact", longitude=self.region["longitude"]).model_copy(
            update={"region_id": self.region["region_id"]}
        )
        self.store.save(exact)
        self.store.save(self.snapshot("near"))
        match = self.inputs.resolve(self.region, ISSUE)
        self.assertEqual(match.spatial.method, "exact")
        self.assertEqual(match.spatial.distance_km, 0)
        self.assertEqual(match.snapshot, exact)

    def test_closest_complete_reference_keeps_requested_and_used_points_separate(self):
        near = self.snapshot("near")
        self.store.save(near)
        self.store.save(self.snapshot("far", longitude=-75.1))
        match = self.inputs.resolve(self.region, ISSUE)
        self.assertEqual(match.snapshot, near)
        self.assertEqual(match.spatial.method, "nearest")
        self.assertEqual(match.spatial.requested_longitude, -75.2)
        self.assertEqual(match.spatial.used_longitude, -75.19)
        self.assertAlmostEqual(match.spatial.distance_km, 1.106, places=2)
        self.assertIsNone(self.store.load(self.region, ISSUE))
        self.assertEqual(match.snapshot.region_id, "synthetic-near")

    def test_exact_climate_is_not_displaced_by_complete_nearby_inputs(self):
        exact = self.snapshot("exact-climate", longitude=self.region["longitude"], soil=False)
        exact = exact.model_copy(update={"region_id": self.region["region_id"]})
        self.store.save(exact)
        self.store.save(self.snapshot("complete-nearby"))

        match = self.inputs.resolve(self.region, ISSUE)

        self.assertEqual(match.snapshot, exact)
        self.assertEqual(match.spatial.method, "exact")
        self.assertEqual(match.spatial.distance_km, 0)
        self.assertIsNone(match.snapshot.soil)
        reference = self.inputs.resolve(self.region, ISSUE, prefer_exact=False)
        self.assertEqual(reference.spatial.method, "nearest")
        self.assertIsNotNone(reference.snapshot.soil)

    def test_old_future_outside_and_distant_snapshots_are_not_used(self):
        for snapshot in (
            self.snapshot("old", issue=ISSUE - timedelta(days=1)),
            self.snapshot("future", issue=ISSUE + timedelta(days=1)),
            self.snapshot("outside", longitude=-76),
        ):
            self.store.save(snapshot)
        self.assertIsNone(self.inputs.resolve(self.region, ISSUE))
        self.store.save(self.snapshot("distant", longitude=-74.7))
        bounded = PreparedDailyInputs(
            self.root / "prepared", self.bundle, self.store, max_distance_km=1
        )
        self.assertIsNone(bounded.resolve(self.region, ISSUE))

    def test_partial_nearby_data_do_not_replace_complete_available_inputs(self):
        self.store.save(self.snapshot("partial", longitude=-75.199, soil=False))
        self.store.save(self.snapshot("complete", longitude=-75.19))
        self.assertEqual(self.inputs.resolve(self.region, ISSUE).snapshot.point_id, "complete")

    def test_nearest_rows_are_found_in_prepared_csv_and_invalid_rows_are_skipped(self):
        target = self.root / "prepared/moisture/features.csv"
        target.parent.mkdir(parents=True)
        first = self.snapshot("invalid", longitude=-75.2)
        second = self.snapshot("valid", longitude=-75.18)
        rows = []
        for snapshot in (first, second):
            body = snapshot.model_dump(mode="json")
            rows.append(
                {
                    key: body[key]
                    for key in (
                        "point_id",
                        "issue_date",
                        "observation_cutoff",
                        "radiation_observation_cutoff",
                        "latitude",
                        "longitude",
                    )
                }
                | snapshot.soil
            )
        rows[0]["smap_mean_7d"] = "nan"
        with target.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        match = self.inputs.resolve(self.region, ISSUE)
        self.assertEqual(match.snapshot.point_id, "valid")
        self.assertEqual(match.spatial.used_longitude, -75.18)
        self.assertNotEqual(match.spatial.source_sha256, "a" * 64)

    def test_no_candidates_and_invalid_distance_configuration_are_explicit(self):
        self.assertIsNone(self.inputs.resolve(self.region, ISSUE))
        for value in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                PreparedDailyInputs(self.root, self.bundle, self.store, max_distance_km=value)
        self.assertAlmostEqual(distance_km(-75, 6, -75, 6), 0)
