ALTER TABLE scans ADD COLUMN IF NOT EXISTS analysis_json TEXT;
-- Unknown evidence is not a healthy result. Preserve null across history queries.
ALTER TABLE scans ALTER COLUMN has_defect DROP NOT NULL;
