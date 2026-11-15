"""Constructor multiespacial desde tablas procesadas, con captura Parquet inmutable."""

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from datetime import date, timedelta
from pathlib import Path

from ml.training.expanded_config import HORIZONS, TARGETS
from packages.contracts.training import DatasetSnapshot, LabeledSample, PreparedDataset
from pipelines.training.snapshots import fingerprint


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def original_csv_identity(path, expected):
    """Git puede convertir CRLF de los CSV entrenados en Windows a LF."""
    lf, crlf = hashlib.sha256(), hashlib.sha256()
    with Path(path).open("rb") as handle:
        for line in handle:
            ending = line.endswith(b"\n")
            body = line[:-2] if line.endswith(b"\r\n") else line[:-1] if ending else line
            lf.update(body + (b"\n" if ending else b""))
            crlf.update(body + (b"\r\n" if ending else b""))
    return expected in (lf.hexdigest(), crlf.hexdigest())


class ExpandedTrainingSnapshots:
    def __init__(self, config, source_root=Path("data/prepared"), root=Path("data/datasets")):
        self.config, self.source_root, self.root = config, Path(source_root), Path(root)

    def path(self, snapshot):
        if not re.fullmatch(r"[0-9a-f]{64}", snapshot.dataset_id):
            raise ValueError("Identificador de snapshot inválido.")
        return self.root / snapshot.dataset_id / "training-sources.json"

    def capture(self, region, cutoff):
        scope = self.config["spatial_scope"]
        if (
            not scope["west"] <= region["longitude"] <= scope["east"]
            or not scope["south"] <= region["latitude"] <= scope["north"]
        ):
            return None
        sources = {}
        for horizon in HORIZONS:
            for target, spec in self.config["sources"][str(horizon)].items():
                source = self.source_root / spec["relative_path"]
                if not source.is_file():
                    return None
                manifest = json.loads((source.parent / "manifest.json").read_text())
                validation = json.loads((source.parent / "validation.json").read_text())[target]
                metadata = manifest[target]
                checksum = digest(source)
                if (
                    metadata["features"] != spec["features"]
                    or metadata.get("horizon_days", 7) != horizon
                    or metadata["target"] != "target"
                    or validation["status"] != "PASS"
                    or validation["rows"] != metadata["rows"]
                ):
                    raise ValueError(f"Manifiesto/validación incompatibles: {horizon}d/{target}.")
                if (
                    validation.get("source_sha256") != checksum
                    and spec["original_source_sha256"] != checksum
                    and not original_csv_identity(source, spec["original_source_sha256"])
                ):
                    raise ValueError(
                        f"El CSV {horizon}d/{target} cambió sin una validación asociada a su hash."
                    )
                receipt_path = source.parent / "publication-evidence.json"
                receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else None
                sources[f"{horizon}/{target}"] = {
                    "source_sha256": checksum,
                    "spec": spec,
                    "metadata": metadata,
                    "validation": validation,
                    "receipt": receipt,
                    "source": source,
                }
        identity = fingerprint(
            {
                "schema": "expanded-training-sources-v1",
                "region": region,
                "config": self.config,
                "sources": {k: {x: v[x] for x in v if x != "source"} for k, v in sources.items()},
            }
        )
        destination = self.root / identity
        self.root.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            import pyarrow as pa
            import pyarrow.csv as arrow_csv
            import pyarrow.parquet as pq

            temporary = Path(tempfile.mkdtemp(prefix="training-snapshot-", dir=self.root))
            try:
                records = {}
                for key, record in sources.items():
                    source = record["source"]
                    spec = record["spec"]
                    types = {name: pa.float64() for name in spec["features"]}
                    types.update(
                        {
                            "target": pa.float64(),
                            "longitude": pa.float64(),
                            "latitude": pa.float64(),
                            "point_id": pa.string(),
                            "issue_date": pa.string(),
                            "observation_cutoff": pa.string(),
                            "target_start": pa.string(),
                            "target_end": pa.string(),
                        }
                    )
                    reader = arrow_csv.open_csv(
                        source, convert_options=arrow_csv.ConvertOptions(column_types=types)
                    )
                    path = temporary / f"{key}.parquet"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    count = 0
                    with pq.ParquetWriter(path, reader.schema, compression="zstd") as writer:
                        for batch in reader:
                            count += batch.num_rows
                            writer.write_batch(batch)
                    if (
                        count != record["metadata"]["rows"]
                        or digest(source) != record["source_sha256"]
                    ):
                        raise ValueError(
                            "La fuente cambió durante su captura o el número de filas es incorrecto."
                        )
                    records[key] = {k: v for k, v in record.items() if k != "source"}
                    records[key].update(
                        parquet=f"{key}.parquet", parquet_sha256=digest(path), rows=count
                    )
                body = {
                    "schema": "expanded-training-sources-v1",
                    "config_sha256": fingerprint(self.config),
                    "spatial_scope": scope,
                    "sources": records,
                }
                (temporary / "training-sources.json").write_text(
                    json.dumps(body, sort_keys=True, indent=2)
                )
                try:
                    os.rename(temporary, destination)
                except FileExistsError:
                    pass
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
        manifest = destination / "training-sources.json"
        body = json.loads(manifest.read_text())
        if body["config_sha256"] != fingerprint(self.config):
            raise ValueError("La configuración del snapshot fue alterada.")
        for record in body["sources"].values():
            if digest(destination / record["parquet"]) != record["parquet_sha256"]:
                raise ValueError("El snapshot Parquet fue alterado.")
        return DatasetSnapshot(
            dataset_id=identity,
            region_id=region["region_id"],
            cutoff=cutoff,
            first_date=min(r["metadata"]["first_issue"] for r in sources.values()),
            last_date=max(r["metadata"]["last_issue"] for r in sources.values()),
            row_count=sum(r["metadata"]["rows"] for r in sources.values()),
            sha256=digest(manifest),
            schema_version="expanded-training-sources-v1",
        )


