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


def test_phone_segmenter_missing_model():
    segmenter = PhoneSegmenter("non_existent_model_12345.pt")
    with pytest.raises(PhoneSegmenterError, match="not found"):
        segmenter.segment_and_correct(np.zeros((100, 100, 3), dtype=np.uint8))
