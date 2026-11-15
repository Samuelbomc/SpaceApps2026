"""Recepción de variables diarias; no usa etiquetas ni infiere datos faltantes."""

import csv
import hashlib
import math
from datetime import date, timedelta
from pathlib import Path

from packages.contracts.pretrained import DailyFeatures


def daily_snapshot_from_csv(
    path, *, region_id, point_id, issue_date, climate_features, soil_features, **_
):
    path = Path(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    found = None
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        metadata = {
            "point_id",
            "issue_date",
            "observation_cutoff",
            "radiation_observation_cutoff",
            "latitude",
            "longitude",
        }
        required = metadata | set(climate_features)
        if len(columns) != len(set(columns)) or not required <= set(columns):
            raise ValueError(
                "Columnas duplicadas o faltantes: " + ", ".join(sorted(required - set(columns)))
            )
        soil_present = bool((set(soil_features) - set(climate_features)) & set(columns))
        if soil_present and not set(soil_features) <= set(columns):
            raise ValueError(
                "Entradas de suelo incompletas: "
                + ", ".join(sorted(set(soil_features) - set(columns)))
            )
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("La fila no coincide con las columnas del CSV.")
            if row["point_id"] != point_id or row["issue_date"] != issue_date.isoformat():
                continue
            if row.get("lead_days"):
                lead = float(row["lead_days"])
                if not math.isfinite(lead) or not lead.is_integer() or not 1 <= lead <= 60:
                    raise ValueError("lead_days debe ser un entero entre 1 y 60.")
                if row.get("target_date") and date.fromisoformat(
                    row["target_date"]
                ) != issue_date + timedelta(days=int(lead)):
                    raise ValueError("target_date debe coincidir con issue_date + lead_days.")
            if (
                row.get("features_available_on")
                and date.fromisoformat(row["features_available_on"]) > issue_date
            ):
                raise ValueError("Las entradas no estaban disponibles en la emisión declarada.")
            candidate = DailyFeatures(
                region_id=region_id,
                point_id=point_id,
                issue_date=issue_date,
                observation_cutoff=row["observation_cutoff"],
                radiation_observation_cutoff=row["radiation_observation_cutoff"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                source_sha256=before,
                climate={key: float(row[key]) for key in climate_features},
                soil={key: float(row[key]) for key in soil_features} if soil_present else None,
            )
            if found is not None and candidate != found:
                raise ValueError("Hay entradas contradictorias para la misma celda y emisión.")
            found = candidate
    if found is None:
        raise ValueError("No hay datos para esa celda y fecha exactas; no se utiliza otra fecha.")
    if before != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError("El archivo cambió durante la recepción.")
    return found
