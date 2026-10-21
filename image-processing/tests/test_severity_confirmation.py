"""Area-led policy: <=2% stays minor; severe needs area >5% AND width >=8%."""
import json
from pathlib import Path

import numpy as np
import pytest

from defect_vision.damage_severity import classify_metrics, evaluate_geometry, load_config


def metrics(area, width, length=0.294):
    return dict(area_ratio=area, width_ratio=width, skeleton_length_ratio=length)


def test_reported_405_pixel_case_is_minor_in_both_area_and_width():
    config = load_config()
    result = classify_metrics(metrics(0.006694901449747516, 0.031746031746031744), config)
    assert result['estimated_severity'] == 'minor'
    assert result['reasons'] == ['area_within_minor_limit']
    assert result['metric_levels']['width_ratio'] == 'minor'


@pytest.mark.parametrize('area,width,expected', [
    (0.049999, 0.08, 'moderate'), (0.05, 0.2, 'moderate'),
    (0.050001, 0.079999, 'moderate'), (0.050001, 0.08, 'severe'),
    (0.2, 0.1, 'severe'),
    (0.019999, 0.2, 'minor'), (0.02, 0.2, 'minor'),
    (0.020001, 0.001, 'moderate'), (0.02, 0.001, 'minor'),
    (0.001, 0.005, 'minor'), (0.0001, 0.2, 'minor'),
    (0.2, 0.0001, 'moderate'),
])
def test_area_led_inclusive_minor_and_combined_severe_boundaries(area, width, expected):
    assert classify_metrics(metrics(area, width), load_config())['estimated_severity'] == expected


def test_skeleton_and_absolute_pixels_do_not_change_the_current_decision():
    config = load_config()
    for length in (0.0, 0.294, 0.9, 20.0):
        for pixels in (1, 199, 200, 405, 405000):
            result = classify_metrics({**metrics(0.00669, 0.03175, length),
                                       'candidate_pixels_original': pixels}, config)
            assert result['estimated_severity'] == 'minor'
            assert all('skeleton_length_ratio' not in reason for reason in result['reasons'])


def test_previous_v3_rule_still_reproduces_original_result():
    old = load_config(Path(__file__).resolve().parents[1] / 'defect_vision/severity.v3.json')
    result = classify_metrics(metrics(0.00669, 0.03175), old)
    assert result['estimated_severity'] == 'severe'


def test_previous_v4_rule_still_reproduces_moderate_result():
    old = load_config(Path(__file__).resolve().parents[1] / 'defect_vision/severity.v4.json')
    assert classify_metrics(metrics(0.00669, 0.03175), old)['estimated_severity'] == 'moderate'


@pytest.mark.parametrize('width,band', [(0.049999, 'minor'), (0.05, 'moderate'),
                                      (0.079999, 'moderate'), (0.08, 'severe')])
def test_width_bands_and_final_severe_gate(width, band):
    config = load_config()
    result = classify_metrics(metrics(0.06, width), config)
    assert result['metric_levels']['width_ratio'] == band
    assert result['estimated_severity'] == ('severe' if band == 'severe' else 'moderate')
    # Width cannot override the inclusive minor-area gate.
    assert classify_metrics(metrics(0.02, width), config)['estimated_severity'] == 'minor'


def test_v5_width_thresholds_remain_reproducible():
    old = load_config(Path(__file__).resolve().parents[1] / 'defect_vision/severity.v5.json')
    assert classify_metrics(metrics(0.06, 0.03), old)['estimated_severity'] == 'severe'
    assert classify_metrics(metrics(0.06, 0.03), load_config())['estimated_severity'] == 'moderate'


@pytest.mark.parametrize('key', ['area_moderate_comparison', 'area_severe_comparison'])
def test_area_boundary_operator_cannot_be_silently_changed(tmp_path, key):
    config = load_config()
    config['classification'][key] = '>='
    path = tmp_path / 'bad-boundary.json'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        load_config(path)


def test_invalid_policy_rejected(tmp_path):
    config = load_config()
    config['classification']['rule'] = 'unknown'
    path = tmp_path / 'bad.json'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        load_config(path)


def test_empty_mask_stays_ungraded_despite_high_width_threshold_sensitivity():
    mask = np.zeros((100, 100), bool)
    result = evaluate_geometry(mask, np.ones_like(mask), full_surface_size=(100, 100),
                               geometry_confirmed=True, observation_complete=True)
    assert result['estimated_severity'] is None
    assert result['classification_rule'] == 'area_led_width_confirmation'
