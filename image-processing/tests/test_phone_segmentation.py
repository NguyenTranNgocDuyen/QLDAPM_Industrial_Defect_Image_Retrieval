"""Unit tests for phone segmentation and corner extraction."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from defect_vision.perspective import correct_perspective, order_corners
from defect_vision.phone_segmenter import (
    PhoneSegmentationResult,
    PhoneSegmenter,
    PhoneSegmenterError,
    extract_corners_from_mask,
    make_mask_overlay,
    refine_corners_via_edges,
)


def _create_synthetic_phone_mask(
    h: int = 500,
    w: int = 400,
    tl: tuple[int, int] = (80, 50),
    tr: tuple[int, int] = (320, 70),
    br: tuple[int, int] = (290, 420),
    bl: tuple[int, int] = (60, 390),
) -> np.ndarray:
    """Create a synthetic binary mask with a defined quadrilateral."""
    mask = np.zeros((h, w), dtype=np.uint8)
    quad = np.array([tl, tr, br, bl], dtype=np.int32)
    cv2.fillPoly(mask, [quad], 255)
    return mask


def test_extract_corners_from_mask_basic():
    mask = _create_synthetic_phone_mask()
    corners = extract_corners_from_mask(mask, image_shape=(500, 400))
    assert corners is not None
    assert corners.shape == (4, 2)

    ordered = order_corners(corners)
    # Check that corners are approximately near the ground truth quadrilateral
    assert np.allclose(ordered[0], [80, 50], atol=12.0)
    assert np.allclose(ordered[1], [320, 70], atol=12.0)
    assert np.allclose(ordered[2], [290, 420], atol=12.0)
    assert np.allclose(ordered[3], [60, 390], atol=12.0)


def test_extract_corners_empty_mask():
    empty_mask = np.zeros((100, 100), dtype=np.uint8)
    corners = extract_corners_from_mask(empty_mask)
    assert corners is None


def test_extract_corners_invalid_input():
    assert extract_corners_from_mask(np.array([])) is None


def test_extract_corners_with_boundary_clipping():
    mask = _create_synthetic_phone_mask(h=200, w=200, tl=(0, 0), tr=(199, 0), br=(199, 199), bl=(0, 199))
    corners = extract_corners_from_mask(mask, image_shape=(200, 200))
    assert corners is not None
    assert np.all(corners[:, 0] >= 0)
    assert np.all(corners[:, 0] <= 199)
    assert np.all(corners[:, 1] >= 0)
    assert np.all(corners[:, 1] <= 199)


def test_refine_corners_via_edges():
    mask = _create_synthetic_phone_mask(h=300, w=300, tl=(50, 50), tr=(250, 50), br=(250, 250), bl=(50, 250))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour = max(contours, key=cv2.contourArea)
    initial_quad = np.array([[50, 50], [250, 50], [250, 250], [50, 250]], dtype=np.float32)

    refined = refine_corners_via_edges(contour, initial_quad)
    assert refined.shape == (4, 2)
    assert np.allclose(refined, initial_quad, atol=2.0)


def test_make_mask_overlay():
    img = np.full((100, 100, 3), 128, dtype=np.uint8)
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[20:80, 20:80] = 255

    overlay = make_mask_overlay(img, mask)
    assert overlay.shape == (100, 100, 3)
    assert overlay.dtype == np.uint8
    # Pixel inside mask should differ from original gray
    assert not np.array_equal(overlay[50, 50], img[50, 50])


def test_phone_segmenter_missing_model(monkeypatch):
    monkeypatch.setattr(PhoneSegmenter, "_resolve_api_key", lambda self: None)
    segmenter = PhoneSegmenter("non_existent_model_12345.pt")
    with pytest.raises(PhoneSegmenterError, match="not found"):
        segmenter.segment_and_correct(np.zeros((100, 100, 3), dtype=np.uint8))


def _rounded_phone_in_perspective(scale=1.0, radius=30):
    """Known straight body edges with rounded corners, then photographed obliquely."""
    source = np.zeros((500, 300), dtype=np.uint8)
    cv2.rectangle(source, (30 + radius, 30), (270 - radius, 470), 255, -1)
    cv2.rectangle(source, (30, 30 + radius), (270, 470 - radius), 255, -1)
    for center in ((30 + radius, 30 + radius), (270 - radius, 30 + radius),
                   (270 - radius, 470 - radius), (30 + radius, 470 - radius)):
        cv2.circle(source, center, radius, 255, -1)
    source_corners = np.float32([[30, 30], [270, 30], [270, 470], [30, 470]])
    true_corners = np.float32([[160, 70], [400, 100], [440, 650], [70, 590]]) * scale
    transform = cv2.getPerspectiveTransform(source_corners, true_corners)
    mask = cv2.warpPerspective(source, transform, (round(550 * scale), round(750 * scale)),
                               flags=cv2.INTER_NEAREST)
    return mask, true_corners


def _phone_coverage(mask, corners):
    polygon = cv2.fillConvexPoly(np.zeros_like(mask), np.round(corners).astype(np.int32), 255)
    return np.count_nonzero((mask > 0) & (polygon > 0)) / np.count_nonzero(mask)


@pytest.mark.parametrize('scale', [1.0, 2.0])
def test_rounded_phone_recovers_edges_and_retains_body_after_warp(scale):
    mask, true_corners = _rounded_phone_in_perspective(scale)
    original_mask = mask.copy()
    old = extract_corners_from_mask(mask, image_shape=mask.shape, adaptive_refinement=False)
    new = extract_corners_from_mask(mask, image_shape=mask.shape)
    assert _phone_coverage(mask, old) < 0.95  # Reproduces the shallow crop.
    assert _phone_coverage(mask, new) > 0.99
    # Adequate legacy edges are intentionally preserved; allow their small
    # residual error while requiring a substantial gain over the shallow crop.
    old_error = np.max(np.linalg.norm(old - true_corners, axis=1))
    new_error = np.max(np.linalg.norm(new - true_corners, axis=1))
    assert new_error < 6 * scale
    assert new_error < old_error * 0.25
    np.testing.assert_array_equal(mask, original_mask)

    # Points along each physical side (including near the rounded corners) must
    # remain within a small raster tolerance of the corrected frame. This checks
    # the downstream homography too, including preserved legacy edge errors.
    corrected = correct_perspective(mask, new)
    edge_points = np.array([
        true_corners[i] * (1 - t) + true_corners[(i + 1) % 4] * t
        for i in range(4) for t in (0.2, 0.5, 0.8)
    ], dtype=np.float32)
    mapped = cv2.perspectiveTransform(edge_points[None], corrected.transform_matrix)[0]
    assert np.all(mapped >= -4.1 * scale)
    assert np.all(mapped[:, 0] <= corrected.output_width - 1 + 4.1 * scale)
    assert np.all(mapped[:, 1] <= corrected.output_height - 1 + 4.1 * scale)


@pytest.mark.parametrize('scale', [0.5, 1.0])
def test_already_well_fitted_phone_keeps_exact_legacy_corners(scale):
    mask, _ = _rounded_phone_in_perspective(scale, radius=15)
    old = extract_corners_from_mask(mask, image_shape=mask.shape, adaptive_refinement=False)
    new = extract_corners_from_mask(mask, image_shape=mask.shape)
    assert _phone_coverage(mask, old) > 0.98
    np.testing.assert_array_equal(new, old)


def test_strong_rounding_uses_bounded_expansion_without_altering_the_mask():
    mask, _ = _rounded_phone_in_perspective(radius=45)
    old = extract_corners_from_mask(mask, image_shape=mask.shape, adaptive_refinement=False)
    audit = {}
    original = mask.copy()
    new = extract_corners_from_mask(mask, image_shape=mask.shape, corner_diagnostics=audit)
    assert _phone_coverage(mask, new) >= 0.98
    assert audit['applied']
    assert audit['after']['background_ratio'] <= 0.12
    assert audit['area_growth'] <= 1.35
    np.testing.assert_array_equal(original, mask)


def test_no_refine_still_returns_original_polygon():
    mask, _ = _rounded_phone_in_perspective()
    old = extract_corners_from_mask(mask, refine_edges=False, adaptive_refinement=False)
    new = extract_corners_from_mask(mask, refine_edges=False)
    np.testing.assert_array_equal(new, old)
