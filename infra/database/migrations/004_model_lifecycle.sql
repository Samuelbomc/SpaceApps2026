-- PostgreSQL conserva identidad, fincas, observaciones y programación durable.
-- ml_records es el adapter local compatible cuando RESULTS_BACKEND=postgresql.
CREATE TABLE IF NOT EXISTS ml_records (
    kind text NOT NULL,
    record_key text NOT NULL,
    body jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (kind,record_key)
);

ALTER TABLE job_schedules ADD COLUMN IF NOT EXISTS last_result jsonb NOT NULL DEFAULT '{}';

INSERT INTO job_schedules(job_key,interval_seconds)
VALUES ('model-training',86400), ('crop-recommendations',3600)
ON CONFLICT(job_key) DO NOTHING;
