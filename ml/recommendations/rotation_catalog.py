"""Cultivos rotables del CSV público; no interpreta parámetros ESTIMADO como umbrales."""

import csv
import hashlib
import io
from importlib.resources import files
from pathlib import Path


def load_rotation_traits(path=None):
    content = (
        Path(path).read_bytes()
        if path is not None
        else files("modulo_rotacion").joinpath("datos/cultivos.csv").read_bytes()
    )
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    required = {"CULTIVO", "CADENA_UPRA", "ESPECIE_ECOCROP", "FAMILIA", "TIPO"}
    if (
        not reader.fieldnames
        or not required <= set(reader.fieldnames)
        or len(reader.fieldnames) != len(set(reader.fieldnames))
    ):
        raise ValueError("El catálogo de rotación tiene columnas faltantes o duplicadas.")
    traits, identifiers = [], set()
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Una fila del catálogo de rotación está incompleta.")
        identifier = row["CULTIVO"].strip()
        if not identifier or identifier in identifiers:
            raise ValueError("Los identificadores de cultivo deben ser únicos y no vacíos.")
        identifiers.add(identifier)
        if row["TIPO"] == "cobertura":
            continue
        if row["TIPO"] not in ("ingreso", "restaura") or not all(
            row[key].strip() for key in required
        ):
            raise ValueError("Faltan identidad, especie o familia para evaluar el cultivo.")
        traits.append(
            {
                "legacy_id": identifier,
                "chain": row["CADENA_UPRA"].strip(),
                "scientific_name": row["ESPECIE_ECOCROP"].strip(),
                "family": row["FAMILIA"].strip(),
            }
        )
    if not traits:
        raise ValueError("El catálogo no contiene cultivos evaluables.")
    return {
        "source": "modulo_rotacion/datos/cultivos.csv",
        "source_sha256": hashlib.sha256(content).hexdigest(),
        "traits": traits,
    }
