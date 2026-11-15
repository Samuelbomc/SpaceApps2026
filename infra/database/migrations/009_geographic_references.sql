ALTER TABLE geographic_analyses ADD COLUMN reference_start_date date;
ALTER TABLE geographic_analyses ADD COLUMN reference_analysis_id text;
ALTER TABLE geographic_analyses ADD COLUMN reference_region_id text REFERENCES regions(region_id);
ALTER TABLE geographic_analyses ADD COLUMN reference_kind text
    CHECK (reference_kind IN ('prepared_reference','bundled_public_snapshot'));

-- Permite evaluar referencias para solicitudes pendientes sin repetir ingesta.
UPDATE geographic_analyses SET retry_at=now()
    WHERE status='waiting_inputs' AND reference_analysis_id IS NULL;
