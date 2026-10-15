-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Defect catalog table
CREATE TABLE IF NOT EXISTS defect_types (
    code VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    severity VARCHAR(20) NOT NULL DEFAULT 'MEDIUM',
    bounding_box_color VARCHAR(10) DEFAULT '#FF0000',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Scans history table
CREATE TABLE IF NOT EXISTS scans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    original_filename VARCHAR(255),
    source_image_url VARCHAR(500),
    source_width INTEGER NOT NULL,
    source_height INTEGER NOT NULL,
    display_image_url VARCHAR(500),
    display_width INTEGER NOT NULL,
    display_height INTEGER NOT NULL,
    coordinate_space VARCHAR(20) NOT NULL DEFAULT 'processed',
    has_defect BOOLEAN NOT NULL DEFAULT FALSE,
    success BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(30) NOT NULL DEFAULT 'COMPLETED',
    error_message TEXT,
    device_info VARCHAR(100),
    preprocessing_ms DOUBLE PRECISION DEFAULT 0.0,
    inference_ms DOUBLE PRECISION DEFAULT 0.0,
    postprocessing_ms DOUBLE PRECISION DEFAULT 0.0,
    total_ms DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Defect detections table
CREATE TABLE IF NOT EXISTS defect_detections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_id UUID NOT NULL,
    defect_class VARCHAR(50) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    x1 DOUBLE PRECISION NOT NULL,
    y1 DOUBLE PRECISION NOT NULL,
    x2 DOUBLE PRECISION NOT NULL,
    y2 DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_detections_scan FOREIGN KEY (scan_id)
        REFERENCES scans (id) ON DELETE CASCADE,
    CONSTRAINT chk_detection_confidence CHECK (confidence >= 0.0 AND confidence <= 1.0)
);

-- Defect reference gallery table
CREATE TABLE IF NOT EXISTS defect_gallery (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(150) NOT NULL,
    image_url VARCHAR(500) NOT NULL,
    defect_class VARCHAR(50) NOT NULL,
    component_type VARCHAR(100),
    description TEXT,
    embedding_vector TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Image retrievals table
CREATE TABLE IF NOT EXISTS image_retrievals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_id UUID NOT NULL,
    gallery_item_id UUID,
    reference_image_url VARCHAR(500) NOT NULL,
    matched_defect_type VARCHAR(50) NOT NULL,
    similarity_score DOUBLE PRECISION NOT NULL,
    rank_order INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_retrievals_scan FOREIGN KEY (scan_id)
        REFERENCES scans (id) ON DELETE CASCADE,
    CONSTRAINT fk_retrievals_gallery FOREIGN KEY (gallery_item_id)
        REFERENCES defect_gallery (id) ON DELETE SET NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_scans_created_at ON scans (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scans_has_defect ON scans (has_defect);
CREATE INDEX IF NOT EXISTS idx_scans_status ON scans (status);
CREATE INDEX IF NOT EXISTS idx_detections_scan_id ON defect_detections (scan_id);
CREATE INDEX IF NOT EXISTS idx_detections_defect_class ON defect_detections (defect_class);
CREATE INDEX IF NOT EXISTS idx_retrievals_scan_id ON image_retrievals (scan_id);
CREATE INDEX IF NOT EXISTS idx_gallery_defect_class ON defect_gallery (defect_class);
