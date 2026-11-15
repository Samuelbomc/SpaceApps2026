"""Retroceso acotado del final consultado; conserva las fechas reales del proveedor."""

from datetime import timedelta

from packages.contracts.models import DateRange
from pipelines.ingestion.http import IngestionError


def fetch_with_date_fallback(fetch, period, reference_date, *, usable, max_lag_days=5):
    if type(max_lag_days) is not int or not 1 <= max_lag_days <= 30:
        raise ValueError("El margen máximo de consulta debe estar entre 1 y 30 días.")
    oldest = max(period.start, min(period.end, reference_date - timedelta(days=max_lag_days)))
    attempted, latest, last_error = [], None, None
    candidate = period
    while True:
        attempted.append(candidate.end.isoformat())
        try:
            result = fetch(candidate)
            latest = (result, candidate)
            if usable(result):
                return result, candidate, attempted
        except IngestionError as exc:
            # Cambiar la fecha no permite eludir autenticación, cuotas o caídas.
            if exc.http_status not in (400, 422) or exc.retry_after_seconds:
                raise
            last_error = exc
        if candidate.end <= oldest:
            break
        candidate = DateRange(period.start, candidate.end - timedelta(days=1))
    if latest is not None:
        return *latest, attempted
    raise last_error
