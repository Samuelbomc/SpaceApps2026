"""Repositorio de acceso a GPM IMERG."""

from ._satellite import SatelliteRepository
from pipelines.ingestion.sources.nasa.gpm import GPMClient


class GPMRepository(SatelliteRepository):
    source = "gpm"
    client_class = GPMClient
