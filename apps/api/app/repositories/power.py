"""Repositorio de acceso a NASA POWER."""

from packages.contracts import DataQuery, SourceResult
from pipelines.ingestion.sources.nasa.power import PowerClient

from ._response import source_result


class PowerRepository:
    def __init__(self, client: PowerClient | None = None):
        self.client = client if client is not None else PowerClient()

    def fetch(self, query: DataQuery) -> SourceResult:
        """Respuesta original: no selecciona features ni interpreta valores."""
        if query.period is None:
            raise ValueError("POWER requiere un intervalo de fechas.")
        if query.point is not None:
            payload = self.client.fetch_point_daily(
                query.period, query.point, query.power_parameters
            )
        else:
            payload = self.client.fetch_daily(query.period, query.bbox, query.power_parameters)
        return source_result("power", query, payload)
