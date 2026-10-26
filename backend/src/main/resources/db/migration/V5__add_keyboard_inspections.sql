CREATE TABLE keyboard_inspections (
 id UUID PRIMARY KEY, original_filename VARCHAR(500), device_info VARCHAR(255), layout_type VARCHAR(30),
 source_image_url VARCHAR(500), display_image_url VARCHAR(500), status VARCHAR(40) NOT NULL,
 success BOOLEAN NOT NULL, has_defect BOOLEAN NOT NULL, analysis_json TEXT NOT NULL, total_ms DOUBLE PRECISION,
 created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE keyboard_defects (
 id UUID PRIMARY KEY, inspection_id UUID NOT NULL REFERENCES keyboard_inspections(id) ON DELETE CASCADE,
 defect_type VARCHAR(40) NOT NULL, severity VARCHAR(20) NOT NULL, confidence DOUBLE PRECISION NOT NULL,
 key_label VARCHAR(100), row_index INTEGER, column_index INTEGER, x1 DOUBLE PRECISION, y1 DOUBLE PRECISION,
 x2 DOUBLE PRECISION, y2 DOUBLE PRECISION, reason TEXT
);
CREATE INDEX idx_keyboard_inspections_created_at ON keyboard_inspections(created_at DESC);
CREATE INDEX idx_keyboard_inspections_has_defect ON keyboard_inspections(has_defect);
CREATE INDEX idx_keyboard_defects_inspection_id ON keyboard_defects(inspection_id);
