import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
from keyboard_vision.pipeline import KeyCandidate, cluster_rows, draw_grid_debug, geometry_defects, quality

def test_quality_rejects_uniform_blurry_image():
    assert quality(np.zeros((200,200,3), dtype=np.uint8))['status'] == 'needs_review'

def test_clusters_rows_and_detects_missing_gap():
    keys=[KeyCandidate(x, 10, 30, 30, 0, .8) for x in (0,40,120,160)]
    keys += [KeyCandidate(x, 60, 30, 30, 0, .8) for x in (0,40,80,120)]
    rows=cluster_rows(keys); found=geometry_defects(rows)
    assert len(rows)==2
    assert any(d['type']=='missing_key' for d in found)

def test_defect_bounding_box_uses_source_coordinates():
    keys=[KeyCandidate(x, 10, 30, 30, 0, .8) for x in (0,40,120,160)]
    defect=next(item for item in geometry_defects(cluster_rows(keys), origin=(100, 50)) if item['type']=='missing_key')
    assert defect['bbox']['coordinateSpace'] == 'source'
    assert defect['bbox']['x1'] >= 100
    assert defect['bbox']['y1'] >= 50

def test_grid_debug_has_the_roi_shape():
    image=np.zeros((120,160,3), dtype=np.uint8)
    rows=cluster_rows([KeyCandidate(x, 10, 30, 30, 0, .8) for x in (0,40,80)])
    assert draw_grid_debug(image, rows).shape == image.shape
