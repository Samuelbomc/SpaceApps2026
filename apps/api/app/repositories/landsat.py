"""Repositorio de acceso a Landsat mediante HLSL30."""

from ._satellite import SatelliteRepository
from pipelines.ingestion.sources.nasa.hls import HLSClient


class LandsatRepository(SatelliteRepository):
    source = "landsat"
    client_class = HLSClient
