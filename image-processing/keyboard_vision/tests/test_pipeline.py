import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
from keyboard_vision.pipeline import KeyCandidate, cluster_rows, geometry_defects, quality

def test_quality_rejects_uniform_blurry_image():
    assert quality(np.zeros((200,200,3), dtype=np.uint8))['status'] == 'needs_review'

def test_clusters_rows_and_detects_missing_gap():
    keys=[KeyCandidate(x, 10, 30, 30, 0, .8) for x in (0,40,120,160)]
    keys += [KeyCandidate(x, 60, 30, 30, 0, .8) for x in (0,40,80,120)]
    rows=cluster_rows(keys); found=geometry_defects(rows)
    assert len(rows)==2
    assert any(d['type']=='missing_key' for d in found)
