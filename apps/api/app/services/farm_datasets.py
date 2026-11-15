"""CSV locales acotados y auditables; validar formato no certifica una medición."""

import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from psycopg.errors import UniqueViolation

from packages.contracts.farms import (
    Farm,
    FarmDataset,
    FarmFeatureBundle,
    FarmModelContext,
    LocalObservation,
)

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 20000
VARIABLES = [
    {
        "variable": "air_temperature",
        "label": "Temperatura media del aire",
        "unit": "C",
        "aggregation": "daily_mean",
        "minimum": None,
        "maximum": None,
    },
    {
        "variable": "relative_humidity",
        "label": "Humedad relativa del aire",
        "unit": "%",
        "aggregation": "daily_mean",
        "minimum": 0,
        "maximum": 100,
    },
    {
        "variable": "precipitation",
        "label": "Precipitación acumulada del día",
        "unit": "mm",
        "aggregation": "daily_total",
        "minimum": 0,
        "maximum": None,
    },
    {
        "variable": "soil_moisture",
        "label": "Humedad volumétrica del suelo",
        "unit": "m3/m3",
        "aggregation": "daily_observation",
        "minimum": 0,
        "maximum": 1,
    },
    {
        "variable": "soil_ph",
        "label": "pH del suelo",
        "unit": "pH",
        "aggregation": "daily_observation",
        "minimum": 0,
        "maximum": 14,
    },
    {
        "variable": "crop_yield",
        "label": "Rendimiento de la cosecha",
        "unit": "t/ha",
        "aggregation": "harvest_observation",
        "minimum": 0,
        "maximum": None,
    },
]
RULES = {item["variable"]: item for item in VARIABLES}


