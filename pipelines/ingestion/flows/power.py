"""Flujo local e incremental POWER: GET, procesamiento y persistencia Parquet."""

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from packages.contracts import DataQuery, DateRange, GeoPoint
from packages.contracts.observations import power_location_id
from pipelines.ingestion.http import JsonHTTPClient, write_json
from pipelines.ingestion.sources.nasa.power import PowerClient
from pipelines.ingestion.storage.power import PowerParquetRepository, arrow_modules
from pipelines.processing.cleaning.power_point import process_power_point


class PowerIngestionFlow:
    def __init__(self, client: PowerClient | None = None, repository: PowerParquetRepository | None = None,
                 raw_directory: Path = Path("data/raw/nasa_power")):
        # El checkpoint de observaciones determina qué consultar; los GET elegidos
        # omiten caché por defecto para recoger revisiones reales de NASA.
        self.client = client if client is not None else PowerClient(JsonHTTPClient(cache_dir=None))
        self.repository = repository if repository is not None else PowerParquetRepository()
        self.raw_directory = Path(raw_directory)

    def _plan(self, query: DataQuery, refresh_days: int, chunk_days: int, today: date, force: bool) -> list[DateRange]:
        existing = self.repository.read(query.point, query.period, variables=query.power_parameters)
        covered = {(row["date"], row["variable"]) for row in existing
                   if row["value"] is not None and row["quality"] == "provider_value_unvalidated"}
        windows, start, previous = [], None, None
        day = query.period.start
        refresh_start = today - timedelta(days=refresh_days - 1) if refresh_days else None
        while day <= query.period.end:
            needed = force or (refresh_start is not None and day >= refresh_start) or any(
                (day.isoformat(), variable) not in covered for variable in query.power_parameters)
            if needed:
                if start is None:
                    start = day
                elif (day - start).days >= chunk_days:
                    windows.append(DateRange(start, previous))
                    start = day
                previous = day
            elif start is not None:
                windows.append(DateRange(start, previous))
                start = previous = None
            day += timedelta(days=1)
        if start is not None:
            windows.append(DateRange(start, previous))
        return windows

    def run(self, query: DataQuery, *, refresh_days: int = 90, chunk_days: int = 366,
            force: bool = False, today: date | None = None) -> dict:
        today = today if today is not None else datetime.now(timezone.utc).date()
        if query.point is None or query.period is None:
            raise ValueError("La primera ingesta persistente POWER requiere punto y periodo explícitos.")
        if query.period.end > today:
            raise ValueError("La ingesta histórica no admite fechas futuras.")
        if type(refresh_days) is not int or refresh_days < 0 or type(chunk_days) is not int or not 1 <= chunk_days <= 366:
            raise ValueError("refresh_days debe ser no negativo y chunk_days estar entre 1 y 366.")
        arrow_modules()  # Fallar antes de consumir NASA si falta la dependencia.
        windows = self._plan(query, refresh_days, chunk_days, today, force)
        result = {"source": "NASA_POWER", "query_id": query.query_id, "requested": query.as_dict(),
                  "location_id": power_location_id(query.point), "storage": str(self.repository.root),
                  "chunks": [], "inserted": 0, "updated": 0, "unchanged": 0}
        for window in windows:
            raw = self.client.fetch_point_daily(window, query.point, query.power_parameters)
            digest = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
            raw_path = self.raw_directory / result["location_id"] / f"{window.start}_{window.end}_{digest}.json"
            write_json(raw_path, raw)
            records = process_power_point(raw)
            for row in records:
                row["raw_path"] = str(raw_path)
            counts = self.repository.upsert(records)
            for key, value in counts.items():
                result[key] += value
            result["chunks"].append({**window.as_dict(), "records": len(records), "raw_path": str(raw_path), **counts})
        remaining = self._plan(query, 0, chunk_days, today, False)
        result["remaining_gap_days"] = sum((window.end - window.start).days + 1 for window in remaining)
        result["status"] = "incomplete" if remaining else "ok"
        result["notes"] = "Una fila por ubicación/fecha/variable. Nodata y valores inválidos se conservan y se reintentan. Sin entrenamiento ni inferencia."
        return result
