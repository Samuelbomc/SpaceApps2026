"""Entrenamiento autónomo condicionado por etiquetas, validación temporal y políticas."""

import uuid
from datetime import datetime, timezone

from ml.evaluation.promotion import mae, promotion_decision, temporal_split
from packages.contracts.training import ModelRelease, TrainingOutcome, TrainingPolicy
from pipelines.training.snapshots import fingerprint


class ModelTrainingPipeline:
    def __init__(self, snapshots, artifacts, registry, *, builder=None, trainer=None, policies=None,
                 horizons=(7, 15, 30, 60)):
        self.snapshots, self.artifacts, self.registry = snapshots, artifacts, registry
        self.builder, self.trainer = builder, trainer
        self.policies = policies or {}
        self.horizons = horizons

    def run(self, region, cutoff):
        snapshot = self.snapshots.capture(region, cutoff)
        outcomes = []
        for kind in ("climate", "soil"):
            for horizon in self.horizons:
                slot = f'{region["region_id"]}:{kind}:{horizon}'
                policy = self.policies.get((kind, horizon), TrainingPolicy())
                if snapshot is None:
                    outcome = TrainingOutcome(slot=slot, status="insufficient_labels", message="No hay histórico procesado para la región.")
                elif self.builder is None or self.trainer is None or not policy.max_mae:
                    outcome = TrainingOutcome(slot=slot, status="pending_configuration", dataset_id=snapshot.dataset_id,
                                              message="Falta configurar el constructor de etiquetas verificadas, el trainer o los umbrales de validación.")
                else:
                    outcome = self._train(slot, kind, horizon, snapshot, policy)
                outcomes.append(outcome)
        self.registry.record_outcomes([outcome.model_dump(mode="json") for outcome in outcomes])
        return outcomes

    def _train(self, slot, kind, horizon, snapshot, policy):
        dataset = self.builder.build(snapshot, self.snapshots.path(snapshot), kind, horizon)
        if (dataset.dataset_id != snapshot.dataset_id or dataset.model_kind != kind or dataset.horizon_days != horizon):
            raise ValueError("El constructor devolvió un dataset de otra tarea o snapshot.")
        incumbent = self.registry.current(slot)
        training, validation = temporal_split(dataset, snapshot.cutoff, policy)
        base = {"slot": slot, "dataset_id": snapshot.dataset_id}
        if len(training) < policy.min_train_samples or len(validation) < policy.min_validation_samples:
            return TrainingOutcome(**base, status="insufficient_labels", message="No hay suficientes muestras verificadas después de la separación temporal y su purga.")
        identity = fingerprint({"dataset": dataset.model_dump(mode="json"), "builder": self.builder.version,
                                "trainer": self.trainer.version, "policy": policy.model_dump(mode="json")})
        # Primero verificar el campeón: no ocultar corrupción con un 'unchanged'.
        champion = self.trainer.load(incumbent, self.artifacts.verify(incumbent)) if incumbent else None
        if self.registry.attempt(identity) is not None or (incumbent and incumbent.training_fingerprint == identity):
            return TrainingOutcome(**base, status="unchanged", version=incumbent.version if incumbent else None,
                                   message="Esta versión de datos y configuración ya fue evaluada.")
        if incumbent and sum(sample.label_end > incumbent.trained_through for sample in dataset.samples) < policy.min_new_labels:
            return TrainingOutcome(**base, status="insufficient_labels", version=incumbent.version,
                                   message="Se conserva el campeón: aún faltan etiquetas nuevas suficientes.")
        if incumbent and (incumbent.feature_names != dataset.feature_names or incumbent.target_units != dataset.target_units
                          or incumbent.recipe_version != dataset.recipe_version):
            raise ValueError("Un cambio de esquema requiere una migración explícita del adapter del campeón.")
        fitted = self.trainer.fit(dataset, training)
        targets = dataset.target_units
        candidate_mae = mae(validation, fitted.predict(validation), targets)
        baseline_mae = mae(validation, [sample.baseline for sample in validation], targets)
        incumbent_mae = mae(validation, champion.predict(validation), targets) if champion else None
        accepted, reasons = promotion_decision(candidate_mae, baseline_mae, incumbent_mae, policy)
        metrics = {"candidate_mae": candidate_mae, "baseline_mae": baseline_mae, "incumbent_mae": incumbent_mae,
                   "validation_id": fingerprint([sample.model_dump(mode="json") for sample in validation]),
                   "train_samples": len(training), "validation_samples": len(validation),
                   "train_label_end": max(sample.label_end for sample in training).isoformat(),
                   "validation_feature_start": min(sample.feature_date for sample in validation).isoformat(),
                   "reasons": reasons}
        version = uuid.uuid4().hex
        metadata = {"slot": slot, "version": version, "dataset_id": snapshot.dataset_id,
                    "snapshot_sha256": snapshot.sha256, "training_fingerprint": identity,
                    "recipe_version": dataset.recipe_version, "builder_version": self.builder.version,
                    "trainer_version": self.trainer.version, "policy": policy.model_dump(mode="json"),
                    "feature_names": dataset.feature_names, "target_units": targets, "metrics": metrics}
        # Conservar las features y etiquetas exactas, no solo su hash.
        self._save_prepared(identity, dataset)
        hashes = self.artifacts.save(version, fitted, metadata)
        release = ModelRelease(slot=slot, version=version, model_kind=kind, region_id=snapshot.region_id,
                               horizon_days=horizon, dataset_id=snapshot.dataset_id, training_fingerprint=identity,
                               recipe_version=dataset.recipe_version, policy_version=policy.version,
                               trained_through=max(sample.label_end for sample in dataset.samples),
                               feature_names=dataset.feature_names, target_units=targets, artifact_sha256=hashes,
                               metrics=metrics, created_at=datetime.now(timezone.utc))
        if accepted:
            self.artifacts.verify(release)
            if not self.registry.publish(release, incumbent.version if incumbent else None):
                raise RuntimeError("El campeón cambió durante la evaluación; se requiere una nueva comparación.")
        status = "published" if accepted else "rejected"
        outcome = TrainingOutcome(**base, version=version, status=status,
                                  message="Candidato publicado tras superar la validación." if accepted else "; ".join(reasons))
        self.registry.record_attempt(identity, {"outcome": outcome.model_dump(mode="json"),
                                                "release": release.model_dump(mode="json")})
        return outcome

    def _save_prepared(self, identity, dataset):
        import json
        import os
        import tempfile
        from pipelines.ingestion.storage.power import arrow_modules
        pa, pq = arrow_modules()
        directory = self.snapshots.root / dataset.dataset_id / "prepared"
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{identity}.parquet"
        rows = [{"feature_date": sample.feature_date, "label_start": sample.label_start,
                 "label_end": sample.label_end, "label_available_on": sample.label_available_on,
                 "features": json.dumps(sample.features, sort_keys=True), "targets": json.dumps(sample.targets, sort_keys=True),
                 "baseline": json.dumps(sample.baseline, sort_keys=True), "label_sources": sample.label_sources,
                 "labels_verified": sample.labels_verified} for sample in dataset.samples]
        table = pa.Table.from_pylist(rows).replace_schema_metadata({b"prepared_dataset": json.dumps({
            "feature_names": dataset.feature_names, "target_units": dataset.target_units,
            "recipe_version": dataset.recipe_version, "training_fingerprint": identity}).encode()})
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as handle:
            temporary = type(target)(handle.name)
        try:
            pq.write_table(table, temporary, compression="snappy")
            try:
                os.link(temporary, target)
            except FileExistsError:
                pass
        finally:
            temporary.unlink(missing_ok=True)
