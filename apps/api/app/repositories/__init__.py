"""Repositorios de acceso externo; independientes del futuro dominio y de ML."""

from .ecostress import ECOSTRESSRepository
from .gpm import GPMRepository
from .grace import GRACERepository
from .landsat import LandsatRepository
from .power import PowerRepository
from .smap import SMAPRepository
from .srtm import SRTMRepository

__all__ = [
    "PowerRepository",
    "GPMRepository",
    "SMAPRepository",
    "SRTMRepository",
    "GRACERepository",
    "ECOSTRESSRepository",
    "LandsatRepository",
]
