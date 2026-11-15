"""Repositorio de acceso a SMAP."""

from pipelines.ingestion.sources.nasa.smap import SMAPClient

from ._satellite import SatelliteRepository


class SMAPRepository(SatelliteRepository):
    source = "smap"
    client_class = SMAPClient
