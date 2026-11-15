"""Subconjuntos SMAP nativos: trabajo remoto durable, sin sondeo bloqueante."""

import hashlib
import json
from datetime import UTC, datetime
from math import ceil
from urllib.parse import urljoin, urlparse

from pipelines.ingestion.download import GranuleDownloader, earthdata_session
from pipelines.ingestion.http import IngestionError, retry_delay, write_json


class HarmonyPointClient:
    BASE = "https://harmony.earthdata.nasa.gov"

    def __init__(self, session=None, downloader=None):
        self.session, self.downloader = session, downloader

    def acquire(self, catalog, point, period, directory, *, max_bytes, now=None):
        now = now or datetime.now(UTC)
        session = self.session if self.session is not None else earthdata_session()
        state_path = directory / "harmony-job.json"
        try:
            state = json.loads(state_path.read_text()) if state_path.is_file() else {}
            if not isinstance(state, dict):
                state = {}
        except (OSError, ValueError):
            state = {}
        if not state.get("job_id"):
            fields = [
                f"/Soil_Moisture_Retrieval_Data_{part}/{field}{suffix}"
                for part, suffix in (("AM", ""), ("PM", "_pm"))
                for field in ("soil_moisture", "retrieval_qual_flag", "soil_moisture_error")
            ]
            params = [
                ("subset", f"lon({point.longitude - 0.12}:{point.longitude + 0.12})"),
                ("subset", f"lat({point.latitude - 0.12}:{point.latitude + 0.12})"),
                ("subset", f'time("{period.start}T00:00:00Z":"{period.end}T23:59:59Z")'),
                ("variable", ",".join(fields)),
                ("format", "application/x-netcdf4"),
                ("forceAsync", "true"),
                ("skipPreview", "true"),
                ("ignoreErrors", "false"),
                ("maxResults", "120"),
            ]
            # No reproyectar, interpolar ni cambiar la resolución del entrenamiento.
            url = f"{self.BASE}/{catalog['collection']['id']}/ogc-api-coverages/1.0.0/collections/parameter_vars/coverage/rangeset"
            response = self.get_json(session, url, params=params)
            if not isinstance(response.get("jobID"), str) or not response["jobID"]:
                raise IngestionError("Harmony no devolvió un identificador de trabajo válido.")
            state = {"job_id": response["jobID"]}
            write_json(state_path, state)
        try:
            status = self.get_json(session, f"{self.BASE}/jobs/{state['job_id']}")
        except IngestionError as exc:
            if exc.http_status in (404, 410):
                self.invalidate(state_path, state, "missing")
                raise IngestionError(
                    "El trabajo Harmony ya no está disponible; se solicitará otro.",
                    retry_after_seconds=300,
                ) from None
            raise
        if status.get("status") in ("failed", "canceled"):
            write_json(state_path, {"failed_job_id": state["job_id"]})
            raise IngestionError(
                "Harmony no completó el subconjunto SMAP.", retry_after_seconds=3600
            )
        if status.get("status") == "paused":
            self.get_json(session, f"{self.BASE}/jobs/{state['job_id']}/resume")
            return {"state": "subset_pending", "retry_after_seconds": 300}
        if status.get("status") == "successful" and status.get("dataExpiration"):
            try:
                expiration = datetime.fromisoformat(status["dataExpiration"].replace("Z", "+00:00"))
                if expiration.tzinfo is None:
                    raise ValueError
            except (ValueError, TypeError, AttributeError):
                raise IngestionError(
                    "Harmony devolvió una fecha de vencimiento incompatible."
                ) from None
            if expiration <= now:
                self.invalidate(state_path, state, "expired")
                raise IngestionError(
                    "Los resultados Harmony vencieron; se solicitará otro trabajo.",
                    retry_after_seconds=300,
                )
        if status.get("status") != "successful":
            return {"state": "subset_pending", "retry_after_seconds": 300}
        pending, visited, assets = [f"{self.BASE}/stac/{state['job_id']}"], set(), []
        while pending:
            url = pending.pop()
            if url in visited:
                continue
            if len(visited) >= 250 or not url.startswith(self.BASE + "/"):
                raise IngestionError("Catálogo Harmony fuera de límites.")
            visited.add(url)
            try:
                doc = self.get_json(session, url)
            except IngestionError as exc:
                if exc.http_status in (404, 410):
                    self.invalidate(state_path, state, "missing_results")
                raise
            pending.extend(
                urljoin(url, link["href"])
                for link in doc.get("links", [])
                if link.get("rel") in ("item", "child", "next")
            )
            for name, asset in doc.get("assets", {}).items():
                href = urljoin(url, asset["href"])
                if urlparse(href).scheme == "https" and urlparse(href).path.endswith(
                    (".nc4", ".nc")
                ):
                    identity = hashlib.sha256(
                        json.dumps(
                            [
                                state["job_id"],
                                doc.get("id", urlparse(url).path),
                                name,
                                urlparse(href).path,
                            ]
                        ).encode()
                    ).hexdigest()
                    assets.append({"id": identity, "asset_identity": identity, "data_urls": [href]})
            if len(assets) > 120:
                raise IngestionError("Harmony excede el límite de archivos de esta ventana.")
        if not assets:
            raise IngestionError("Harmony no devolvió datos NetCDF nativos.")
        if self.downloader is None:
            import requests

            # Las salidas firmadas no reciben las credenciales Earthdata.
            downloader = GranuleDownloader(session=requests.Session())
        else:
            downloader = self.downloader
        result = downloader.download(
            {**catalog, "granules": assets, "subset_applied": True},
            directory,
            patterns=("*.nc4", "*.nc"),
            max_files=120,
            max_bytes=max_bytes,
        )
        return {"state": "downloaded", "files": len(result["files"]), "subset_applied": True}

    @staticmethod
    def invalidate(path, state, reason):
        # Cambiar solo el puntero remoto: los archivos locales completos se conservan.
        write_json(path, {"previous_job_id": state["job_id"], "reason": reason})

    @staticmethod
    def get_json(session, url, **kwargs):
        try:
            response = session.get(url, timeout=(15, 60), **kwargs)
            if response.status_code not in (200, 201, 202):
                retry = response.headers.get("Retry-After", "")
                raise IngestionError(
                    "Harmony rechazó la petición; revisa acceso y disponibilidad.",
                    retry_after_seconds=ceil(retry_delay(retry) or 0),
                    http_status=response.status_code,
                )
            body = response.json()
            if not isinstance(body, dict):
                raise IngestionError("Harmony devolvió una respuesta JSON incompatible.")
            return body
        except IngestionError:
            raise
        except Exception:
            raise IngestionError(
                "Harmony no está disponible; se conserva el trabajo para reintentar."
            ) from None
