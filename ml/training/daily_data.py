"""Fuentes diarias inmutables e índices compactos; no expande features sesenta veces."""

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ml.training.expanded_dataset import digest, original_csv_identity
from pipelines.training.snapshots import fingerprint


@dataclass(frozen=True)
class DailySnapshot:
    dataset_id: str
    root: Path
    cutoff: date
    sha256: str
    publication_ready: bool


class DailyTrainingSources:
    def __init__(self, config, source_root, root):
        self.config, self.source_root, self.root = config, Path(source_root), Path(root) / "daily"

    def capture(self, region, cutoff):
        scope = self.config["spatial_scope"]
        if not (
            scope["west"] <= region["longitude"] <= scope["east"]
            and scope["south"] <= region["latitude"] <= scope["north"]
        ):
            return None
        manifest_path, validation_path = (
            self.source_root / "manifest.json",
            self.source_root / "validation.json",
        )
        if not manifest_path.is_file() or not validation_path.is_file():
            return None
        manifest = json.loads(manifest_path.read_text())
        validation = json.loads(validation_path.read_text())
        if (
            manifest["recipe_version"] != self.config["recipe_version"]
            or validation.get("status") != "PASS"
        ):
            raise ValueError("El preparado diario no tiene una receta y validación compatibles.")
        files = {}
        audited = True
        available_models = {}
        receipt_path = self.source_root / "publication-evidence.json"
        receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else {}
        for name, spec in self.config["models"].items():
            relatives = [
                "features.csv",
                "labels.csv",
                *[f"pairs/lead_{lead:02d}.npz" for lead in range(1, 61)],
            ]
            if name not in manifest["models"] or any(
                not (self.source_root / name / relative).is_file() for relative in relatives
            ):
                continue
            provided = manifest["models"][name]
            if (
                provided["features"] != spec["features"]
                or provided["base_features"] != spec["base_features"]
            ):
                raise ValueError("Las columnas diarias no coinciden con la receta del modelo.")
            available_models[name] = provided
            for relative in relatives:
                key = f"{name}/{relative}"
                source = self.source_root / key
                checksum = digest(source)
                verified = validation.get("source_sha256", {}).get(name, {}).get(relative)
                original = spec["original_source_sha256"][relative]
                if checksum not in (verified, original) and not (
                    source.suffix == ".csv" and original_csv_identity(source, original)
                ):
                    raise ValueError(
                        f"Fuente diaria cambiada sin validación vinculada a su hash: {key}."
                    )
                files[key] = checksum
                audited &= receipt.get("sources", {}).get(name, {}).get(relative) == checksum
        if not available_models:
            return None
        manifest = {**manifest, "models": available_models}
        audited &= bool(
            receipt.get("reviewed_by")
            and receipt.get("reviewed_on")
            and receipt.get("feature_availability_verified") is True
            and receipt.get("spatial_scope_verified") is True
            and receipt.get("recipe_version") == self.config["recipe_version"]
        )
        body = {
            "schema": "daily-training-sources-v1",
            "manifest": manifest,
            "validation": validation,
            "files": files,
            "receipt": receipt,
            "config_sha256": fingerprint(self.config),
        }
        identity = fingerprint(body)
        destination = self.root / identity
        self.root.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            temporary = Path(tempfile.mkdtemp(prefix="daily-capture-", dir=self.root))
            try:
                for key, checksum in files.items():
                    target = temporary / key
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(self.source_root / key, target)
                    if digest(target) != checksum or digest(self.source_root / key) != checksum:
                        raise ValueError("Las fuentes cambiaron durante la captura diaria.")
                (temporary / "source-manifest.json").write_text(json.dumps(body, sort_keys=True))
                try:
                    os.rename(temporary, destination)
                except FileExistsError:
                    pass
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
        stored = json.loads((destination / "source-manifest.json").read_text())
        if stored != body:
            raise ValueError("El manifiesto diario inmutable fue alterado.")
        return DailySnapshot(
            identity, destination, cutoff, digest(destination / "source-manifest.json"), audited
        )


