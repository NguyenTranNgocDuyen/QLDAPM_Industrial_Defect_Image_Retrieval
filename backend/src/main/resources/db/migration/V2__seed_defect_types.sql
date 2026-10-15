-- Seed defect catalog types
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
