"""Repositorio de acceso a SRTM; su consulta es estática."""

from ._satellite import SatelliteRepository
from pipelines.ingestion.sources.nasa.srtm import SRTMClient


class SRTMRepository(SatelliteRepository):
    source = "srtm"
    client_class = SRTMClient