def parse_csv(content: bytes, *, today=None):
    if not content or len(content) > MAX_FILE_BYTES:
        raise ValueError("El CSV debe contener datos y pesar como máximo 5 MiB.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("Guarda el CSV con codificación UTF-8.") from None
    if "\x00" in text:
        raise ValueError("El archivo no es un CSV de texto válido.")
    header = text.splitlines()[0] if text.splitlines() else ""
    delimiter = ";" if header.count(";") > header.count(",") else ","
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    if reader.fieldnames is None:
        raise ValueError("Falta el encabezado del CSV.")
    fields = [value.strip() for value in reader.fieldnames]
    required = {"date", "variable", "value", "unit"}
    if (
        len(fields) != len(set(fields))
        or not required.issubset(fields)
        or set(fields) - required - {"crop"}
    ):
        raise ValueError(
            "Usa las columnas date,variable,value,unit y, opcionalmente, crop. Descarga la plantilla."
        )
    reader.fieldnames = fields
    today = today or datetime.now(ZoneInfo("America/Bogota")).date()
    rows, seen = [], set()
    try:
        for raw in reader:
            line = reader.line_num
            if len(rows) >= MAX_ROWS:
                raise ValueError(f"El archivo admite como máximo {MAX_ROWS} observaciones.")
            if None in raw or any(value is None for value in raw.values()):
                raise ValueError(f"Fila {line}: cantidad de columnas incorrecta.")
            values = {key: value.strip() for key, value in raw.items()}
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", values["date"]):
                raise ValueError(f"Fila {line}: usa fechas AAAA-MM-DD.")
            try:
                observed = date.fromisoformat(values["date"])
            except ValueError:
                raise ValueError(f"Fila {line}: fecha inválida.") from None
            if observed > today:
                raise ValueError(
                    f"Fila {line}: una observación histórica no puede tener fecha futura."
                )
            rule = RULES.get(values["variable"])
            if rule is None:
                raise ValueError(
                    f"Fila {line}: variable no admitida; consulta el catálogo de variables."
                )
            if values["unit"] != rule["unit"]:
                raise ValueError(
                    f"Fila {line}: {values['variable']} requiere la unidad {rule['unit']}."
                )
            try:
                value = float(values["value"])
            except ValueError:
                raise ValueError(
                    f"Fila {line}: escribe un valor numérico con punto decimal."
                ) from None
            if (
                not math.isfinite(value)
                or (rule["minimum"] is not None and value < rule["minimum"])
                or (rule["maximum"] is not None and value > rule["maximum"])
            ):
                raise ValueError(
                    f"Fila {line}: valor ausente, no finito o fuera del rango permitido."
                )
            crop = values.get("crop", "")
            if (
                len(crop) > 80
                or (crop and not crop[0].isalnum())
                or any(ord(char) < 32 for char in crop)
            ):
                raise ValueError(f"Fila {line}: nombre de cultivo inválido.")
            if values["variable"] == "crop_yield" and not crop:
                raise ValueError(f"Fila {line}: indica crop para identificar la cosecha.")
            key = (observed, values["variable"], crop)
            if key in seen:
                raise ValueError(
                    f"Fila {line}: observación repetida para fecha, variable y cultivo."
                )
            seen.add(key)
            rows.append(
                {
                    "date": observed,
                    "variable": values["variable"],
                    "value": value,
                    "unit": values["unit"],
                    "crop": crop,
                }
            )
    except csv.Error:
        raise ValueError("CSV mal formado; revisa las comillas y las columnas.") from None
    if not rows:
        raise ValueError("El archivo solo tiene encabezados; agrega observaciones reales.")
    return rows


class FarmDatasetService:
    def __init__(self, repository, root: Path):
        self.repository, self.root = repository, Path(root)

    def path(self, key):
        root = self.root.resolve()
        result = (root / key).resolve()
        if not result.is_relative_to(root):
            raise ValueError("Ruta de dataset inválida.")
        return result

    def upload(self, owner, farm_id, filename, content):
        filename = (filename or "").replace("\\", "/").split("/")[-1]
        if (
            not filename.lower().endswith(".csv")
            or len(filename) > 180
            or any(ord(c) < 32 for c in filename)
        ):
            raise ValueError(
                "Selecciona un archivo .csv con un nombre válido de hasta 180 caracteres."
            )
        rows = parse_csv(content)
        digest = hashlib.sha256(content).hexdigest()
        existing = self.repository.duplicate(owner, farm_id, digest)
        if existing:
            return existing, True
        dataset_id = uuid4()
        key = f"{owner}/{farm_id}/{dataset_id}.csv"
        target = self.path(key)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if shutil.disk_usage(target.parent).free < len(content) + 100 * 1024 * 1024:
            raise OSError("Espacio insuficiente para conservar el dataset local.")
        try:
            with target.open("xb") as handle:
                os.chmod(target, 0o600)
                handle.write(content)
            record = self.repository.store_dataset(
                owner,
                farm_id,
                {
                    "dataset_id": dataset_id,
                    "original_filename": filename,
                    "storage_key": key,
                    "sha256": digest,
                },
                rows,
            )
            return record, False
        except UniqueViolation:
            target.unlink(missing_ok=True)
            existing = self.repository.duplicate(owner, farm_id, digest)
            if existing:
                return existing, True
            raise
        except Exception:
            target.unlink(missing_ok=True)
            raise

    def bundle(self, owner, farm_id, cutoff: date):
        farm, raw_rows, raw_versions = self.repository.context_snapshot(owner, farm_id, cutoff)
        if farm is None:
            raise PermissionError("Finca no encontrada.")
        observations = [LocalObservation(**row) for row in raw_rows]
        keys = Counter((row.date, row.variable, row.crop) for row in observations)
        conflicts = sum(1 for count in keys.values() if count > 1)
        active_ids = {row.dataset_id for row in observations}
        versions = [
            FarmDataset(
                **{
                    key: record[key]
                    for key in (
                        "dataset_id",
                        "farm_id",
                        "original_filename",
                        "sha256",
                        "row_count",
                        "first_date",
                        "last_date",
                        "variables",
                        "created_at",
                    )
                }
            )
            for record in raw_versions
            if record["dataset_id"] in active_ids
        ]
        versions.sort(key=lambda record: str(record.dataset_id))
        identity = {
            "datasets": [version.model_dump(mode="json") for version in versions],
            "farm": Farm(**farm).model_dump(mode="json"),
            "cutoff": str(cutoff),
            "observations": [row.model_dump(mode="json") for row in observations],
        }
        digest = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        limitations = [
            "Los archivos superaron controles de formato y rangos básicos; sus mediciones no están verificadas.",
            "Las fechas locales de la finca deben alinearse con las fechas UTC y las resoluciones de NASA.",
            "La ficha de la finca describe su revisión actual; no reconstruye propiedades históricas.",
            "No hay modelos entrenados ni validación de una mejora de precisión con estos datos.",
        ]
        if conflicts:
            limitations.append(
                "Hay observaciones solapadas entre datasets; deben resolverse antes de entrenar o inferir."
            )
        context = FarmModelContext(
            farm=Farm(**farm),
            dataset_ids=sorted({row.dataset_id for row in observations}, key=str),
            dataset_versions=versions,
            observation_count=len(observations),
            available_through=max((row.date for row in observations), default=None),
            conflict_count=conflicts,
            snapshot_id=digest,
            limitations=limitations,
        )
        return FarmFeatureBundle(context=context, observations=observations)
