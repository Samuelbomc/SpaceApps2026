CREATE TABLE manual_updates (
    request_id uuid PRIMARY KEY,
    requested_by uuid REFERENCES farmer_users(user_id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    retry_at timestamptz,
    phase text NOT NULL CHECK (phase IN ('ingestion','training','recommendations')),
    status text NOT NULL CHECK (status IN ('queued','running','retry_scheduled','completed','completed_with_limitations','failed')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    message text NOT NULL,
    stages jsonb NOT NULL
);
-- La actualización es del sistema: varias solicitudes comparten la corrida activa.
CREATE UNIQUE INDEX manual_updates_one_active ON manual_updates ((true))
WHERE status IN ('queued','running','retry_scheduled');
CREATE INDEX manual_updates_recent ON manual_updates(created_at DESC);
