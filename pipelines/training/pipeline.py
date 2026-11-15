"""Entrenamiento autónomo condicionado por etiquetas, validación temporal y políticas."""

import uuid
from datetime import UTC, datetime

from ml.evaluation.promotion import (
    chronological_partitions,
    mae,
    promotion_decision,
    temporal_split,
)
from packages.contracts.training import ModelRelease, TrainingOutcome, TrainingPolicy
from pipelines.training.snapshots import fingerprint


class ModelTrainingPipeline:
    def __init__(
        self,
        snapshots,
        artifacts,
        registry,
        *,
        builder=None,
        trainer=None,
        policies=None,
        horizons=(7, 15, 30, 60),
    ):
        self.snapshots, self.artifacts, self.registry = snapshots, artifacts, registry
        self.builder, self.trainer = builder, trainer
        self.policies = policies or {}
        self.horizons = horizons

    def run(self, region, cutoff):
        snapshot = self.snapshots.capture(region, cutoff)
        outcomes = []
        for kind in ("climate", "soil"):
            for horizon in self.horizons:
                slot = f"{region['region_id']}:{kind}:{horizon}"
                policy = self.policies.get((kind, horizon), TrainingPolicy())
                if snapshot is None:
                    outcome = TrainingOutcome(
                        slot=slot,
                        status="insufficient_labels",
                        message="No hay histórico procesado para la región.",
                    )
                elif self.builder is None or self.trainer is None or not policy.max_mae:
                    outcome = TrainingOutcome(
                        slot=slot,
                        status="pending_configuration",
                        dataset_id=snapshot.dataset_id,
                        message="Falta configurar el constructor de etiquetas verificadas, el trainer o los umbrales de validación.",
                    )
                else:
                    outcome = self._train(slot, kind, horizon, snapshot, policy)
                outcomes.append(outcome)
        self.registry.record_outcomes([outcome.model_dump(mode="json") for outcome in outcomes])
        return outcomes

    def _train(self, slot, kind, horizon, snapshot, policy):
        dataset = self.builder.build(snapshot, self.snapshots.path(snapshot), kind, horizon)
        if (
            dataset.dataset_id != snapshot.dataset_id
            or dataset.model_kind != kind
            or dataset.horizon_days != horizon
        ):
            raise ValueError("El constructor devolvió un dataset de otra tarea o snapshot.")
        incumbent = self.registry.current(slot)
        if policy.split_strategy == "chronological_60_20_20":
            training, validation, test = chronological_partitions(dataset, snapshot.cutoff)
        else:
            training, validation = temporal_split(dataset, snapshot.cutoff, policy)
            test = []
        base = {"slot": slot, "dataset_id": snapshot.dataset_id}
        if (
            len(training) < policy.min_train_samples
            or len(validation) < policy.min_validation_samples
        ):
            return TrainingOutcome(
                **base,
                status="insufficient_labels",
                message="No hay suficientes muestras verificadas después de la separación temporal y su purga.",
            )
        for partition, minimum in [
            (training, policy.min_train_samples),
            (validation, policy.min_validation_samples),
        ] + (
            [(test, policy.min_test_samples)]
            if policy.split_strategy == "chronological_60_20_20"
            else []
        ):
            if any(
                sum(target in row.targets for row in partition) < minimum
                or len({row.spatial_id for row in partition if target in row.targets})
                < policy.min_spatial_locations
                for target in dataset.target_units
            ):
                return TrainingOutcome(
                    **base,
                    status="insufficient_labels",
                    message="Faltan muestras o ubicaciones por objetivo en una partición temporal.",
                )
        identity = fingerprint(
            {
                "dataset": dataset.model_dump(mode="json"),
                "builder": self.builder.version,
                "trainer": self.trainer.version,
                "policy": policy.model_dump(mode="json"),
            }
        )
        # Primero verificar el campeón: no ocultar corrupción con un 'unchanged'.
        champion = (
            self.trainer.load(incumbent, self.artifacts.verify(incumbent)) if incumbent else None
        )
        if self.registry.attempt(identity) is not None or (
            incumbent and incumbent.training_fingerprint == identity
        ):
            return TrainingOutcome(
                **base,
                status="unchanged",
                version=incumbent.version if incumbent else None,
                message="Esta versión de datos y configuración ya fue evaluada.",
            )
        if incumbent and any(
            len(
                {
                    sample.feature_date
                    for sample in dataset.samples
                    if target in sample.targets
                    and sample.label_end
                    > (incumbent.evaluated_through or incumbent.trained_through)
                }
            )
            < policy.min_new_labels
            for target in dataset.target_units
        ):
            return TrainingOutcome(
                **base,
                status="insufficient_labels",
                version=incumbent.version,
                message="Se conserva el campeón: aún faltan etiquetas nuevas suficientes.",
            )
        if incumbent and (
            incumbent.feature_names != dataset.feature_names
            or incumbent.target_units != dataset.target_units
            or incumbent.recipe_version != dataset.recipe_version
        ):
            raise ValueError(
                "Un cambio de esquema requiere una migración explícita del adapter del campeón."
            )
        fitted = (
            self.trainer.fit_with_validation(dataset, training, validation)
            if policy.split_strategy == "chronological_60_20_20"
            and hasattr(self.trainer, "fit_with_validation")
            else self.trainer.fit(dataset, training)
        )
        targets = dataset.target_units
        candidate_mae = mae(validation, fitted.predict(validation), targets)
        baseline_mae = mae(validation, [sample.baseline for sample in validation], targets)
        incumbent_mae = mae(validation, champion.predict(validation), targets) if champion else None
        accepted, reasons = promotion_decision(candidate_mae, baseline_mae, incumbent_mae, policy)
        test_metrics = None
        if test:
            test_candidate = mae(test, fitted.predict(test), targets)
            test_baseline = mae(test, [s.baseline for s in test], targets)
            test_incumbent = mae(test, champion.predict(test), targets) if champion else None
            test_accepted, test_reasons = promotion_decision(
                test_candidate, test_baseline, test_incumbent, policy
            )
            accepted = accepted and test_accepted
            reasons += ["test: " + reason for reason in test_reasons]
            test_metrics = {
                "candidate_mae": test_candidate,
                "baseline_mae": test_baseline,
                "incumbent_mae": test_incumbent,
                "samples": len(test),
                "snapshot_id": fingerprint([s.model_dump(mode="json") for s in test]),
            }
        publication_ready = policy.publication_allowed and dataset.publication_ready
        if accepted and not publication_ready:
            reasons.append(
                "Evaluación técnica superada; falta revisión de publicación, disponibilidad histórica o cobertura de etiquetas."
            )
        metrics = {
            "candidate_mae": candidate_mae,
            "baseline_mae": baseline_mae,
            "incumbent_mae": incumbent_mae,
            "validation_id": fingerprint([sample.model_dump(mode="json") for sample in validation]),
            "train_samples": len(training),
            "validation_samples": len(validation),
            "train_label_end": max(sample.label_end for sample in training).isoformat(),
            "validation_feature_start": min(
                sample.feature_date for sample in validation
            ).isoformat(),
            "reasons": reasons,
            "test": test_metrics,
            "spatial_locations": len({s.spatial_id for s in dataset.samples}),
            "samples_per_target": {
                name: {
                    target: sum(target in sample.targets for sample in partition)
                    for target in dataset.target_units
                }
                for name, partition in [
                    ("train", training),
                    ("validation", validation),
                    ("test", test),
                ]
            },
            "publication_ready": publication_ready,
            "dataset_provenance": dataset.provenance,
        }
        version = uuid.uuid4().hex
        metadata = {
            "slot": slot,
            "version": version,
            "dataset_id": snapshot.dataset_id,
            "snapshot_sha256": snapshot.sha256,
            "training_fingerprint": identity,
            "recipe_version": dataset.recipe_version,
            "builder_version": self.builder.version,
            "trainer_version": self.trainer.version,
            "policy": policy.model_dump(mode="json"),
            "feature_names": dataset.feature_names,
            "target_units": targets,
            "metrics": metrics,
        }
        # Conservar las features y etiquetas exactas, no solo su hash.
        self._save_prepared(identity, dataset)
        hashes = self.artifacts.save(version, fitted, metadata)
        release = ModelRelease(
            slot=slot,
            version=version,
            model_kind=kind,
            region_id=snapshot.region_id,
            horizon_days=horizon,
            dataset_id=snapshot.dataset_id,
            training_fingerprint=identity,
            recipe_version=dataset.recipe_version,
            policy_version=policy.version,
            trained_through=max(sample.label_end for sample in training),
            evaluated_through=max(sample.label_end for sample in dataset.samples),
            validation_status="validated" if accepted and publication_ready else "experimental",
            spatial_scope=dataset.provenance.get("spatial_scope", {}),
            feature_names=dataset.feature_names,
            target_units=targets,
            artifact_sha256=hashes,
            metrics=metrics,
            created_at=datetime.now(UTC),
        )
        if accepted and publication_ready:
            self.artifacts.verify(release)
            if not self.registry.publish(release, incumbent.version if incumbent else None):
                raise RuntimeError(
                    "El campeón cambió durante la evaluación; se requiere una nueva comparación."
                )
        status = (
            "published"
            if accepted and publication_ready
            else "pending_review"
            if accepted
            else "rejected"
        )
        outcome = TrainingOutcome(
            **base,
            version=version,
            status=status,
            message="Candidato publicado tras superar la validación."
            if status == "published"
            else "; ".join(reasons),
        )
        self.registry.record_attempt(
            identity,
            {
                "outcome": outcome.model_dump(mode="json"),
                "release": release.model_dump(mode="json"),
            },
        )
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
        rows = [
            {
                "feature_date": sample.feature_date,
                "label_start": sample.label_start,
                "label_end": sample.label_end,
                "label_available_on": sample.label_available_on,
                "features": sample.features,
                "targets": sample.targets,
                "baseline": sample.baseline,
                "label_sources": sample.label_sources,
                "labels_verified": sample.labels_verified,
            }
            for sample in dataset.samples
        ]
        for row, sample in zip(rows, dataset.samples):
            row.update(
                spatial_id=sample.spatial_id,
                longitude=sample.longitude,
                latitude=sample.latitude,
                observation_cutoff=sample.observation_cutoff,
                label_observed_days=json.dumps(sample.label_observed_days),
            )
        schema = pa.schema(
            [
                pa.field(name, pa.date32())
                for name in ("feature_date", "label_start", "label_end", "label_available_on")
            ]
            + [
                pa.field(
                    "features",
                    pa.struct([pa.field(name, pa.float64()) for name in dataset.feature_names]),
                ),
                pa.field(
                    "targets",
                    pa.struct([pa.field(name, pa.float64()) for name in dataset.target_units]),
                ),
                pa.field(
                    "baseline",
                    pa.struct([pa.field(name, pa.float64()) for name in dataset.target_units]),
                ),
                pa.field("label_sources", pa.list_(pa.string())),
                pa.field("labels_verified", pa.bool_()),
                pa.field("spatial_id", pa.string()),
                pa.field("longitude", pa.float64()),
                pa.field("latitude", pa.float64()),
                pa.field("observation_cutoff", pa.date32()),
                pa.field("label_observed_days", pa.string()),
            ]
        )
        table = pa.Table.from_pylist(rows, schema=schema).replace_schema_metadata(
            {
                b"prepared_dataset": json.dumps(
                    {
                        "prepared_format_version": 2,
                        "feature_names": dataset.feature_names,
                        "target_units": dataset.target_units,
                        "recipe_version": dataset.recipe_version,
                        "training_fingerprint": identity,
                    }
                ).encode()
            }
        )
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as handle:
            temporary = type(target)(handle.name)
        try:
            pq.write_table(table, temporary, compression="zstd")
            try:
                os.link(temporary, target)
            except FileExistsError:
                pass
        finally:
            temporary.unlink(missing_ok=True)
