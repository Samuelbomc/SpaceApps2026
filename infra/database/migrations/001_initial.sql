CREATE TABLE IF NOT EXISTS regions (
    region_id text PRIMARY KEY,
    name text NOT NULL,
    latitude double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180)
);

CREATE TABLE IF NOT EXISTS observations (
    region_id text NOT NULL REFERENCES regions(region_id),
    source text NOT NULL,
    product text NOT NULL,
    observed_date date NOT NULL,
    variable text NOT NULL,
    time_standard text NOT NULL CHECK (time_standard = 'UTC'),
    body jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (region_id, source, product, observed_date, variable, time_standard)
);
CREATE INDEX IF NOT EXISTS observations_region_date ON observations(region_id, observed_date DESC);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id text PRIMARY KEY,
    region_id text NOT NULL REFERENCES regions(region_id),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    status text NOT NULL CHECK (status IN ('running', 'ok', 'partial', 'failed')),
    summary jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ingestion_runs_latest ON ingestion_runs(started_at DESC);

CREATE TABLE IF NOT EXISTS source_snapshots (
    run_id text NOT NULL REFERENCES ingestion_runs(run_id),
    source text NOT NULL,
    body jsonb NOT NULL,
    PRIMARY KEY (run_id, source)
);

CREATE TABLE IF NOT EXISTS job_schedules (
    job_key text PRIMARY KEY,
    interval_seconds integer NOT NULL CHECK (interval_seconds > 0),
    next_run_at timestamptz NOT NULL DEFAULT now(),
    last_success_at timestamptz,
    last_error text,
    retry_at timestamptz
);

CREATE TABLE IF NOT EXISTS analyses (
    analysis_id text PRIMARY KEY,
    region_id text NOT NULL REFERENCES regions(region_id),
    reference_date date NOT NULL,
    horizon_days integer NOT NULL CHECK (horizon_days BETWEEN 1 AND 90),
    input_snapshot_id text NOT NULL,
    body jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS analyses_region_date ON analyses(region_id, reference_date DESC);
