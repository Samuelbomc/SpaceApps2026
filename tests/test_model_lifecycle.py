"""Datos y modelos sintéticos únicamente para probar orquestación y barreras ML."""

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock

from ml.evaluation.promotion import temporal_split
from ml.training.artifacts import ModelArtifactStore
from packages.contracts.training import DatasetSnapshot, LabeledSample, PreparedDataset, TrainingPolicy
from pipelines.training.pipeline import ModelTrainingPipeline


class MemoryRegistry:
    def __init__(self):
        self.models, self.attempts, self.outcomes = {}, {}, []

    def current(self, slot):
        return self.models.get(slot)

    def published_models(self):
        return list(self.models.values())

    def attempt(self, key):
        return self.attempts.get(key)

    def record_attempt(self, key, body):
        self.attempts.setdefault(key, body)

    def publish(self, release, expected_version):
        current = self.current(release.slot)
        if (current.version if current else None) != expected_version:
            return False
        self.models[release.slot] = release
        return True

    def record_outcomes(self, outcomes):
        self.outcomes = outcomes

    def recent_training(self):
        return self.outcomes


class FixtureBuilder:
    version = "test-only-builder-v1"

    def __init__(self):
        self.count, self.verified = 240, True

    def build(self, snapshot, path, kind, horizon):
        samples = []
        for index in range(self.count):
            day = date(2020, 1, 1) + timedelta(days=index)
            end = day + timedelta(days=horizon)
            samples.append(LabeledSample(feature_date=day, label_start=day + timedelta(days=1), label_end=end,
                                         label_available_on=end, features={"x": float(index)}, targets={"target": index+1.},
                                         baseline={"target": index+6.}, label_sources=["synthetic-test-fixture"],
                                         labels_verified=self.verified))
        return PreparedDataset(dataset_id=snapshot.dataset_id, recipe_version=self.version, model_kind=kind,
                               horizon_days=horizon, feature_names=["x"], target_units={"target": "test-only-unit"}, samples=samples)


class FixtureModel:
    def __init__(self, offset):
        self.offset = offset

    def predict(self, samples):
        return [{"target": sample.features["x"] + self.offset} for sample in samples]

    def save(self, directory):
        (directory/"model.json").write_text(json.dumps({"synthetic_test_offset": self.offset}))


class FixtureTrainer:
    version = "test-only-trainer-v1"

    def __init__(self):
        self.calls, self.offset, self.training = 0, 3., []

    def fit(self, dataset, samples):
        self.calls += 1
        self.training = samples
        return FixtureModel(self.offset)

    def load(self, release, directory):
        return FixtureModel(json.loads((directory/"model.json").read_text())["synthetic_test_offset"])


class ModelLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.region = {"region_id": "test-only", "latitude": 6., "longitude": -75.}
        self.snapshot = DatasetSnapshot(dataset_id="a"*64, region_id="test-only", cutoff=date(2024,1,1),
                                        first_date=date(2020,1,1), last_date=date(2020,12,31), row_count=366, sha256="test-only")
        self.snapshots = Mock()
        self.snapshots.root = self.root/"datasets"
        self.snapshots.capture.side_effect = lambda *_: self.snapshot
        self.snapshots.path.return_value = self.root/"fixture-only.parquet"
        self.builder, self.trainer, self.registry = FixtureBuilder(), FixtureTrainer(), MemoryRegistry()
        self.artifacts = ModelArtifactStore(self.root/"models")
        self.policy = TrainingPolicy(version="test-only-policy", min_train_samples=100, min_validation_samples=20,
                                     validation_days=30, min_new_labels=7, max_mae={"target": 3.})
        self.pipeline = ModelTrainingPipeline(self.snapshots, self.artifacts, self.registry, builder=self.builder,
                                              trainer=self.trainer, policies={(kind,7):self.policy for kind in ("climate","soil")},
                                              horizons=(7,))

    def run_pipeline(self):
        return self.pipeline.run(self.region, date(2024,1,1))

    def add_labels(self):
        self.builder.count += 10
        self.snapshot = self.snapshot.model_copy(update={"dataset_id":"b"*64})

    def test_no_configuration_never_fits_or_publishes(self):
        self.pipeline.builder = None
        result = self.run_pipeline()
        self.assertTrue(all(item.status=="pending_configuration" for item in result))
        self.assertEqual(self.trainer.calls, 0)
        self.assertEqual(self.registry.published_models(), [])

    def test_promotion_purges_overlap_preserves_inputs_and_is_idempotent(self):
        result = self.run_pipeline()
        self.assertEqual([item.status for item in result], ["published","published"])
        release = self.registry.current("test-only:climate:7")
        self.assertLess(release.metrics["train_label_end"], release.metrics["validation_feature_start"])
        self.assertEqual(release.metrics["candidate_mae"], {"target":2.})
        self.assertTrue(self.artifacts.verify(release).is_dir())
        self.assertEqual(len(list((self.snapshots.root/self.snapshot.dataset_id/"prepared").glob("*.parquet"))),2)
        self.assertEqual([item.status for item in self.run_pipeline()], ["unchanged","unchanged"])
        self.assertEqual(self.trainer.calls,2)

    def test_better_candidate_replaces_champion_on_identical_new_validation(self):
        self.run_pipeline()
        previous = self.registry.current("test-only:climate:7")
        self.add_labels()
        self.trainer.offset = 2.
        self.assertEqual(self.run_pipeline()[0].status,"published")
        release = self.registry.current(previous.slot)
        self.assertNotEqual(release.version,previous.version)
        self.assertEqual(release.metrics["incumbent_mae"], {"target":2.})
        self.assertEqual(release.metrics["candidate_mae"], {"target":1.})
        self.assertTrue(self.artifacts.verify(previous).exists())

    def test_rejected_candidate_keeps_champion_and_is_not_refit_next_poll(self):
        self.run_pipeline()
        previous = self.registry.current("test-only:climate:7")
        self.add_labels()
        self.trainer.offset = 4.
        self.assertEqual(self.run_pipeline()[0].status,"rejected")
        self.assertEqual(self.registry.current(previous.slot).version,previous.version)
        count = self.trainer.calls
        self.assertEqual(self.run_pipeline()[0].status,"unchanged")
        self.assertEqual(self.trainer.calls,count)

    def test_unverified_or_unavailable_labels_block_training(self):
        self.builder.verified=False
        with self.assertRaisesRegex(ValueError,"etiquetas"):
            self.run_pipeline()
        self.builder.verified=True
        self.snapshot=self.snapshot.model_copy(update={"cutoff":date(2020,4,1)})
        with self.assertRaisesRegex(ValueError,"etiquetas"):
            self.run_pipeline()
        self.assertEqual(self.trainer.calls,0)

    def test_short_history_and_new_observations_without_new_labels_do_not_train(self):
        self.builder.count=20
        self.assertEqual(self.run_pipeline()[0].status,"insufficient_labels")
        self.assertEqual(self.trainer.calls,0)
        self.builder.count=240
        self.run_pipeline()
        self.snapshot=self.snapshot.model_copy(update={"dataset_id":"c"*64})
        self.assertEqual(self.run_pipeline()[0].status,"insufficient_labels")
        self.assertEqual(self.trainer.calls,2)

    def test_corrupt_artifact_and_training_failure_keep_published_version(self):
        self.run_pipeline()
        previous=self.registry.current("test-only:climate:7")
        path=self.artifacts.directory(previous.version)/"model.json"
        original=path.read_bytes()
        path.write_text('{}')
        with self.assertRaisesRegex(ValueError,"alterado"):
            self.run_pipeline()
        path.write_bytes(original)
        self.add_labels()
        self.trainer.fit=Mock(side_effect=RuntimeError("test-only training interruption"))
        with self.assertRaises(RuntimeError):
            self.run_pipeline()
        self.assertEqual(self.registry.current(previous.slot).version,previous.version)

    def test_nan_predictions_never_publish(self):
        self.trainer.offset=float("nan")
        with self.assertRaisesRegex(ValueError,"finita"):
            self.run_pipeline()
        self.assertEqual(self.registry.published_models(),[])

    def test_compare_and_swap_failure_does_not_record_a_false_publication(self):
        self.registry.publish=Mock(return_value=False)
        with self.assertRaisesRegex(RuntimeError,"campeón cambió"):
            self.run_pipeline()
        self.assertEqual(self.registry.attempts,{})

    def test_baseline_must_be_beaten_even_on_first_release(self):
        self.trainer.offset=6.
        self.policy.max_mae={"target":10.}
        self.assertEqual(self.run_pipeline()[0].status,"rejected")
        self.assertEqual(self.registry.published_models(),[])


