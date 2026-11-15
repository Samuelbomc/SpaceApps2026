"""Adquisición puntual de productos fijados por daily-direct-1-60-v1."""

import hashlib
import json
import math
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from packages.contracts.models import DateRange, GeoPoint
from pipelines.ingestion.date_fallback import fetch_with_date_fallback
from pipelines.ingestion.download import GranuleDownloader, file_digest
from pipelines.ingestion.http import IngestionError, JsonHTTPClient, write_json
from pipelines.ingestion.recovery import SourceRecovery
from pipelines.ingestion.sources.nasa._cmr import CMRClient
from pipelines.ingestion.sources.nasa.catalog import PRODUCTS
from pipelines.ingestion.sources.nasa.harmony_point import HarmonyPointClient
from pipelines.ingestion.sources.nasa.power import PowerClient

POWER_FIELDS = ("T2M", "T2M_MIN", "T2M_MAX", "RH2M", "QV2M", "WS2M", "ALLSKY_SFC_SW_DWN")
MODEL_PRODUCTS = {
    "GPM": replace(PRODUCTS["gpm"], short_name="GPM_3IMERGDL", notes="IMERG Late diario."),
    "SMAP": replace(
        PRODUCTS["smap"],
        short_name="SPL3SMP_E",
        version="006",
        cadence="daily",
        variables=("soil_moisture", "retrieval_qual_flag", "soil_moisture_error"),
        documentation="https://nsidc.org/data/spl3smp_e/versions/6",
        notes="L3 enhanced AM/PM; no sustituir por L4.",
    ),
}