class DailyDesign:
    def __init__(self, snapshot, name, spec, *, label_lag_days=2):
        import numpy as np
        import pandas as pd

        self.np, self.pd = np, pd
        self.name, self.spec, self.snapshot = name, spec, snapshot
        self.metadata = json.loads((snapshot.root / "source-manifest.json").read_text())
        for relative in [
            "features.csv",
            "labels.csv",
            *[f"pairs/lead_{lead:02d}.npz" for lead in range(1, 61)],
        ]:
            key = f"{name}/{relative}"
            if digest(snapshot.root / key) != self.metadata["files"][key]:
                raise ValueError("El snapshot diario fue alterado.")
        features = pd.read_csv(snapshot.root / name / "features.csv")
        labels = pd.read_csv(snapshot.root / name / "labels.csv")
        self.features = features[spec["base_features"]].to_numpy(dtype=np.float32)
        self.targets = labels.target.to_numpy(dtype=np.float32)
        if not np.isfinite(self.features).all() or not np.isfinite(self.targets).all():
            raise ValueError("El preparado diario contiene valores no finitos.")
        if not np.array_equal(features.feature_id, np.arange(len(features))) or not np.array_equal(
            labels.label_id, np.arange(len(labels))
        ):
            raise ValueError("Los índices normalizados no coinciden con sus filas.")
        if (
            features.duplicated(["point_id", "issue_date"]).any()
            or labels.duplicated(["point_id", "target_date"]).any()
        ):
            raise ValueError("Hay una celda/fecha duplicada en el preparado diario.")

        def days(values):
            if not values.astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
                raise ValueError("Las fechas diarias deben tener formato ISO de día.")
            return pd.to_datetime(values).to_numpy(dtype="datetime64[D]").astype(np.int32)

        self.issue, self.target_date = days(features.issue_date), days(labels.target_date)
        if not np.array_equal(
            days(features.observation_cutoff), self.issue - 2
        ) or not np.array_equal(days(features.radiation_observation_cutoff), self.issue - 7):
            raise ValueError(
                "Los cortes meteorológico y de radiación no respetan la receta diaria."
            )
        self.available = (
            days(labels.label_available_on)
            if "label_available_on" in labels
            else self.target_date + label_lag_days
        )
        if (self.available < self.target_date).any():
            raise ValueError("La etiqueta no puede estar disponible antes de ser observada.")
        if (
            "features_available_on" in features
            and (days(features.features_available_on) > self.issue).any()
        ):
            raise ValueError("Hay features posteriores a su emisión.")
        if snapshot.publication_ready and (
            "features_available_on" not in features or "label_available_on" not in labels
        ):
            raise ValueError("Publicar exige disponibilidad explícita por fila.")
        self.points, self.label_points = features.point_id.to_numpy(), labels.point_id.to_numpy()
        self.baseline = features[spec["baseline_feature"]].to_numpy(dtype=np.float32)
        self.cutoff = int(np.datetime64(snapshot.cutoff, "D").astype(np.int32))
        self.pairs = []
        used = np.zeros(len(features), dtype=bool)
        for lead in range(1, 61):
            with np.load(
                snapshot.root / name / "pairs" / f"lead_{lead:02d}.npz", allow_pickle=False
            ) as pair:
                fi, li = pair["feature_id"], pair["label_id"]
                if (
                    fi.ndim != 1
                    or li.shape != fi.shape
                    or fi.dtype.kind not in "iu"
                    or li.dtype.kind not in "iu"
                    or (fi < 0).any()
                    or (li < 0).any()
                    or (fi >= len(features)).any()
                    or (li >= len(labels)).any()
                ):
                    raise ValueError("Índices diarios inválidos.")
                if (
                    not np.array_equal(self.points[fi], self.label_points[li])
                    or not (self.target_date[li] - self.issue[fi] == lead).all()
                ):
                    raise ValueError("Un par enlaza otra celda o un día incorrecto.")
                if len(np.unique(fi)) != len(fi):
                    raise ValueError("Hay pares repetidos para una celda/emisión/lead.")
                eligible = (self.available[li] <= self.cutoff) & (self.issue[fi] <= self.cutoff)
                fi, li = fi[eligible], li[eligible]
                self.pairs.append((fi, li, lead))
                used[fi] = True
        dates = np.unique(self.issue[used])
        self.boundaries = None
        if len(dates) >= 5:
            self.test_start = int(dates[int(len(dates) * 0.8)])
            dev_used = np.zeros(len(features), dtype=bool)
            for fi, li, _ in self.pairs:
                dev = (self.issue[fi] < self.test_start) & (
                    self.target_date[li] < self.test_start - 2
                )
                dev_used[fi[dev]] = True
            dev_dates = np.unique(self.issue[dev_used])
            if len(dev_dates) >= 5:
                self.boundaries = [
                    int(dev_dates[int(len(dev_dates) * q)]) for q in (0.4, 0.55, 0.7, 0.85)
                ] + [self.test_start]
        import hashlib

        effective = hashlib.sha256(self.features[used].tobytes())
        effective.update(self.issue[used].tobytes())
        effective.update(json.dumps(self.points[used].tolist()).encode())
        for fi, li, lead in self.pairs:
            effective.update(bytes([lead]))
            effective.update(self.issue[fi].tobytes())
            effective.update(self.target_date[li].tobytes())
            effective.update(self.targets[li].tobytes())
        self.identity = fingerprint(
            {
                "effective_design": effective.hexdigest(),
                "name": name,
                "publication_ready": snapshot.publication_ready,
                "receipt": self.metadata["receipt"],
            }
        )

    def indices(self, partition, fold=None):
        for fi, li, lead in self.pairs:
            issue, target = self.issue[fi], self.target_date[li]
            if partition == "test":
                mask = issue >= self.test_start
            elif partition == "development":
                mask = (issue < self.test_start) & (target < self.test_start - 2)
            else:
                start, end = self.boundaries[fold : fold + 2]
                mask = (
                    (issue < start) & (target < start - 2)
                    if partition == "train"
                    else (issue >= start) & (issue < end) & (target < end - 2)
                ) & (target < self.test_start - 2)
            yield fi[mask], li[mask], lead

    def batches(self, partition, fold=None, batch_size=65536):
        from ml.datasets.calendar import target_calendar

        np = self.np
        for ids, lids, lead in self.indices(partition, fold):
            for offset in range(0, len(ids), batch_size):
                xids, yids = ids[offset : offset + batch_size], lids[offset : offset + batch_size]
                calendar = np.column_stack(
                    list(target_calendar(self.target_date[yids].astype("datetime64[D]")).values())
                ).astype(np.float32)
                matrix = np.column_stack(
                    [self.features[xids], np.full(len(xids), lead, dtype=np.float32), calendar]
                )
                yield (
                    matrix,
                    self.targets[yids],
                    self.baseline[xids],
                    self.issue[xids],
                    self.target_date[yids],
                    self.points[xids],
                )

    def summary(self, partition, fold=None):
        count = 0
        points = set()
        first = None
        last = None
        for fi, li, _ in self.indices(partition, fold):
            if not len(fi):
                continue
            issue, observed = self.issue[fi], self.target_date[li]
            count += len(fi)
            points.update(self.np.unique(self.points[fi]).tolist())
            first = int(issue.min()) if first is None else min(first, int(issue.min()))
            last = int(observed.max()) if last is None else max(last, int(observed.max()))
        return {"rows": count, "locations": len(points), "first_issue": first, "last_target": last}
