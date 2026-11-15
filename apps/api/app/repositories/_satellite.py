"""Acceso común a productos NASA: sin reglas agrícolas ni preparación de ML."""

from packages.contracts import DataQuery, SourceResult
from pipelines.ingestion.sources.nasa._base import CMRSourceClient

from ._response import source_result


class SatelliteRepository:
    """Reutiliza el cliente CMR; cada repositorio concreto fija su fuente."""

    source: str
    client_class: type[CMRSourceClient]

    def __init__(self, client: CMRSourceClient | None = None):
        self.client = client if client is not None else self.client_class()

    def collection(self) -> dict:
        return self.client.collection()

    def fetch(self, query: DataQuery) -> SourceResult:
        """Devuelve el catálogo con metadatos originales y enlaces de acceso."""
        payload = self.client.search(query)
        return source_result(self.source, query, payload)
