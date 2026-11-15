CREATE TABLE geographic_areas (
    area_id text PRIMARY KEY,
    region_id text NOT NULL UNIQUE REFERENCES regions(region_id),
    geometry jsonb NOT NULL,
    sampling_point jsonb NOT NULL,
    sampling_method text NOT NULL CHECK (sampling_method IN ('selected_point','interior_reference_point')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE geographic_analyses (
    request_id uuid PRIMARY KEY,
    area_id text NOT NULL REFERENCES geographic_areas(area_id),
    horizon_days integer NOT NULL CHECK (horizon_days IN (7,15,30,60)),
    forecast_start_date date NOT NULL,
    status text NOT NULL CHECK (status IN ('queued','running','waiting_inputs','retry_scheduled','completed','failed')),
    attempts integer NOT NULL DEFAULT 0,
    retry_at timestamptz,
    messages jsonb NOT NULL DEFAULT '[]',
    analysis_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (area_id, horizon_days, forecast_start_date)
);
CREATE INDEX geographic_analyses_due ON geographic_analyses(status,retry_at,created_at);
