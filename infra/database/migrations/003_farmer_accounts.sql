CREATE TABLE farmer_users (
    user_id uuid PRIMARY KEY,
    email text NOT NULL UNIQUE CHECK (email = lower(email)),
    display_name text NOT NULL,
    password_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE farmer_sessions (
    token_hash text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES farmer_users(user_id) ON DELETE CASCADE,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX farmer_sessions_user ON farmer_sessions(user_id);
CREATE TABLE auth_rate_limits (
    bucket text PRIMARY KEY,
    window_started timestamptz NOT NULL DEFAULT now(),
    attempts integer NOT NULL
);
CREATE TABLE farms (
    farm_id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES farmer_users(user_id) ON DELETE CASCADE,
    body jsonb NOT NULL,
    revision integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX farms_owner ON farms(owner_id);
CREATE TABLE farm_datasets (
    dataset_id uuid PRIMARY KEY,
    farm_id uuid NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
    original_filename text NOT NULL,
    storage_key text NOT NULL UNIQUE,
    sha256 text NOT NULL,
    row_count integer NOT NULL CHECK(row_count > 0),
    first_date date NOT NULL,
    last_date date NOT NULL,
    variables jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(farm_id, sha256)
);
CREATE TABLE farm_observations (
    dataset_id uuid NOT NULL REFERENCES farm_datasets(dataset_id) ON DELETE CASCADE,
    observed_date date NOT NULL,
    variable text NOT NULL,
    value double precision NOT NULL,
    unit text NOT NULL,
    crop text NOT NULL DEFAULT '',
    PRIMARY KEY(dataset_id, observed_date, variable, crop)
);
CREATE INDEX farm_observations_date ON farm_observations(observed_date);
