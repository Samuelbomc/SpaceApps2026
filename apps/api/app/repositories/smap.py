"""Repositorio de acceso a SMAP."""

from ._satellite import SatelliteRepository
from pipelines.ingestion.sources.nasa.smap import SMAPClient


class SMAPRepository(SatelliteRepository):
    source = "smap"
    client_class = SMAPClient
