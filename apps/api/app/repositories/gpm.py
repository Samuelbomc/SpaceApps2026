"""Repositorio de acceso a GPM IMERG."""

from pipelines.ingestion.sources.nasa.gpm import GPMClient

from ._satellite import SatelliteRepository


class GPMRepository(SatelliteRepository):
    source = "gpm"
    client_class = GPMClient
