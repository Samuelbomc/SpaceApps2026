"""Descarga explícita y acotada de activos obtenidos del catálogo CMR."""

import fnmatch
import hashlib
import json
import os
import shutil
import tempfile
import time
from math import ceil, isfinite
from pathlib import Path
from urllib.parse import unquote, urlparse

from .http import IngestionError, retry_delay, utc_now, write_json


def earthdata_session():
    # No hay prompts interactivos ni persistencia en ~/.netrc.
    if not (
        os.environ.get("EARTHDATA_TOKEN")
        or (os.environ.get("EARTHDATA_USERNAME") and os.environ.get("EARTHDATA_PASSWORD"))
    ):
        raise IngestionError(
            "Configura EARTHDATA_TOKEN o EARTHDATA_USERNAME/EARTHDATA_PASSWORD "
            "en el entorno para descargar. No los agregues al repositorio."
        )
    try:
        import earthaccess
    except ImportError:
        raise IngestionError(
            "Instala el extra de descarga: python -m pip install '.[download]'."
        ) from None
    try:
        auth = earthaccess.login(strategy="environment", persist=False)
        if not auth.authenticated:
            raise IngestionError("Earthdata rechazó la autenticación.")
        return earthaccess.get_requests_https_session()
    except IngestionError:
        raise
    except Exception:
        raise IngestionError(
            "No fue posible iniciar sesión en Earthdata; revisa credenciales y permisos DAAC."
        ) from None


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class GranuleDownloader:
    def __init__(self, session=None, *, max_elapsed_seconds=300, clock=time.monotonic):
        self.session = session
        if not isfinite(max_elapsed_seconds) or max_elapsed_seconds <= 0:
            raise ValueError("El tiempo máximo de descarga debe ser finito y positivo.")
        self.max_elapsed_seconds, self.clock = max_elapsed_seconds, clock

    def download(
        self,
        manifest: dict,
        directory: Path,
        *,
        patterns: tuple[str, ...] = (),
        max_files: int = 3,
        max_bytes: int = 100 * 1024 * 1024,
    ) -> dict:
        if max_files < 1 or max_bytes < 1:
            raise ValueError("Los límites de archivos y bytes deben ser positivos.")
        product_identity = json.loads(json.dumps(manifest["product"]))
        assets = []
        for granule in manifest["granules"]:
            for url in granule["data_urls"]:
                name = unquote(urlparse(url).path.rsplit("/", 1)[-1])
                if patterns and not any(fnmatch.fnmatchcase(name, p) for p in patterns):
                    continue
                if url not in {a[1] for a in assets}:
                    assets.append((granule["id"], url, name, granule.get("asset_identity")))
        selected = assets[:max_files]
        if not selected:
            return {"files": [], "matching_assets": len(assets), "limit_reached": False}
        deadline = self.clock() + self.max_elapsed_seconds
        results, used = [], 0

        def check_deadline():
            if self.clock() >= deadline:
                error = IngestionError(
                    "Se agotó el tiempo de descarga; se conservarán los archivos completos para reintentar."
                )
                error.downloaded_bytes = used
                raise error

        session = self.session if self.session is not None else earthdata_session()
        for granule_id, url, name, identity in selected:
            check_deadline()
            if not name or name in (".", "..") or "/" in name or "\\" in name:
                raise IngestionError("Nombre de archivo remoto inválido.")
            # Evitar colisiones entre granules y permitir reanudar con checksum.
            asset_dir = directory / hashlib.sha256(granule_id.encode()).hexdigest()[:16]
            asset_dir.mkdir(parents=True, exist_ok=True)
            target, sidecar = asset_dir / name, asset_dir / f"{name}.metadata.json"
            if target.exists() and sidecar.exists():
                try:
                    previous = json.loads(sidecar.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    previous = {}
                if not isinstance(previous, dict):
                    previous = {}
                if (
                    (
                        previous.get("url") == url
                        or (identity is not None and previous.get("asset_identity") == identity)
                    )
                    and previous.get("product") == product_identity
                    and previous.get("bytes") == target.stat().st_size
                    and previous.get("sha256") == file_digest(target)
                ):
                    results.append({**previous, "cached": True})
                    continue
            temporary = None
            try:
                with session.get(url, stream=True, timeout=(15, 120)) as response:
                    check_deadline()
                    if response.status_code != 200:
                        raise IngestionError(
                            f"Descarga HTTP {response.status_code}; revisa permisos Earthdata/DAAC.",
                            retry_after_seconds=ceil(
                                retry_delay(response.headers.get("Retry-After", "")) or 0
                            ),
                            http_status=response.status_code,
                        )
                    content_type = response.headers.get("Content-Type", "").lower()
                    if "text/html" in content_type:
                        raise IngestionError("La descarga devolvió HTML (posible página de login).")
                    length = response.headers.get("Content-Length")
                    expected = int(length) if length and length.isdigit() else None
                    if expected is not None and expected > max_bytes - used:
                        raise IngestionError(
                            "El archivo excede el presupuesto de descarga. "
                            "Selecciona capas con --asset o aumenta --max-mb."
                        )
                    if shutil.disk_usage(asset_dir).free < (expected or 0) + 20 * 1024 * 1024:
                        raise IngestionError(
                            "Espacio insuficiente para descargar y conservar 20 MiB libres."
                        )
                    digest, size = hashlib.sha256(), 0
                    with tempfile.NamedTemporaryFile(
                        dir=asset_dir, suffix=".part", delete=False
                    ) as handle:
                        temporary = Path(handle.name)
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            check_deadline()
                            if used + size + len(chunk) > max_bytes:
                                raise IngestionError(
                                    "Se alcanzó el límite de bytes; se elimina el archivo parcial."
                                )
                            if shutil.disk_usage(asset_dir).free < len(chunk) + 20 * 1024 * 1024:
                                raise IngestionError(
                                    "Espacio insuficiente; se elimina el archivo parcial."
                                )
                            size += len(chunk)
                            digest.update(chunk)
                            handle.write(chunk)
                    if size == 0 or (expected is not None and size != expected):
                        raise IngestionError("Archivo vacío o incompleto; no se conservará.")
                    os.replace(temporary, target)
                    record = {
                        "url": url,
                        "granule_id": granule_id,
                        "asset_identity": identity,
                        "bytes": size,
                        "sha256": digest.hexdigest(),
                        "path": str(target),
                        "retrieved_at": utc_now(),
                        "product": manifest["product"],
                        "bbox_requested": manifest["bbox"],
                        "point_requested": manifest.get("point"),
                        "period_requested": manifest.get("period_requested"),
                        "subset_applied": manifest.get("subset_applied", False),
                        "content_type": content_type,
                    }
                    write_json(sidecar, record)
                    results.append({**record, "cached": False})
                    used += size
            except IngestionError as exc:
                exc.downloaded_bytes = used
                raise
            except OSError:
                raise
            except Exception:
                error = IngestionError(
                    "La descarga falló; revisa conexión y autorización del proveedor."
                )
                error.downloaded_bytes = used
                raise error from None
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return {
            "files": results,
            "matching_assets": len(assets),
            "limit_reached": len(assets) > max_files,
            "downloaded_bytes": used,
            "notes": "Archivos completos del catálogo; subset_applied identifica recortes remotos. "
            "Cada archivo completo conserva un sidecar para reanudar incluso tras un error.",
        }