class ModelPointSources:
    def __init__(
        self,
        root,
        *,
        power=None,
        cmr=None,
        downloader=None,
        harmony=None,
        max_bytes=128 * 1024**2,
        max_lag_days=5,
    ):
        self.root = Path(root)
        self.power = power if power is not None else PowerClient(JsonHTTPClient(cache_ttl=900))
        self.cmr = cmr if cmr is not None else CMRClient(JsonHTTPClient(cache_ttl=900))
        self.downloader = downloader if downloader is not None else GranuleDownloader()
        self.harmony = harmony if harmony is not None else HarmonyPointClient()
        if max_bytes < 1:
            raise ValueError("El presupuesto de descarga debe ser positivo.")
        self.max_bytes = max_bytes
        if type(max_lag_days) is not int or not 1 <= max_lag_days <= 30:
            raise ValueError("El margen máximo de consulta debe estar entre 1 y 30 días.")
        self.max_lag_days = max_lag_days

    def acquire(self, region, issue_date, directory, *, now=None):
        fixed_now = now
        now = now or datetime.now(UTC)
        point = GeoPoint(latitude=region["latitude"], longitude=region["longitude"])
        period = DateRange(issue_date - timedelta(days=60), issue_date - timedelta(days=2))
        context = hashlib.sha256(
            json.dumps(
                {
                    "point": point.as_dict(),
                    "period": period.as_dict(),
                    "recipe": "daily-direct-1-60-v1",
                    "products": {name: item.as_dict() for name, item in MODEL_PRODUCTS.items()},
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        recovery = SourceRecovery(
            directory / "source-recovery.json",
            context,
            now,
            clock=(lambda: datetime.now(UTC)) if fixed_now is None else None,
        )
        status, payload = {}, None
        cached = directory / "power.json"
        try:
            if cached.is_file() and file_digest(cached) == recovery.entry("POWER").get("sha256"):
                payload = json.loads(cached.read_text())
        except (OSError, ValueError):
            payload = None
        if recovery.due("POWER") or (
            payload is None
            and recovery.entry("POWER").get("status", {}).get("state") == "downloaded"
        ):
            try:
                fresh, used_period, attempts = fetch_with_date_fallback(
                    lambda selected: self.power.fetch_point_daily(
                        selected, point, POWER_FIELDS, time_standard="LST"
                    ),
                    period,
                    issue_date + timedelta(days=1),
                    usable=self.has_weather,
                    max_lag_days=self.max_lag_days,
                )
                if not self.has_weather(fresh):
                    raise IngestionError(
                        "POWER no devolvió meteorología en las fechas consultadas.",
                        retry_after_seconds=3600,
                    )
                write_json(cached, fresh)
                payload = fresh
                status["POWER"] = recovery.record(
                    "POWER",
                    {
                        "state": "downloaded",
                        "time_standard": "LST",
                        "query_end": used_period.end.isoformat(),
                        "attempted_end_dates": attempts,
                    },
                    sha256=file_digest(cached),
                )
            except IngestionError as exc:
                status["POWER"] = recovery.record("POWER", self.failure(exc))
                if payload is not None:
                    status["POWER"]["cached"] = True
        else:
            status["POWER"] = recovery.status("POWER")
            status["POWER"]["cached"] = payload is not None
        remaining = self.max_bytes
        authenticated = bool(
            os.getenv("EARTHDATA_TOKEN")
            or (os.getenv("EARTHDATA_USERNAME") and os.getenv("EARTHDATA_PASSWORD"))
        )
        for folder, product in MODEL_PRODUCTS.items():
            if not recovery.due(folder, access_configured=authenticated):
                status[folder] = recovery.status(folder)
                continue
            try:
                catalog, source_period, attempts = fetch_with_date_fallback(
                    lambda selected: self.cmr.search_product(
                        product, selected, point=point, limit=120
                    ),
                    period,
                    issue_date + timedelta(days=1),
                    usable=lambda body: bool(body["granules"]),
                    max_lag_days=self.max_lag_days,
                )
                write_json(directory / f"{folder.lower()}-catalog.json", catalog)
                if catalog["limit_reached"]:
                    raise IngestionError(
                        "El catálogo está truncado; no se prepara una entrada parcial."
                    )
                if not catalog["granules"]:
                    raise IngestionError(
                        "No hay archivos disponibles en las fechas consultadas.",
                        retry_after_seconds=3600,
                    )
                if not authenticated:
                    status[folder] = recovery.record(
                        folder,
                        {
                            "state": "requires_earthdata",
                            "granules": len(catalog["granules"]),
                            "query_end": source_period.end.isoformat(),
                            "attempted_end_dates": attempts,
                        },
                    )
                    continue
                if folder == "SMAP":
                    if remaining <= 0:
                        raise IngestionError("Presupuesto de descarga agotado en este intento.")
                    status[folder] = recovery.record(
                        folder,
                        {
                            **self.harmony.acquire(
                                catalog,
                                point,
                                source_period,
                                directory / "SMAP" / source_period.end.isoformat(),
                                max_bytes=remaining,
                            ),
                            "query_end": source_period.end.isoformat(),
                            "attempted_end_dates": attempts,
                        },
                    )
                    continue
                result = self.downloader.download(
                    catalog,
                    self.root / folder,
                    patterns=("*.nc4", "*.h5"),
                    max_files=120,
                    max_bytes=remaining,
                )
                remaining -= result.get("downloaded_bytes", 0)
                status[folder] = recovery.record(
                    folder,
                    {
                        "state": "downloaded",
                        "files": len(result["files"]),
                        "query_end": source_period.end.isoformat(),
                        "attempted_end_dates": attempts,
                    },
                )
            except IngestionError as exc:
                remaining -= getattr(exc, "downloaded_bytes", 0)
                status[folder] = recovery.record(folder, self.failure(exc))
        return payload, status

    @staticmethod
    def has_weather(payload):
        try:
            response = payload["raw_responses"][0]["response"]
            parameters = response["properties"]["parameter"]
            fill = response["header"].get("fill_value", -999)
            return any(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                and value != fill
                for field in POWER_FIELDS
                for value in parameters.get(field, {}).values()
            )
        except (KeyError, TypeError, AttributeError):
            return False

    @staticmethod
    def failure(exc):
        return {
            "state": "unavailable",
            "reason": str(exc),
            "retry_after_seconds": getattr(exc, "retry_after_seconds", 0),
        }
