"""Lectura validada del catálogo; no depende de FastAPI ni de MongoDB."""

from importlib.resources import files

from packages.contracts.agronomy import CropCatalog


def load_crop_catalog():
    return CropCatalog.model_validate_json(
        files("ml.configs").joinpath("ecocrop.catalog.json").read_text(encoding="utf-8")
    )
