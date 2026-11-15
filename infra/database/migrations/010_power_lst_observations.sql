-- Conservar por separado las observaciones UTC y las LST de la receta diaria.
ALTER TABLE observations DROP CONSTRAINT observations_time_standard_check;
ALTER TABLE observations ADD CONSTRAINT observations_time_standard_check
    CHECK (time_standard IN ('UTC', 'LST'));
