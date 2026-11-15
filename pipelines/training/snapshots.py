"""Copias inmutables del histórico procesado completo, sin usar la ventana SQL reciente."""

import hashlib
import json
import os
import tempfile
from datetime import date
from pathlib import Path

from packages.contracts import DateRange, GeoPoint
from packages.contracts.training import DatasetSnapshot
from pipelines.ingestion.storage.power import (
    PowerParquetRepository,
    arrow_modules,
    observation_schema,
)


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
        ).encode()
    ).hexdigest()


class HistoricalSnapshotStore:
    def __init__(self, history=None, root=Path("data/datasets")):
        self.history = history if history is not None else PowerParquetRepository()
        self.root = Path(root)

    def path(self, snapshot):
        if len(snapshot.dataset_id) != 64 or any(
            c not in "0123456789abcdef" for c in snapshot.dataset_id
        ):
            raise ValueError("Identificador de snapshot inválido.")
        return self.root / snapshot.dataset_id / "observations.parquet"

    def capture(self, region, cutoff):
        rows = self.history.read(
            GeoPoint(region["latitude"], region["longitude"]), DateRange(date(1900, 1, 1), cutoff)
        )
        if not rows:
            return None
        # Orden canónico y contenido completo: las revisiones producen otra versión recuperable.
        rows.sort(
            key=lambda row: (
                row["date"],
                row["source"],
                row["product"],
                row["variable"],
                row["time_standard"],
            )
        )
        identity = fingerprint({"region": region, "schema": "power_observation_v1", "rows": rows})
        directory = self.root / identity
        target = directory / "observations.parquet"
        directory.mkdir(parents=True, exist_ok=True)
        pa, pq = arrow_modules()
        if not target.exists():
            table = pa.Table.from_pylist(
                [{**row, "date": date.fromisoformat(row["date"])} for row in rows],
                schema=observation_schema(),
            )
            with tempfile.NamedTemporaryFile(
                dir=directory, suffix=".parquet", delete=False
            ) as handle:
                temporary = Path(handle.name)
            try:
                pq.write_table(table, temporary, compression="snappy")
                # No se sobreescribe una versión ya existente.
                try:
                    os.link(temporary, target)
                except FileExistsError:
                    pass
            finally:
                temporary.unlink(missing_ok=True)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        snapshot = DatasetSnapshot(
            dataset_id=identity,
            region_id=region["region_id"],
            cutoff=cutoff,
            first_date=rows[0]["date"],
            last_date=rows[-1]["date"],
            row_count=len(rows),
            sha256=digest,
        )
        manifest = directory / "manifest.json"
        # cutoff cambia entre ejecuciones sin cambiar los datos: el manifiesto fija la primera captura.
        if not manifest.exists():
            with manifest.open("x") as handle:
                handle.write(snapshot.model_dump_json(indent=2))
        else:
            original = DatasetSnapshot.model_validate_json(manifest.read_text())
            if original.sha256 != digest:
                raise ValueError("El snapshot histórico fue alterado; se bloquea el entrenamiento.")
        return snapshot
