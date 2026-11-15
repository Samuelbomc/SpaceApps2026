"""Repositorio Parquet de observaciones POWER, particionado por punto y año."""

import os
import tempfile
from collections import defaultdict
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from packages.contracts import DateRange, GeoPoint
from packages.contracts.observations import PowerObservation, power_location_id
from pipelines.ingestion.http import IngestionError


def arrow_modules():
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        return pa, pq
    except ImportError:
        raise IngestionError("Instala almacenamiento Parquet: python -m pip install '.[storage]'.") from None


def observation_schema():
    pa, _ = arrow_modules()
    names = ("source", "product", "product_version", "api_version", "location_id", "cell_id",
             "latitude", "longitude", "response_latitude", "response_longitude", "date", "variable",
             "value", "raw_value", "unit", "quality", "time_standard", "resolution", "retrieved_at",
             "data_sources", "response_sha256", "raw_path")
    numeric = {"latitude", "longitude", "response_latitude", "response_longitude", "value"}
    return pa.schema([(name, pa.date32() if name == "date" else pa.float64() if name in numeric else pa.string())
                      for name in names], metadata={b"field_shift_schema": b"power_observation_v1"})


class PowerParquetRepository:
    def __init__(self, root: Path = Path("data/observations/nasa_power")):
        self.root = Path(root)

    @contextmanager
    def _writer_lock(self):
        self.root.mkdir(parents=True, exist_ok=True)
        lock = self.root / ".write.lock"
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise IngestionError("Hay otra escritura Parquet activa o un bloqueo pendiente de una ejecución interrumpida.") from None
        try:
            os.close(descriptor)
            yield
        finally:
            lock.unlink(missing_ok=True)

    @staticmethod
    def _read_file(path: Path) -> list[PowerObservation]:
        _, pq = arrow_modules()
        # ParquetFile evita inferir columnas de partición desde carpetas padre.
        table = pq.ParquetFile(path).read()
        if table.schema.metadata is None or table.schema.metadata.get(b"field_shift_schema") != b"power_observation_v1":
            raise IngestionError(f"Versión de esquema Parquet desconocida en {path}.")
        rows = table.to_pylist()
        for row in rows:
            row["date"] = row["date"].isoformat()
        return rows

    @staticmethod
    def _key(row: dict) -> tuple:
        return row["source"], row["product"], row["location_id"], row["date"], row["variable"], row["time_standard"]

    def read(self, point: GeoPoint, period: DateRange, *, variables: tuple[str, ...] | None = None) -> list[PowerObservation]:
        rows = []
        for year in range(period.start.year, period.end.year + 1):
            path = self.root / power_location_id(point) / f"{year}.parquet"
            if path.exists():
                rows.extend(row for row in self._read_file(path)
                            if period.start.isoformat() <= row["date"] <= period.end.isoformat()
                            and (variables is None or row["variable"] in variables))
        return sorted(rows, key=lambda row: (row["date"], row["variable"]))

    def upsert(self, records: list[PowerObservation]) -> dict:
        if not records:
            return {"inserted": 0, "updated": 0, "unchanged": 0}
        pa, pq = arrow_modules()
        schema = observation_schema()
        partitions = defaultdict(dict)
        for row in records:
            day = date.fromisoformat(row["date"])
            expected_id = power_location_id(GeoPoint(row["latitude"], row["longitude"]))
            if (row["location_id"] != expected_id or row["source"] != "NASA_POWER"
                    or row["product"] != "POWER_DAILY" or row["time_standard"] != "UTC"):
                raise ValueError("Identidad de observación POWER inválida.")
            partitions[(expected_id, day.year)][self._key(row)] = dict(row)
        counts = {"inserted": 0, "updated": 0, "unchanged": 0}
        with self._writer_lock():
            for (location_id, year), incoming in sorted(partitions.items()):
                path = self.root / location_id / f"{year}.parquet"
                existing = {self._key(row): row for row in self._read_file(path)} if path.exists() else {}
                changed = False
                for key, row in incoming.items():
                    state = "inserted" if key not in existing else "unchanged" if existing[key] == row else "updated"
                    counts[state] += 1
                    changed |= state != "unchanged"
                    existing[key] = row
                if not changed:
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                rows = [{**existing[key], "date": date.fromisoformat(existing[key]["date"])} for key in sorted(existing)]
                table = pa.Table.from_pylist(rows, schema=schema)
                temporary = None
                try:
                    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as handle:
                        temporary = Path(handle.name)
                    pq.write_table(table, temporary, compression="snappy")
                    os.replace(temporary, path)
                finally:
                    if temporary is not None:
                        temporary.unlink(missing_ok=True)
        return counts
