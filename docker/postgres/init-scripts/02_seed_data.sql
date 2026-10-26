-- =============================================================================
-- Industrial Defect Image Retrieval - Seed Data
-- =============================================================================

-- 1. Defect Catalog Types
INSERT INTO defect_types (code, name, description, severity, bounding_box_color, is_active)
VALUES
    ('scratch', 'Vết xước bề mặt', 'Vết xước trên vỏ hoặc màn hình thiết bị', 'MEDIUM', '#FF5722', TRUE),
    ('crack', 'Vết nứt / vỡ', 'Nứt kính hoặc nứt khung viền thiết bị', 'CRITICAL', '#E91E63', TRUE),
    ('dent', 'Vết móp méo', 'Lõm hoặc biến dạng cơ học trên vỏ máy', 'HIGH', '#9C27B0', TRUE),
    ('pinhole', 'Lỗ kim / bọt khí', 'Lỗ nhỏ hoặc bong bóng sơn trên bề mặt linh kiện', 'LOW', '#FF9800', TRUE),
    ('contamination', 'Dị vật / Bụi bẩn', 'Bám bụi, dầu mỡ hoặc keo thừa trên linh kiện', 'LOW', '#4CAF50', TRUE),
    ('solder_bridge', 'Chập mối hàn', 'Chập mạch hàn giữa các chân linh kiện trên bo mạch', 'CRITICAL', '#F44336', TRUE),
    ('missing_component', 'Thiếu linh kiện', 'Linh kiện bị rơi hoặc chưa được gắn vào bo mạch', 'CRITICAL', '#D32F2F', TRUE)
ON CONFLICT (code) DO NOTHING;

-- 2. Seed Sample Defect Gallery (Reference images for retrieval)
INSERT INTO defect_gallery (id, title, image_url, defect_class, component_type, description)
VALUES
    ('a0000000-0000-0000-0000-000000000001', 'Mẫu xước vỏ nhôm A1', '/static/gallery/scratch_01.jpg', 'scratch', 'Chassis', 'Vết xước dài 15mm bề mặt anodized'),
    ('a0000000-0000-0000-0000-000000000002', 'Mẫu nứt góc màn hình kính', '/static/gallery/crack_01.jpg', 'crack', 'Glass Display', 'Vết nứt tia từ góc trên bên phải'),
    ('a0000000-0000-0000-0000-000000000003', 'Mẫu chập chân IC', '/static/gallery/solder_01.jpg', 'solder_bridge', 'PCB Board', 'Chập chân số 4 và 5 của vi điều khiển')
ON CONFLICT (id) DO NOTHING;

-- 3. Seed Sample Completed Scan (For testing contract compliance immediately)
INSERT INTO scans (
    id,
    original_filename,
    source_image_url,
    source_width,
    source_height,
    display_image_url,
    display_width,
    display_height,
    coordinate_space,
    has_defect,
    success,
    status,
    preprocessing_ms,
    inference_ms,
    postprocessing_ms,
    total_ms,
    device_info
) VALUES (
    '81f59d2d-9b93-4f5e-a18b-b5a34178ad18',
    'sample_phone_back.jpg',
    '/api/scans/81f59d2d-9b93-4f5e-a18b-b5a34178ad18/source',
    1280,
    720,
    '/api/scans/81f59d2d-9b93-4f5e-a18b-b5a34178ad18/image',
    1280,
    720,
    'processed',
    TRUE,
    TRUE,
    'COMPLETED',
    12.4,
    54.8,
    4.1,
    71.3,
    'Demo Device A100'
) ON CONFLICT (id) DO NOTHING;

-- 4. Sample Detections for the Scan above
INSERT INTO defect_detections (
    id,
    scan_id,
    defect_class,
    confidence,
    x1,
    y1,
    x2,
    y2
) VALUES (
    'd0000000-0000-0000-0000-000000000001',
    '81f59d2d-9b93-4f5e-a18b-b5a34178ad18',
    'scratch',
    0.910000,
    120.0,
    80.0,
    300.0,
    180.0
) ON CONFLICT (id) DO NOTHING;

-- 5. Sample Image Retrieval Result
INSERT INTO image_retrievals (
    id,
    scan_id,
    gallery_item_id,
    reference_image_url,
    matched_defect_type,
    similarity_score,
    rank_order
) VALUES (
    'r0000000-0000-0000-0000-000000000001',
    '81f59d2d-9b93-4f5e-a18b-b5a34178ad18',
    'a0000000-0000-0000-0000-000000000001',
    '/static/gallery/scratch_01.jpg',
    'scratch',
    0.885,
    1
) ON CONFLICT (id) DO NOTHING;
