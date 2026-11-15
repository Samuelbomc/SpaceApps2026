"""Datos sintéticos identificados: contratos del reentrenamiento, nunca datos de finca."""

import csv
import json
import shutil
import tempfile
import unittest
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

from ml.evaluation.promotion import chronological_partitions
from ml.evaluation.rolling_origin import rolling_origin_plan
from ml.features.expanded import ExpandedFeatureStore
from ml.inference.registered import RegisteredPredictorFactory
from ml.training.artifacts import ModelArtifactStore
from ml.training.expanded_config import HORIZONS, TARGETS, load_training_config, training_policies
from ml.training.expanded_dataset import (
    ExpandedTrainingDatasetBuilder,
    ExpandedTrainingSnapshots,
    digest,
    original_csv_identity,
)
from ml.training.xgboost import ExpandedXGBoostTrainer
from packages.contracts.api import AnalysisRequest
from packages.contracts.pretrained import ExpandedFeatures
from packages.contracts.training import ModelRelease
from pipelines.training.pipeline import ModelTrainingPipeline
from tests.test_model_lifecycle import MemoryRegistry


def write_fixture(root, config, *, days=350, audited=False):
    """No son umbrales o etiquetas reales: solo fixtures de software."""
    for horizon in HORIZONS:
        manifest, validation = {}, {}
        for target in TARGETS:
            spec = config["sources"][str(horizon)][target]
            path = root / spec["relative_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            header = spec["features"] + [
                "target",
                "point_id",
                "longitude",
                "latitude",
                "issue_date",
                "observation_cutoff",
                "target_start",
                "target_end",
                "target_observed_days",
                "features_available_on",
                "label_available_on",
            ]
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
                writer.writeheader()
                for i in range(days):
                    issue = date(2020, 1, 1) + timedelta(days=i)
                    for point in range(3):
                        features = {name: 1.0 for name in spec["features"]}
                        features.update(
                            t2m_mean_7d=10.0 + point,
                            t2m_min_mean_7d=7.0 + point,
                            t2m_max_mean_7d=13.0 + point,
                            gpm_late_sum_7d_mm=10.0 + point,
                        )
                        if target == "moisture":
                            features.update(smap_mean_7d=0.2 + point * 0.01)
                        value = {
                            "temperature_mean": 20.0 + point,
                            "temperature_min": 17.0 + point,
                            "temperature_max": 23.0 + point,
                            "precipitation": 50.0 + point,
                            "moisture": 0.25 + point * 0.01,
                        }[target]
                        writer.writerow(
                            {
                                **features,
                                "target": value,
                                "point_id": f"{target}_{point}",
                                "longitude": -75.5 + point * 0.2,
                                "latitude": 6.0,
                                "issue_date": issue,
                                "observation_cutoff": issue - timedelta(days=2),
                                "target_start": issue + timedelta(days=1),
                                "target_end": issue + timedelta(days=horizon),
                                "target_observed_days": horizon,
                                "features_available_on": issue,
                                "label_available_on": issue + timedelta(days=horizon + 2),
                            }
                        )
            checksum = digest(path)
            spec["original_source_sha256"] = checksum
            manifest[target] = {
                "features": spec["features"],
                "target": "target",
                "rows": days * 3,
                "horizon_days": horizon,
                "first_issue": "2020-01-01",
                "last_issue": str(date(2020, 1, 1) + timedelta(days=days - 1)),
            }
            validation[target] = {
                "status": "PASS",
                "rows": days * 3,
                "source_sha256": checksum,
                "synthetic_test": True,
            }
        folder = root / config["sources"][str(horizon)]["moisture"]["relative_path"]
        folder = folder.parent
        (folder / "manifest.json").write_text(json.dumps(manifest))
        (folder / "validation.json").write_text(json.dumps(validation))
        if audited:
            (folder / "publication-evidence.json").write_text(
                json.dumps(
                    {
                        "reviewed_by": "SYNTHETIC TEST ONLY",
                        "reviewed_on": "2024-01-01",
                        "feature_availability_verified": True,
                        "spatial_scope_verified": True,
                        "recipe_version": "expanded-v1",
                        "sources": {
                            target: digest(
                                root / config["sources"][str(horizon)][target]["relative_path"]
                            )
                            for target in TARGETS
                        },
                    }
                )
            )


class ExpandedTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.sources = Path(cls.shared.name) / "sources"
        cls.config = load_training_config()
        cls.config.update(
            max_rounds=8,
            early_stopping_rounds=3,
            min_train_samples=20,
            min_validation_samples=9,
            min_test_samples=9,
        )
        write_fixture(cls.sources, cls.config)

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = deepcopy(self.config)
        self.region = {"region_id": "synthetic-test-only", "latitude": 6.0, "longitude": -75.5}
        self.snapshots = ExpandedTrainingSnapshots(
            self.config, self.sources, self.root / "datasets"
        )
        self.builder = ExpandedTrainingDatasetBuilder(self.config)
        self.snapshot = self.snapshots.capture(self.region, date(2024, 1, 1))

    def build(self, kind="climate", horizon=7, snapshot=None):
        snapshot = snapshot or self.snapshot
        return self.builder.build(snapshot, self.snapshots.path(snapshot), kind, horizon)

    def test_config_matches_original_recipes_and_prevents_feature_leakage(self):
        canonical = load_training_config()
        self.assertEqual(canonical["split_strategy"], "rolling_origin")
        self.assertEqual(canonical["candidates"][1]["max_depth"], 3)
        self.assertEqual(canonical["max_rounds"], 800)
        self.assertEqual(canonical["early_stopping_rounds"], 30)
        self.assertFalse(canonical["publication_allowed"])
        policies = training_policies(canonical)
        self.assertEqual(len(policies), 8)
        self.assertEqual(len(canonical["sources"]["7"]["moisture"]["features"]), 52)
        altered = deepcopy(canonical)
        altered["sources"]["7"]["temperature_mean"]["features"].append("target")
        path = self.root / "bad.json"
        path.write_text(json.dumps(altered))
        with self.assertRaises(ValueError):
            load_training_config(path)

    def test_pooled_cells_are_preserved_and_targets_and_baselines_keep_units(self):
        for horizon in HORIZONS:
            climate = self.build(horizon=horizon)
            soil = self.build("soil", horizon)
            self.assertEqual(len(climate.samples), 1050)
            self.assertEqual(len({s.spatial_id for s in climate.samples}), 3)
            self.assertEqual(len({s.feature_date for s in climate.samples}), 350)
            row = climate.samples[0]
            self.assertAlmostEqual(
                row.baseline["precipitation"], row.features["gpm_late_sum_7d_mm"] * horizon / 7
            )
            self.assertEqual(row.label_start, row.feature_date + timedelta(days=1))
            self.assertEqual(row.label_end, row.feature_date + timedelta(days=horizon))
            self.assertAlmostEqual(
                soil.samples[0].targets["moisture"], soil.samples[0].features["smap_mean_7d"] + 0.05
            )
            self.assertFalse(soil.publication_ready)

    def test_cutoff_removes_unavailable_labels_and_split_groups_dates_with_purge(self):
        partial = self.snapshot.model_copy(update={"cutoff": date(2020, 10, 1)})
        data = self.build(horizon=60, snapshot=partial)
        self.assertTrue(all(s.label_available_on <= partial.cutoff for s in data.samples))
        self.assertGreater(data.provenance["excluded_unavailable_labels"], 0)
        dataset = self.build(horizon=60)
        train, validation, test = chronological_partitions(dataset, self.snapshot.cutoff)
        self.assertLess(
            max(s.label_end for s in train), min(s.observation_cutoff for s in validation)
        )
        self.assertLess(
            max(s.label_end for s in validation), min(s.observation_cutoff for s in test)
        )
        self.assertFalse({s.feature_date for s in train} & {s.feature_date for s in validation})
        self.assertFalse({s.feature_date for s in validation} & {s.feature_date for s in test})
        self.assertTrue(
            all(
                len({s.spatial_id for s in partition}) == 3
                for partition in [train, validation, test]
            )
        )

    def test_snapshot_is_immutable_and_detects_tampering(self):
        again = self.snapshots.capture(self.region, date(2024, 1, 2))
        self.assertEqual(again.dataset_id, self.snapshot.dataset_id)
        path = self.snapshots.path(self.snapshot).parent / "7/temperature_mean.parquet"
        path.write_bytes(path.read_bytes() + b"tampered")
        with self.assertRaisesRegex(ValueError, "alterado"):
            self.build()
        with self.assertRaisesRegex(ValueError, "alterado"):
            self.snapshots.capture(self.region, date(2024, 1, 2))
        self.assertIsNone(
            self.snapshots.capture({**self.region, "longitude": -70}, date(2024, 1, 1))
        )

    def test_legacy_windows_newlines_are_not_mistaken_for_modified_labels(self):
        path = self.root / "line.csv"
        path.write_bytes(b"x,target\n1,2\n")
        import hashlib

        expected = hashlib.sha256(b"x,target\r\n1,2\r\n").hexdigest()
        self.assertTrue(original_csv_identity(path, expected))
        path.write_bytes(b"x,target\n1,3\n")
        self.assertFalse(original_csv_identity(path, expected))

    def test_missing_rainfall_target_does_not_drop_valid_temperature_labels(self):
        source = self.root / "changed"
        shutil.copytree(self.sources, source)
        path = source / "expanded/precipitation.csv"
        with path.open() as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames
            rows = list(reader)
        rows.pop(0)
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        manifest = json.loads((path.parent / "manifest.json").read_text())
        validation = json.loads((path.parent / "validation.json").read_text())
        manifest["precipitation"]["rows"] -= 1
        validation["precipitation"].update(rows=len(rows), source_sha256=digest(path))
        (path.parent / "manifest.json").write_text(json.dumps(manifest))
        (path.parent / "validation.json").write_text(json.dumps(validation))
        store = ExpandedTrainingSnapshots(self.config, source, self.root / "other-snapshots")
        snapshot = store.capture(self.region, date(2024, 1, 1))
        data = self.builder.build(snapshot, store.path(snapshot), "climate", 7)
        self.assertEqual(len(data.samples), 1050)
        self.assertEqual(sum("temperature_mean" in row.targets for row in data.samples), 1050)
        self.assertEqual(sum("precipitation" in row.targets for row in data.samples), 1049)

    def test_constructor_and_trainer_are_connected_by_default(self):
        from apps.api.app.config import Settings
        from scripts.runtime import build_jobs

        jobs = build_jobs(Mock(), Settings())
        from pipelines.training.daily import DailyModelTrainingPipeline

        self.assertIsInstance(jobs["training"].pipeline, DailyModelTrainingPipeline)
        self.assertEqual(len(jobs["training"].pipeline.config["models"]), 5)
        self.assertTrue(jobs["recommendations"].predictor_factory.uses_feature_snapshots)

    def test_rolling_origin_folds_keep_cells_grouped_and_purge_each_target_before_test(self):
        dataset = self.build("climate", 15)
        plan = rolling_origin_plan(dataset, self.snapshot.cutoff)
        for target, folds in plan.folds.items():
            self.assertEqual(len(folds), 4)
            test = [row for row in plan.test if target in row.targets]
            test_dates = {row.feature_date for row in test}
            for train, validation in folds:
                self.assertTrue(train and validation)
                self.assertLess(
                    max(row.label_end for row in train),
                    min(row.observation_cutoff for row in validation),
                )
                self.assertLess(
                    max(row.label_end for row in validation),
                    min(row.observation_cutoff for row in test),
                )
                self.assertFalse(test_dates & {row.feature_date for row in train + validation})
                self.assertTrue(
                    all(
                        len({row.spatial_id for row in validation if row.feature_date == day}) == 3
                        for day in {row.feature_date for row in validation}
                    )
                )

    def test_holdout_labels_do_not_select_candidates_or_trees_and_oof_metrics_are_recoverable(self):
        from ml.evaluation.promotion import mae

        dataset = self.build("soil", 7)
        plan = rolling_origin_plan(dataset, self.snapshot.cutoff)
        trainer = ExpandedXGBoostTrainer(self.config)
        model = trainer.fit_rolling_origin(dataset, plan)
        measured = mae(
            plan.validation, model.validation_predictions(plan.validation), dataset.target_units
        )
        report = model.config["cross_validation"]["moisture"]
        best = min(report["candidates"], key=lambda candidate: candidate["cv_mae"])
        self.assertAlmostEqual(measured["moisture"], best["cv_mae"])
        altered = dataset.model_copy(deep=True)
        first_test = min(row.feature_date for row in plan.test)
        for row in altered.samples:
            if row.feature_date >= first_test:
                row.targets["moisture"] += 1000
        repeated = trainer.fit_rolling_origin(
            altered, rolling_origin_plan(altered, self.snapshot.cutoff)
        )
        self.assertEqual(
            model.config["selected_parameters"], repeated.config["selected_parameters"]
        )
        self.assertEqual(model.config["selected_rounds"], repeated.config["selected_rounds"])
        self.assertEqual(model.predict(plan.test[:3]), repeated.predict(plan.test[:3]))
        folder = self.root / "cv-artifacts"
        folder.mkdir()
        model.save(folder)
        stored = json.loads((folder / "cv_predictions.json").read_text())
        self.assertEqual(len(stored), len(plan.validation))
        self.assertTrue(all(row["predictions"].keys() == {"moisture"} for row in stored))

    def test_real_training_residual_roundtrip_and_registered_inference_use_same_recipe(self):
        trainer = ExpandedXGBoostTrainer(self.config)
        dataset = self.build("soil", 7)
        train, validation, test = chronological_partitions(dataset, self.snapshot.cutoff)
        model = trainer.fit_with_validation(dataset, train, validation)
        artifacts = ModelArtifactStore(self.root / "models")
        version = "f" * 32
        hashes = artifacts.save(version, model, {"synthetic_test": True})
        release = ModelRelease(
            slot="synthetic-test-only:soil:7",
            version=version,
            model_kind="soil",
            region_id=self.region["region_id"],
            horizon_days=7,
            dataset_id=self.snapshot.dataset_id,
            training_fingerprint="test-only",
            recipe_version="expanded-v1",
            policy_version="test-only",
            trained_through=max(s.label_end for s in train),
            feature_names=dataset.feature_names,
            target_units=dataset.target_units,
            artifact_sha256=hashes,
            metrics={},
            created_at=datetime.now(UTC),
            spatial_scope=self.config["spatial_scope"],
        )
        loaded = trainer.load(release, artifacts.verify(release))
        self.assertEqual(model.predict(test[:4]), loaded.predict(test[:4]))
        sample = test[0]
        climate_names = self.config["sources"]["7"]["temperature_mean"]["features"]
        inputs = ExpandedFeatures(
            region_id=self.region["region_id"],
            longitude=sample.longitude,
            latitude=sample.latitude,
            issue_date=sample.feature_date,
            observation_cutoff=sample.observation_cutoff,
            source_sha256="a" * 64,
            climate={k: sample.features[k] for k in climate_names},
            soil=sample.features,
        )
        store = ExpandedFeatureStore(self.root / "features")
        store.save(inputs)
        factory = RegisteredPredictorFactory(trainer, store)
        bound = factory.bind(inputs)
        adapter = bound.create(release, artifacts.verify(release))
        request = AnalysisRequest(
            region_id=inputs.region_id,
            reference_date=inputs.observation_cutoff,
            forecast_start_date=inputs.issue_date + timedelta(days=1),
            horizon_days=7,
        )
        forecast = adapter.predict(request, [])
        self.assertEqual(forecast.values[0].value, model.predict([sample])[0]["moisture"])
        self.assertEqual(forecast.values[0].statistic, "mean")
        with self.assertRaisesRegex(ValueError, "publicada"):
            bound.create(
                release.model_copy(update={"validation_status": "experimental"}),
                artifacts.verify(release),
            )

    def test_pipeline_evaluates_but_does_not_publish_unreviewed_data(self):
        trainer = ExpandedXGBoostTrainer(self.config)
        registry = MemoryRegistry()
        policies = training_policies(self.config)
        for policy in policies.values():
            policy.max_mae = {key: 100.0 for key in policy.max_mae}
        pipeline = ModelTrainingPipeline(
            self.snapshots,
            ModelArtifactStore(self.root / "models"),
            registry,
            builder=self.builder,
            trainer=trainer,
            policies=policies,
            horizons=(7,),
        )
        results = pipeline.run(self.region, date(2024, 1, 1))
        self.assertEqual([r.status for r in results], ["pending_review", "pending_review"])
        self.assertFalse(registry.published_models())
        for attempt in registry.attempts.values():
            release = attempt["release"]
            self.assertEqual(release["validation_status"], "experimental")
            self.assertIsNotNone(release["metrics"]["test"])
            self.assertEqual(release["metrics"]["validation_method"], "rolling_origin")
            self.assertTrue(release["metrics"]["cross_validation"])
        self.assertEqual(
            [r.status for r in pipeline.run(self.region, date(2024, 1, 1))],
            ["unchanged", "unchanged"],
        )

    def test_audited_availability_and_explicit_policy_allow_publication(self):
        source = self.root / "audited"
        config = deepcopy(self.config)
        config["publication_allowed"] = True
        write_fixture(source, config, audited=True)
        store = ExpandedTrainingSnapshots(config, source, self.root / "audited-snapshots")
        builder = ExpandedTrainingDatasetBuilder(config)
        registry = MemoryRegistry()
        policies = training_policies(config)
        for policy in policies.values():
            policy.max_mae = {key: 100.0 for key in policy.max_mae}
        pipeline = ModelTrainingPipeline(
            store,
            ModelArtifactStore(self.root / "audited-models"),
            registry,
            builder=builder,
            trainer=ExpandedXGBoostTrainer(config),
            policies=policies,
            horizons=(7,),
        )
        self.assertEqual(
            [r.status for r in pipeline.run(self.region, date(2024, 1, 1))],
            ["published", "published"],
        )
        self.assertEqual(len(registry.published_models()), 2)
        self.assertTrue(
            all(r.validation_status == "validated" for r in registry.published_models())
        )
