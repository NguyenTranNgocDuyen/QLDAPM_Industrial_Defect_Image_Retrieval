"""An incomplete view may receive a clearly limited area estimate, never fake L/W."""
import json

import cv2
import numpy as np
import pytest

from defect_vision.damage_severity import evaluate_observed_area, load_config


@pytest.mark.parametrize('count,level', [(1, 'minor'), (50, 'minor'), (200, 'minor'),
                                        (201, 'moderate'), (500, 'moderate'), (501, 'moderate')])
def test_observed_area_levels_are_partial_and_json_safe(count, level):
    surface = np.ones((100, 100), bool)
    damage = np.zeros_like(surface)
    damage.flat[:count] = True
    before = damage.copy()
    result = evaluate_observed_area(damage, surface, reasons=['phone_touches_source_border'])
    assert result['estimated_severity'] == level
    assert result['needs_review'] and result['severity_is_partial']
    assert result['area_ratio'] == pytest.approx(count / 10000)
    assert result['skeleton_length_ratio'] is None and result['width_ratio'] is None
    assert result['unassessed_metrics'] == ['skeleton_length_ratio', 'width_ratio']
    if count > 500:
        assert 'severe_unconfirmed_without_width' in result['reasons']
    else:
        assert 'severe_unconfirmed_without_width' not in result['reasons']
    assert result['measurement_coordinate_space'] == 'source'
    assert result['locations_coordinate_space'] == 'source'
    assert sum(x['candidate_pixels_source'] for x in result['locations']) == count
    np.testing.assert_array_equal(damage, before)
    json.dumps(result, allow_nan=False)


def test_long_thin_partial_view_never_claims_length_or_width_have_passed():
    surface = np.ones((1000, 1000), bool)
    damage = np.zeros_like(surface)
    damage[500, 50:950] = True
    result = evaluate_observed_area(damage, surface, reasons=['missing_surface_corners'])
    assert result['severity_is_partial'] and 'partial_area_estimate_only' in result['reasons']
    assert result['metric_levels'].keys() == {'area_ratio'}
    assert 'length_and_width_unavailable' in result['limitations']
    # Missing geometry is not replaced by the image/visible bbox as a full face.
    assert result['skeleton_length_ratio'] is None and result['width_ratio'] is None


def test_area_excludes_background_and_is_resolution_independent():
    surface = np.zeros((100, 100), np.uint8)
    surface[:50] = 255
    damage = np.zeros_like(surface)
    damage[10:20, 10:20] = 255
    damage[80:90] = 255  # Outside the observed phone; must not count.
    a = evaluate_observed_area(damage, surface, reasons=[])
    b = evaluate_observed_area(cv2.resize(damage, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST),
                              cv2.resize(surface, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST), reasons=[])
    assert a['area_ratio'] == b['area_ratio'] == 0.02
    assert a['estimated_severity'] == b['estimated_severity'] == 'minor'


def test_empty_tiny_or_invalid_masks_are_not_forced_to_be_healthy_or_minor():
    damage = np.zeros((100, 100), bool)
    result = evaluate_observed_area(damage, np.ones_like(damage), reasons=[])
    assert result['status'] == 'no_detected_damage'
    assert result['estimated_severity'] is None and result['needs_review']
    assert 'unseen_surface_not_assessed' in result['limitations']
    assert evaluate_observed_area(damage, damage, reasons=[])['estimated_severity'] is None
    tiny = np.ones((10, 10), bool)
    assert evaluate_observed_area(tiny, tiny, reasons=[])['estimated_severity'] is None
    with pytest.raises(ValueError):
        evaluate_observed_area(damage, tiny, reasons=[])


def test_invalid_fallback_configuration_is_rejected(tmp_path):
    config = load_config()
    config['observed_area_fallback']['min_surface_pixels'] = True
    path = tmp_path / 'invalid.json'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        load_config(path)
