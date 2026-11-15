"""Catálogo público de requisitos; consulta sin ejecutar modelos ni recomendar siembras."""

from fastapi import APIRouter

from ml.recommendations.catalog import load_crop_catalog
from packages.contracts.agronomy import CropCatalog

router = APIRouter(prefix="/api/v1/crops", tags=["Agronomic catalog"])


@router.get("/catalog", response_model=CropCatalog)
def catalog():
    return load_crop_catalog()