class SnapshotTests(unittest.TestCase):
    def test_complete_history_and_revisions_produce_recoverable_copies(self):
        from pipelines.training.snapshots import HistoricalSnapshotStore
        from pipelines.ingestion.storage.power import PowerParquetRepository
        from pipelines.processing.cleaning.power_point import process_power_point
        from tests.test_power_pipeline import FakePowerClient, POINT, query
        with tempfile.TemporaryDirectory() as folder:
            history=PowerParquetRepository(Path(folder)/"history")
            request=query(start="2020-01-01",end="2020-01-03")
            client=FakePowerClient()
            history.upsert(process_power_point(client.fetch_point_daily(request.period,POINT,("T2M",))))
            store=HistoricalSnapshotStore(history,Path(folder)/"snapshots")
            region={"region_id":"fixture", "latitude":POINT.latitude,"longitude":POINT.longitude}
            first=store.capture(region,date(2024,1,1))
            content=store.path(first).read_bytes()
            self.assertEqual(first.row_count,3)
            client.overrides[("2020-01-01","T2M")]=21.7
            history.upsert(process_power_point(client.fetch_point_daily(request.period,POINT,("T2M",))))
            second=store.capture(region,date(2024,1,1))
            self.assertNotEqual(first.dataset_id,second.dataset_id)
            self.assertEqual(store.path(first).read_bytes(),content)
            store.path(second).write_bytes(content)
            with self.assertRaisesRegex(ValueError,"alterado"):
                store.capture(region,date(2024,1,1))


class XGBoostAdapterTests(unittest.TestCase):
    def test_real_xgboost_roundtrip_uses_json_without_publishing_anything(self):
        import importlib.util
        if not importlib.util.find_spec("xgboost"):
            self.skipTest("Requiere el extra ml para la prueba real del adapter")
        from ml.training.xgboost import XGBoostTrainer
        from packages.contracts.training import ModelRelease
        from datetime import datetime, timezone
        snapshot=DatasetSnapshot(dataset_id="a"*64,region_id="test",cutoff=date(2024,1,1),first_date=date(2020,1,1),last_date=date(2020,12,31),row_count=240,sha256="fixture")
        dataset=FixtureBuilder().build(snapshot,None,"climate",7)
        trainer=XGBoostTrainer(version="test-only-v1",params={"max_depth":2,"eta":0.3},num_boost_round=10)
        model=trainer.fit(dataset,dataset.samples[:100])
        with tempfile.TemporaryDirectory() as folder:
            store=ModelArtifactStore(Path(folder))
            version="f"*32
            hashes=store.save(version,model,{"synthetic_test":True})
            release=ModelRelease(slot="test:climate:7",version=version,model_kind="climate",region_id="test",horizon_days=7,
                                 dataset_id=snapshot.dataset_id,training_fingerprint="test-only",recipe_version="test-only",policy_version="test-only",
                                 trained_through=date(2020,5,1),feature_names=dataset.feature_names,target_units=dataset.target_units,
                                 artifact_sha256=hashes,metrics={},created_at=datetime.now(timezone.utc))
            loaded=trainer.load(release,store.verify(release))
            self.assertEqual(model.predict(dataset.samples[-5:]),loaded.predict(dataset.samples[-5:]))
