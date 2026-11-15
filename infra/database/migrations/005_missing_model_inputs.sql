-- Un diagnóstico de entradas faltantes no tiene un snapshot científico de entrada.
-- El contrato HTTP ya permite null; las predicciones conservan su hash de features.
ALTER TABLE analyses ALTER COLUMN input_snapshot_id DROP NOT NULL;
