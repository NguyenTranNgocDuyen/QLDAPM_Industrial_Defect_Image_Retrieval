import json
import math
import cv2
import numpy as np
import pytest

from defect_vision.damage_severity import evaluate_geometry, load_config, skeleton_length


def evaluate(mask, **kwargs):
    return evaluate_geometry(mask, np.ones_like(mask), full_surface_size=(mask.shape[1], mask.shape[0]),
                             geometry_confirmed=True, observation_complete=True, **kwargs)


def test_long_thin_candidate_is_reference_only_under_area_width_rule():
    d = np.zeros((1000, 1000), bool)
    d[500, 50:950] = True
    r = evaluate(d)
    assert r['area_ratio'] < 0.005
    assert r['width_ratio'] < 0.005
    assert r['skeleton_length_ratio'] > 0.5
    assert r['estimated_severity'] == 'minor'
    assert r['metric_levels']['skeleton_length_ratio'] == 'severe'
    assert all('skeleton_length_ratio' not in reason for reason in r['reasons'])


def test_short_thick_and_large_patch():
    d = np.zeros((1000, 1000), bool)
    d[400:420, 400:430] = True
    r = evaluate(d)
    assert r['area_ratio'] < 0.005 and r['skeleton_length_ratio'] < 0.2
    assert r['width_ratio'] >= 0.015
    assert r['estimated_severity'] == 'minor'
    assert 'area_within_minor_limit' in r['reasons']
    d[300:550, 300:550] = True
    assert evaluate(d)['metric_levels']['area_ratio'] == 'severe'


@pytest.mark.parametrize('kind', ['empty', 'point', 'full', 'edge', 'multiple', 'loop'])
def test_degenerate_and_topological_cases_are_finite_and_do_not_mutate(kind):
    d = np.zeros((100, 100), np.uint8)
    if kind == 'point': d[50, 50] = 255
    if kind == 'full': d[:] = 255
    if kind == 'edge': d[:3, :] = 255
    if kind == 'multiple': d[20, 10:40] = 255; d[70, 10:90] = 255
    if kind == 'loop': cv2.circle(d, (50, 50), 20, 255, 1)
    before = d.copy()
    r = evaluate(d)
    json.dumps(r, allow_nan=False)
    np.testing.assert_array_equal(before, d)
    if kind == 'empty':
        assert r['estimated_severity'] is None and r['status'] == 'no_detected_damage'
    if kind == 'point': assert r['skeleton_length_max_px'] == 0
    if kind == 'full': assert r['width_p90_max_px'] > 90
    if kind == 'multiple':
        assert r['component_count'] == 2
        assert r['skeleton_length_max_px'] == 79
        assert r['skeleton_length_total_px'] == 108


def test_diagonal_graph_does_not_add_staircase_shortcuts():
    staircase = np.array([[1, 1], [0, 1]], bool)
    assert skeleton_length(staircase) == 2
    assert skeleton_length(np.eye(3, dtype=bool)) == pytest.approx(2 * math.sqrt(2))


def test_unavailable_geometry_surface_and_invalid_masks():
    d = np.ones((20, 20), bool)
    assert evaluate_geometry(d, None)['status'] == 'insufficient_evidence'
    assert evaluate_geometry(d, np.zeros_like(d))['status'] == 'insufficient_evidence'
    assert evaluate_geometry(d, d)['estimated_severity'] is None
    r = evaluate_geometry(d, d, full_surface_size=(20, 20), geometry_confirmed=True)
    assert r['status'] == 'needs_review' and r['estimated_severity'] is None
    with pytest.raises(ValueError): evaluate_geometry(d, np.ones((10, 10), bool))
    with pytest.raises(ValueError): evaluate_geometry(d.astype(float), d)
    with pytest.raises(ValueError): evaluate_geometry(d, d, full_surface_size=(5, 5))


@pytest.mark.parametrize('shape', ['line', 'patch', 'short'])
def test_uniform_resolution_change_preserves_normalized_metrics(shape):
    d = np.zeros((600, 400), np.uint8)
    if shape == 'line': d[100:500, 200:203] = 1
    if shape == 'patch': d[100:250, 100:200] = 1
    if shape == 'short': d[200:220, 200:240] = 1
    a = evaluate(d)
    b = evaluate(cv2.resize(d, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST))
    for metric in ('area_ratio', 'skeleton_length_ratio', 'width_ratio'):
        assert a[metric] == pytest.approx(b[metric], abs=0.006)
    assert a['estimated_severity'] == b['estimated_severity']


def test_config_validation(tmp_path):
    cfg = load_config()
    cfg['area_ratio']['severe'] = float('nan')
    path = tmp_path / 'invalid.json'
    path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError): load_config(path)
    cfg['area_ratio']['severe'] = cfg['area_ratio']['moderate']
    path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError): load_config(path)


def test_provisional_geometry_is_explicit_and_strict_mode_still_requires_evidence():
    d = np.zeros((1024,1024), bool); d[500,50:950] = True
    kwargs = dict(full_surface_size=(1024,1024), geometry_confirmed=False, observation_complete=False)
    strict = evaluate_geometry(d, np.ones_like(d), **kwargs)
    assert strict['estimated_severity'] is None
    image = evaluate_geometry(d, np.ones_like(d), allow_image_estimate=True, **kwargs)
    assert image['estimated_severity'] == 'minor' and image['needs_review'] is True
    assert image['estimation_basis'] == 'image_geometry'
    missing = evaluate_geometry(d, np.ones_like(d), allow_image_estimate=True)
    assert missing['estimated_severity'] is None  # A frame is still mandatory.


def test_image_geometry_config_rejects_nonfinite_and_out_of_range(tmp_path):
    config = load_config()
    for key, value in [('min_quad_fill_ratio', float('inf')), ('min_convex_fill_ratio', 1.1),
                       ('max_opposite_edge_ratio', 0.5), ('min_short_side_px', -1), ('enabled', 'yes')]:
        broken = json.loads(json.dumps(config)); broken['image_geometry'][key] = value
        path = tmp_path / 'quality.json'; path.write_text(json.dumps(broken))
        with pytest.raises(ValueError): load_config(path)
