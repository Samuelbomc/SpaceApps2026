"""Repositorio de acceso a Landsat mediante HLSL30."""

from pipelines.ingestion.sources.nasa.hls import HLSClient

from ._satellite import SatelliteRepository


class LandsatRepository(SatelliteRepository):
    source = "landsat"
    client_class = HLSClient
