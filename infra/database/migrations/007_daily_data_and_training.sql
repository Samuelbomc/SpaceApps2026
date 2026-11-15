-- La clave nasa-weekly conserva la identidad del calendario y su historial.
-- Cambiar la cadencia no descarta progreso, errores, fuentes pendientes ni backoff.
UPDATE job_schedules
SET interval_seconds = 86400,
    next_run_at = LEAST(
        next_run_at,
        COALESCE(last_success_at + INTERVAL '1 day', now())
    )
WHERE job_key IN ('nasa-weekly', 'model-training')
  AND interval_seconds <> 86400;
