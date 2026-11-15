"""Normaliza la tabla TSV aportada: comas decimales, unidades y faltantes explícitos."""

import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import Counter

from packages.contracts.agronomy import (
    CropCatalog,
    CropProfile,
    EcologicalRequirement,
    NumericRange,
    QualitativeRequirement,
)

MISSING = {"", "-", "---", "no input", "sin dato"}
LIMITATIONS = [
    "El catálogo describe requisitos generales de especies; requiere validación local y de variedad antes de recomendar siembras.",
    "La precipitación es anual: no se compara con acumulados de 7/15/30/60 días ni se anualizan esos pronósticos.",
    "Un total anual no caracteriza la distribución estacional de la lluvia, el balance hídrico ni el aporte del riego.",
    "Las latitudes originales carecen de hemisferio explícito; no se usan como filtro geográfico.",
    "Textura, drenaje, profundidad, fertilidad, salinidad, luz, Köppen y fotoperiodo se conservan sin convertirlos en umbrales inventados.",
    "No hay reglas de familias, sucesión, plagas o descansos suficientes para evaluar rotaciones.",
]


def number(value, *, optional=False):
    text = value.strip()
    if text.casefold() in MISSING:
        if optional:
            return None
        raise ValueError("Falta un requisito numérico obligatorio.")
    if not re.fullmatch(r"-?\d+(?:[.,]\d+)?", text):
        raise ValueError(f"Valor numérico inválido: {text!r}")
    return float(text.replace(",", "."))


def slug(value):
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def normalize_crop_catalog(content: bytes) -> CropCatalog:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), delimiter="\t")
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError("La tabla requiere una cabecera TSV con nombres únicos.")
    rows = list(reader)
    if not rows:
        raise ValueError("El catálogo está vacío.")
    counts = Counter(row.get("Codigo_ECOCROP") for row in rows)
    crops = []
    for line, row in enumerate(rows, start=2):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"La fila {line} no coincide con las columnas de la cabecera.")
        try:

            def requirement(prefix, suffix, unit):
                return EcologicalRequirement(
                    optimal=NumericRange(
                        minimum=number(row[f"{prefix}_Optima_Min_{suffix}"]),
                        maximum=number(row[f"{prefix}_Optima_Max_{suffix}"]),
                    ),
                    absolute=NumericRange(
                        minimum=number(row[f"{prefix}_Absoluta_Min_{suffix}"]),
                        maximum=number(row[f"{prefix}_Absoluta_Max_{suffix}"]),
                    ),
                    unit=unit,
                )

            ph = EcologicalRequirement(
                optimal=NumericRange(
                    minimum=number(row["pH_Optimo_Min"]), maximum=number(row["pH_Optimo_Max"])
                ),
                absolute=NumericRange(
                    minimum=number(row["pH_Absoluto_Min"]), maximum=number(row["pH_Absoluto_Max"])
                ),
                unit="pH",
            )
            soil = {}
            for dimension in ("Profundidad", "Textura", "Fertilidad", "Salinidad", "Drenaje"):
                key = next(key for key in row if key.startswith(f"Suelo_{dimension}"))
                parts = row[key].split(" / ", 1)
                if len(parts) != 2:
                    raise ValueError(f"Se requieren valores óptimo / absoluto en {key}.")
                soil[dimension.lower()] = QualitativeRequirement(
                    **{
                        name: None if value.strip().casefold() in MISSING else value.strip()
                        for name, value in zip(("optimal", "absolute"), parts)
                    }
                )
            code = int(row["Codigo_ECOCROP"])
            flags = ["latitude_hemispheres_unresolved", "regional_agronomic_validation_pending"]
            if counts[row["Codigo_ECOCROP"]] > 1:
                flags.append("shared_species_requirements_not_variety_specific")
            altitude = number(row["Altitud_Absoluta_Max_(msnm)"], optional=True)
            if altitude is None:
                flags.append("altitude_max_missing")
            crops.append(
                CropProfile(
                    crop_id=f"{code}-{slug(row['Cadena'] + '-' + row['Cultivo'])}",
                    chain=row["Cadena"],
                    crop_name=row["Cultivo"],
                    scientific_name=row["Especie_ECOCROP"],
                    ecocrop_code=code,
                    source_url=row["Fuente"],
                    temperature=requirement("Temp", "(°C)", "C"),
                    annual_rainfall=requirement("Precipitacion", "(mm/año)", "mm/year"),
                    soil_ph=ph,
                    altitude_max_m=altitude,
                    cycle_days=NumericRange(
                        minimum=number(row["Ciclo_Cultivo_Min_(dias)"]),
                        maximum=number(row["Ciclo_Cultivo_Max_(dias)"]),
                    ),
                    lethal_temperature_rest_c=number(
                        row["Temp_Letal_en_Reposo_(°C)"], optional=True
                    ),
                    lethal_temperature_early_growth_c=number(
                        row["Temp_Letal_Crecimiento_Temprano_(°C)"], optional=True
                    ),
                    qualitative_soil=soil,
                    source_attributes=row,
                    quality_flags=flags,
                )
            )
        except (KeyError, StopIteration, ValueError) as exc:
            raise ValueError(f"Fila {line}: {exc}") from None
    digest = hashlib.sha256(content).hexdigest()
    normalized = {
        "schema_version": "ecocrop_catalog_v1",
        "normalizer_version": "ecocrop_tsv_v1",
        "source_sha256": digest,
        "crops": [crop.model_dump(mode="json") for crop in crops],
        "limitations": LIMITATIONS,
    }
    identity = hashlib.sha256(
        json.dumps(normalized, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()
    return CropCatalog(
        version=f"ecocrop-v1-{identity[:16]}",
        source_sha256=digest,
        crops=crops,
        limitations=LIMITATIONS,
    )
