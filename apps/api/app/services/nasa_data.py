"""Coordina la misma consulta entre fuentes, conservando éxitos parciales."""

from pipelines.ingestion.sources.nasa._cmr import CMRClient
from pipelines.ingestion.http import IngestionError, JsonHTTPClient, utc_now
from pipelines.ingestion.sources.nasa.power import PowerClient

from packages.contracts import DataQuery, DataRepository
from apps.api.app.repositories._response import source_result
from apps.api.app.repositories import (
    ECOSTRESSRepository, GPMRepository, GRACERepository, LandsatRepository,
    PowerRepository, SMAPRepository, SRTMRepository,
)
from pipelines.ingestion.sources.nasa.gpm import GPMClient
from pipelines.ingestion.sources.nasa.smap import SMAPClient
from pipelines.ingestion.sources.nasa.srtm import SRTMClient
from pipelines.ingestion.sources.nasa.grace import GRACEClient
from pipelines.ingestion.sources.nasa.ecostress import ECOSTRESSClient
from pipelines.ingestion.sources.nasa.hls import HLSClient


class NASADataService:
    def __init__(self, http: JsonHTTPClient | None = None,
                 repositories: dict[str, DataRepository] | None = None):
        if repositories is not None:
            self.repositories = dict(repositories)
            return
        http = http if http is not None else JsonHTTPClient()
        cmr = CMRClient(http)
        self.repositories = {
            "power": PowerRepository(PowerClient(http)), "gpm": GPMRepository(GPMClient(cmr)),
            "smap": SMAPRepository(SMAPClient(cmr)), "srtm": SRTMRepository(SRTMClient(cmr)),
            "grace": GRACERepository(GRACEClient(cmr)),
            "ecostress": ECOSTRESSRepository(ECOSTRESSClient(cmr)),
            "ecostress-lst": ECOSTRESSRepository(ECOSTRESSClient(cmr, product="lst")),
            "landsat": LandsatRepository(HLSClient(cmr)),
        }

    def fetch(self, query: DataQuery, *, sources: tuple[str, ...] | None = None) -> dict:
        selected = tuple(dict.fromkeys(sources)) if sources is not None else tuple(self.repositories)
        if not selected or any(source not in self.repositories for source in selected):
            raise ValueError("Selecciona fuentes existentes y al menos una fuente.")
        if query.period is None and any(source != "srtm" for source in selected):
            raise ValueError("Se requieren fechas para consultar las fuentes temporales.")
        results = {}
        for source in selected:
            try:
                results[source] = self.repositories[source].fetch(query)
            except IngestionError as exc:
                results[source] = source_result(source, query, None, error=str(exc))
                results[source]["metadata"]["retry_after_seconds"] = exc.retry_after_seconds
        errors = sum(item["status"] == "error" for item in results.values())
        return {"schema_version": 1, "query_id": query.query_id, "requested": query.as_dict(),
                "completed_at": utc_now(), "status": "error" if errors == len(results) else
                "partial" if errors else "ok", "sources": results,
                "notes": "Misma ubicación y periodo de solicitud; resoluciones y coberturas nativas "
                         "conservadas. No hay alineación de píxeles/fechas ni dataset para ML."}
