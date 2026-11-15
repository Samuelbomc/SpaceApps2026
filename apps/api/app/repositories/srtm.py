"""Repositorio de acceso a SRTM; su consulta es estática."""

from pipelines.ingestion.sources.nasa.srtm import SRTMClient

from ._satellite import SatelliteRepository


class SRTMRepository(SatelliteRepository):
    source = "srtm"
    client_class = SRTMClient
