"""Repositorio de acceso a GRACE/GRACE-FO."""

from pipelines.ingestion.sources.nasa.grace import GRACEClient

from ._satellite import SatelliteRepository


class GRACERepository(SatelliteRepository):
    source = "grace"
    client_class = GRACEClient
