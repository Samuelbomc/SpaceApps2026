-- Estado de recuperación durable; no modifica las migraciones ya aplicadas.
ALTER TABLE job_schedules
    ADD COLUMN consecutive_failures integer NOT NULL DEFAULT 0 CHECK (consecutive_failures >= 0),
    ADD COLUMN pending_sources jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(pending_sources) = 'array');
