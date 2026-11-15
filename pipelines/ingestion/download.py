"""Descarga explícita y acotada de activos obtenidos del catálogo CMR."""

import fnmatch
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from .http import IngestionError, utc_now, write_json


def earthdata_session():
    # No hay prompts interactivos ni persistencia en ~/.netrc.
    if not (os.environ.get("EARTHDATA_TOKEN") or
            (os.environ.get("EARTHDATA_USERNAME") and os.environ.get("EARTHDATA_PASSWORD"))):
        raise IngestionError("Configura EARTHDATA_TOKEN o EARTHDATA_USERNAME/EARTHDATA_PASSWORD "
                             "en el entorno para descargar. No los agregues al repositorio.")
    try:
        import earthaccess
    except ImportError:
        raise IngestionError("Instala el extra de descarga: python -m pip install '.[download]'.") from None
    try:
        auth = earthaccess.login(strategy="environment", persist=False)
        if not auth.authenticated:
            raise IngestionError("Earthdata rechazó la autenticación.")
        return earthaccess.get_requests_https_session()
    except IngestionError:
        raise
    except Exception:
        raise IngestionError("No fue posible iniciar sesión en Earthdata; revisa credenciales y permisos DAAC.") from None


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class GranuleDownloader:
    def __init__(self, session=None):
        self.session = session

    def download(self, manifest: dict, directory: Path, *, patterns: tuple[str, ...] = (),
                 max_files: int = 3, max_bytes: int = 100 * 1024 * 1024) -> dict:
        if max_files < 1 or max_bytes < 1:
            raise ValueError("Los límites de archivos y bytes deben ser positivos.")
        assets = []
        for granule in manifest["granules"]:
            for url in granule["data_urls"]:
                name = unquote(urlparse(url).path.rsplit("/", 1)[-1])
                if patterns and not any(fnmatch.fnmatchcase(name, p) for p in patterns):
                    continue
                if url not in {a[1] for a in assets}:
                    assets.append((granule["id"], url, name))
        selected = assets[:max_files]
        if not selected:
            return {"files": [], "matching_assets": len(assets), "limit_reached": False}
        session = self.session if self.session is not None else earthdata_session()
        results, used = [], 0
        for granule_id, url, name in selected:
            if not name or name in (".", "..") or "/" in name or "\\" in name:
                raise IngestionError("Nombre de archivo remoto inválido.")
            # Evitar colisiones entre granules y permitir reanudar con checksum.
            asset_dir = directory / hashlib.sha256(granule_id.encode()).hexdigest()[:16]
            asset_dir.mkdir(parents=True, exist_ok=True)
            target, sidecar = asset_dir / name, asset_dir / f"{name}.metadata.json"
            if target.exists() and sidecar.exists():
                import json
                try:
                    previous = json.loads(sidecar.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    previous = {}
                if (previous.get("url") == url and previous.get("bytes") == target.stat().st_size
                        and previous.get("sha256") == file_digest(target)):
                    results.append({**previous, "cached": True})
                    continue
            temporary = None
            try:
                with session.get(url, stream=True, timeout=(15, 120)) as response:
                    if response.status_code != 200:
                        raise IngestionError(f"Descarga HTTP {response.status_code}; revisa permisos Earthdata/DAAC.")
                    content_type = response.headers.get("Content-Type", "").lower()
                    if "text/html" in content_type:
                        raise IngestionError("La descarga devolvió HTML (posible página de login).")
                    length = response.headers.get("Content-Length")
                    expected = int(length) if length and length.isdigit() else None
                    if expected is not None and expected > max_bytes - used:
                        raise IngestionError("El archivo excede el presupuesto de descarga. "
                                             "Selecciona capas con --asset o aumenta --max-mb.")
                    if shutil.disk_usage(asset_dir).free < (expected or 0) + 20 * 1024 * 1024:
                        raise IngestionError("Espacio insuficiente para descargar y conservar 20 MiB libres.")
                    digest, size = hashlib.sha256(), 0
                    with tempfile.NamedTemporaryFile(dir=asset_dir, suffix=".part", delete=False) as handle:
                        temporary = Path(handle.name)
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if used + size + len(chunk) > max_bytes:
                                raise IngestionError("Se alcanzó el límite de bytes; se elimina el archivo parcial.")
                            if shutil.disk_usage(asset_dir).free < len(chunk) + 20 * 1024 * 1024:
                                raise IngestionError("Espacio insuficiente; se elimina el archivo parcial.")
                            size += len(chunk)
                            digest.update(chunk)
                            handle.write(chunk)
                    if size == 0 or (expected is not None and size != expected):
                        raise IngestionError("Archivo vacío o incompleto; no se conservará.")
                    os.replace(temporary, target)
                    record = {"url": url, "granule_id": granule_id, "bytes": size,
                              "sha256": digest.hexdigest(), "path": str(target),
                              "retrieved_at": utc_now(), "product": manifest["product"],
                              "bbox_requested": manifest["bbox"],
                              "point_requested": manifest.get("point"),
                              "period_requested": manifest.get("period_requested"),
                              "subset_applied": False, "content_type": content_type}
                    write_json(sidecar, record)
                    results.append({**record, "cached": False})
                    used += size
            except (IngestionError, OSError):
                raise
            except Exception:
                raise IngestionError("La descarga falló; revisa conexión y autorización del proveedor.") from None
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return {"files": results, "matching_assets": len(assets),
                "limit_reached": len(assets) > max_files, "downloaded_bytes": used,
                "notes": "Archivos originales completos, sin recorte espacial o temporal. "
                         "Cada archivo completo conserva un sidecar para reanudar incluso tras un error."}
