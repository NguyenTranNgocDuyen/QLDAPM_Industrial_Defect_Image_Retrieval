"""Crop recovery and its rejection guards; no models or severity labels required."""
import cv2
import numpy as np
import pytest

from defect_vision.corner_expansion import expand_quad_to_mask, load_expansion_config, quad_mask_metrics
from defect_vision.damage_service import rectify_masks
from defect_vision.perspective import correct_perspective


def clipped_rectangle(scale=1):
    mask = np.zeros((500 * scale, 400 * scale), np.uint8)
    mask[50 * scale:450 * scale, 50 * scale:350 * scale] = 255
    quad = np.float32([[50, 50], [325, 50], [325, 449], [50, 449]]) * scale
    return mask, quad


@pytest.mark.parametrize('scale', [1, 2, 3])
def test_only_clipped_edge_moves_and_masks_stay_unchanged(scale):
    mask, quad = clipped_rectangle(scale)
    original = mask.copy()
    result, audit = expand_quad_to_mask(mask, quad)
    assert audit['applied']
    assert audit['after']['mask_coverage'] >= 0.98
    assert audit['after']['background_ratio'] <= 0.08
    # Left, top and bottom are adequate. Only the right line moves outward.
    assert audit['edge_offsets_px'][0] == 0
    assert audit['edge_offsets_px'][2] == 0
    assert audit['edge_offsets_px'][3] == 0
    assert 0 < audit['edge_offsets_px'][1] <= 30 * scale
    np.testing.assert_allclose(result[[0, 3]], quad[[0, 3]], atol=0.001)
    np.testing.assert_allclose(result[[1, 2], 1], quad[[1, 2], 1], atol=0.001)
    np.testing.assert_array_equal(mask, original)


def test_small_outlier_does_not_expand_a_good_crop():
    mask, _ = clipped_rectangle()
    mask[5, 5] = 255
    quad = np.float32([[50, 50], [349, 50], [349, 449], [50, 449]])
    result, audit = expand_quad_to_mask(mask, quad)
    np.testing.assert_array_equal(result, quad)
    assert not audit['applied'] and audit['reason'] == 'already_covered'


def test_large_missing_region_is_not_reconstructed_by_expansion():
    mask, quad = clipped_rectangle()
    quad[1:3, 0] = 250
    result, audit = expand_quad_to_mask(mask, quad)
    np.testing.assert_array_equal(result, quad)
    assert audit['reason'] == 'edge_offset_limit'


@pytest.mark.parametrize('guard,limit,reason', [
    ('max_area_growth', 1.01, 'area_growth_limit'),
    ('max_corner_displacement_ratio', 0.01, 'corner_displacement_limit'),
    ('max_background_ratio', 0.001, 'background_limit'),
])
def test_expansion_limits_return_original_quad(guard, limit, reason):
    mask, quad = clipped_rectangle()
    if guard == 'max_background_ratio':
        # Hollow surface: coverage alone must not allow a crop full of background.
        mask[100:400, 100:300] = 0
    config = {**load_expansion_config(), guard: limit}
    result, audit = expand_quad_to_mask(mask, quad, config=config)
    np.testing.assert_array_equal(result, quad)
    assert not audit['applied'] and audit['reason'] == reason


def test_out_of_frame_intersections_are_rejected_without_clamping():
    mask = np.zeros((500, 400), np.uint8)
    mask[10:450, 0:300] = 255
    quad = np.float32([[12, 15], [295, 15], [290, 445], [2, 445]])
    result, audit = expand_quad_to_mask(mask, quad)
    assert audit['reason'] == 'candidate_outside_image'
    np.testing.assert_array_equal(result, quad)


def test_expanded_warp_uses_identical_transform_for_image_and_masks():
    body, quad = clipped_rectangle()
    damage = np.zeros_like(body)
    damage[100:400, 330:345] = 255  # Damage lies beyond the initial crop.
    result, _ = expand_quad_to_mask(body, quad)
    rgb = np.repeat(damage[..., None], 3, axis=2)
    corrected = correct_perspective(rgb, result, interpolation=cv2.INTER_NEAREST)
    d, s = rectify_masks(damage, body, corrected.transform_matrix,
                         (corrected.output_width, corrected.output_height))
    np.testing.assert_array_equal(d, corrected.image[..., 0] != 0)
    assert d.any() and np.all(s[d])
    assert quad_mask_metrics(body != 0, result)['mask_coverage'] >= 0.98


@pytest.mark.parametrize('mask', [np.zeros((50, 50)), np.zeros((2, 3, 4))])
def test_invalid_surface_is_not_turned_into_recovered_geometry(mask):
    with pytest.raises(ValueError, match='nonempty 2D'):
        expand_quad_to_mask(mask, [[1, 1], [20, 1], [20, 20], [1, 20]])
