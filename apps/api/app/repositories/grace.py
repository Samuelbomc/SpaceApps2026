"""Repositorio de acceso a GRACE/GRACE-FO."""

from ._satellite import SatelliteRepository
from pipelines.ingestion.sources.nasa.grace import GRACEClient


class GRACERepository(SatelliteRepository):
    source = "grace"
    client_class = GRACEClient