class ExpandedTrainingDatasetBuilder:
    version = "expanded-dataset-builder-v1"

    def __init__(self, config):
        self.config = config

    def build(self, snapshot, observations_path, model_kind, horizon_days):
        import pyarrow.parquet as pq

        if digest(observations_path) != snapshot.sha256:
            raise ValueError("El manifiesto del snapshot fue alterado.")
        body = json.loads(Path(observations_path).read_text())
        if body["config_sha256"] != fingerprint(self.config):
            raise ValueError("La receta del snapshot no coincide con el constructor.")
        targets = TARGETS[:-1] if model_kind == "climate" else TARGETS[-1:]
        joined = {}
        publication_ready = True
        excluded_future = 0
        lag = self.config["label_lag_days"]
        for target in targets:
            record = body["sources"][f"{horizon_days}/{target}"]
            spec = record["spec"]
            path = Path(observations_path).parent / record["parquet"]
            if digest(path) != record["parquet_sha256"]:
                raise ValueError("El dataset Parquet fue alterado.")
            receipt = record["receipt"]
            audited = bool(
                receipt
                and receipt.get("reviewed_by")
                and receipt.get("reviewed_on")
                and receipt.get("recipe_version") == self.config["recipe_version"]
                and receipt.get("spatial_scope_verified") is True
                and receipt.get("feature_availability_verified") is True
                and receipt.get("sources", {}).get(target) == record["source_sha256"]
            )
            publication_ready &= audited
            for batch in pq.ParquetFile(path).iter_batches(batch_size=2048):
                for row in batch.to_pylist():
                    issue = date.fromisoformat(row["issue_date"])
                    cut = date.fromisoformat(row["observation_cutoff"])
                    start = date.fromisoformat(row["target_start"])
                    end = date.fromisoformat(row["target_end"])
                    if (
                        cut != issue - timedelta(days=2)
                        or start != issue + timedelta(days=1)
                        or end != issue + timedelta(days=horizon_days)
                    ):
                        raise ValueError("La fila no respeta t-2 y el horizonte t+1..t+H.")
                    if audited and (
                        row.get("label_available_on") is None
                        or row.get("features_available_on") is None
                    ):
                        raise ValueError(
                            "La revisión de publicación requiere fechas explícitas de disponibilidad."
                        )
                    available = (
                        date.fromisoformat(str(row["label_available_on"]))
                        if row.get("label_available_on") is not None
                        else end + timedelta(days=lag)
                    )
                    if (
                        row.get("features_available_on") is not None
                        and date.fromisoformat(str(row["features_available_on"])) > issue
                    ):
                        raise ValueError(
                            "Las entradas no estaban disponibles al emitir el pronóstico."
                        )
                    if available < end:
                        raise ValueError(
                            "La etiqueta no puede estar disponible antes de terminar su periodo."
                        )
                    if available > snapshot.cutoff:
                        excluded_future += 1
                        continue
                    x, y = float(row["longitude"]), float(row["latitude"])
                    scope = body["spatial_scope"]
                    if (
                        not scope["west"] - 1e-7 <= x <= scope["east"] + 1e-7
                        or not scope["south"] - 1e-7 <= y <= scope["north"] + 1e-7
                    ):
                        raise ValueError("Celda fuera del ámbito de entrenamiento.")
                    features = {name: float(row[name]) for name in spec["features"]}
                    value = float(row["target"])
                    if not all(math.isfinite(v) for v in [*features.values(), value]):
                        raise ValueError("No se admiten valores ausentes o no finitos.")
                    if (
                        target == "precipitation"
                        and value < 0
                        or target == "moisture"
                        and not 0.02 <= value <= 0.5
                    ):
                        raise ValueError("Etiqueta fuera del dominio de la receta.")
                    # Los CSV climáticos usan prefijos distintos para la misma celda.
                    point = row["point_id"].rsplit("_", 1)[-1]
                    spatial = f"{x:.10f},{y:.10f}"
                    key = (issue, spatial)
                    if key not in joined:
                        joined[key] = {
                            "issue": issue,
                            "cut": cut,
                            "start": start,
                            "end": end,
                            "available": available,
                            "features": features,
                            "longitude": x,
                            "latitude": y,
                            "targets": {},
                            "baseline": {},
                            "sources": [],
                            "coverage": {},
                        }
                    item = joined[key]
                    if (
                        target in item["targets"]
                        or item["features"] != features
                        or item["end"] != end
                    ):
                        raise ValueError(
                            "Filas duplicadas o features contradictorias entre objetivos de una celda."
                        )
                    item["available"] = max(item["available"], available)
                    item["targets"][target] = value
                    item["baseline"][target] = (
                        features[spec["baseline_feature"]] * spec["baseline_scale"]
                    )
                    item["sources"].append(f"{target}:{record['source_sha256']}:cell-{point}")
                    coverage = (
                        int(row["target_observed_days"]) if target == "moisture" else horizon_days
                    )
                    if not 1 <= coverage <= horizon_days:
                        raise ValueError("Cobertura de etiqueta inválida.")
                    item["coverage"][target] = coverage
                    if target == "moisture":
                        publication_ready &= coverage == horizon_days
        samples = [
            LabeledSample(
                feature_date=item["issue"],
                observation_cutoff=item["cut"],
                spatial_id=spatial,
                longitude=item["longitude"],
                latitude=item["latitude"],
                label_start=item["start"],
                label_end=item["end"],
                label_available_on=item["available"],
                features=item["features"],
                targets=item["targets"],
                baseline=item["baseline"],
                label_sources=item["sources"],
                labels_verified=True,
                label_observed_days=item["coverage"],
            )
            for (_, spatial), item in sorted(joined.items())
        ]
        return PreparedDataset(
            dataset_id=snapshot.dataset_id,
            recipe_version=self.config["recipe_version"],
            model_kind=model_kind,
            horizon_days=horizon_days,
            feature_names=self.config["sources"][str(horizon_days)][targets[0]]["features"],
            target_units={
                target: self.config["sources"][str(horizon_days)][target]["unit"]
                for target in targets
            },
            samples=samples,
            target_mode="per_target",
            publication_ready=bool(samples) and publication_ready,
            provenance={
                "spatial_scope": body["spatial_scope"],
                "source_manifest_sha256": snapshot.sha256,
                "excluded_unavailable_labels": excluded_future,
                "label_lag_days_assumed": lag,
                "verification": "prepared-source-integrity; publication requires audited availability and complete labels",
            },
        )
