"""HTTP público con timeout, reintentos y caché JSON; nunca almacena credenciales."""

import hashlib
import json
import os
import random
import tempfile
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from http.client import IncompleteRead, RemoteDisconnected
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class IngestionError(RuntimeError):
    """Error operativo que puede mostrarse sin incluir secretos."""

    def __init__(self, message, *, retry_after_seconds=0):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def retry_delay(header: str, *, now=None) -> float | None:
    """Retry-After admite segundos o fecha HTTP; nunca espera valores negativos."""
    if header.isdigit():
        return float(header)
    try:
        due = parsedate_to_datetime(header)
        return max(0.0, (due - (now or datetime.now(UTC))).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return None


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class JsonHTTPClient:
    def __init__(
        self,
        cache_dir: Path | None = Path("data/cache"),
        *,
        timeout: float = 60,
        attempts: int = 3,
        cache_ttl: float = 86400,
        opener=urlopen,
        sleeper=time.sleep,
        jitter=random.uniform,
    ):
        if attempts < 1 or timeout <= 0 or cache_ttl < 0:
            raise ValueError("Timeout y reintentos deben ser positivos; TTL no negativo.")
        self.cache_dir = cache_dir
        self.timeout, self.attempts, self.cache_ttl = timeout, attempts, cache_ttl
        self.opener, self.sleeper, self.jitter = opener, sleeper, jitter

    def get(self, endpoint: str, params: dict) -> dict:
        url = endpoint + "?" + urlencode(sorted(params.items()), doseq=True)
        digest = hashlib.sha256(url.encode()).hexdigest()
        cache = self.cache_dir / f"{digest}.json" if self.cache_dir is not None else None
        if cache is not None and cache.exists():
            try:
                stored = json.loads(cache.read_text(encoding="utf-8"))
                if time.time() - stored["cached_at"] < self.cache_ttl:
                    return stored["payload"]
            except (ValueError, KeyError, TypeError):
                pass  # Una entrada dañada se reemplaza con una respuesta real.
        request = Request(url, headers={"User-Agent": "AgroGeo/0.1", "Accept": "application/json"})
        for attempt in range(self.attempts):
            try:
                with self.opener(request, timeout=self.timeout) as response:
                    payload = json.load(response)
                if not isinstance(payload, dict):
                    raise IngestionError("La API no devolvió un objeto JSON.")
                if cache is not None:
                    write_json(cache, {"cached_at": time.time(), "url": url, "payload": payload})
                return payload
            except HTTPError as exc:
                code = exc.code
                header = exc.headers.get("Retry-After", "") if exc.headers else ""
                server_delay = retry_delay(header)
                exc.close()
                if code not in (408, 429, 500, 502, 503, 504) or attempt == self.attempts - 1:
                    raise IngestionError(
                        f"HTTP {code} al consultar {endpoint}.",
                        retry_after_seconds=server_delay or 0,
                    ) from None
                # Esperas largas se delegan al scheduler persistente, sin bloquear el worker.
                if server_delay is not None and server_delay > 60:
                    raise IngestionError(
                        f"HTTP {code}: proveedor solicita reintentar después.",
                        retry_after_seconds=server_delay,
                    ) from None
                delay = server_delay if server_delay is not None else self._backoff(attempt)
            except (
                URLError,
                TimeoutError,
                ConnectionError,
                IncompleteRead,
                RemoteDisconnected,
            ) as exc:
                if attempt == self.attempts - 1:
                    raise IngestionError(
                        f"No fue posible conectar con {endpoint} ({type(exc).__name__})."
                    ) from None
                delay = self._backoff(attempt)
            except (ValueError, UnicodeError):
                if attempt == self.attempts - 1:
                    raise IngestionError(f"Respuesta JSON inválida de {endpoint}.") from None
                delay = self._backoff(attempt)
            self.sleeper(delay)
        raise AssertionError("Bucle de reintentos agotado")

    def _backoff(self, attempt):
        base = min(30.0, 2.0**attempt)
        return base + self.jitter(0, base * 0.25)
