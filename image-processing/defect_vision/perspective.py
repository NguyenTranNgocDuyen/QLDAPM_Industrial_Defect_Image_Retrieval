"""Perspective correction based on four device-corner coordinates."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Iterable

import cv2
import numpy as np
from numpy.typing import NDArray


Image = NDArray[np.uint8]
PointArray = NDArray[np.float32]


class PerspectiveCorrectionError(ValueError):
    """Raised when an image or its four corner points are invalid."""


@dataclass(frozen=True)
class PerspectiveResult:
    """Result and metadata from one perspective-correction operation."""

    image: Image
    ordered_corners: PointArray
    transform_matrix: NDArray[np.float64]
    output_width: int
    output_height: int
    elapsed_ms: float


def _as_corner_array(points: Iterable[Iterable[float]]) -> PointArray:
    corners = np.asarray(list(points), dtype=np.float32)
    if corners.shape != (4, 2):
        raise PerspectiveCorrectionError(
            "Exactly four corner points with shape (4, 2) are required."
        )
    if not np.isfinite(corners).all():
        raise PerspectiveCorrectionError("Corner coordinates must be finite numbers.")
    if np.unique(corners, axis=0).shape[0] != 4:
        raise PerspectiveCorrectionError("Corner points must be distinct.")
    return corners


def order_corners(points: Iterable[Iterable[float]]) -> PointArray:
    """Return corners as top-left, top-right, bottom-right, bottom-left."""
    corners = _as_corner_array(points)
    hull = cv2.convexHull(corners, returnPoints=True).reshape(-1, 2)
    if hull.shape[0] != 4 or abs(cv2.contourArea(hull)) < 4.0:
        raise PerspectiveCorrectionError(
            "Corner points must form a non-degenerate convex quadrilateral."
        )

    center = hull.mean(axis=0)
    angles = np.arctan2(hull[:, 1] - center[1], hull[:, 0] - center[0])
    ordered = hull[np.argsort(angles)]

    top_left_index = int(np.argmin(ordered.sum(axis=1)))
    ordered = np.roll(ordered, -top_left_index, axis=0)

    # In image coordinates (y grows downward), clockwise corners have a
    # positive cross product. Reverse the order while keeping top-left first.
    edge_1 = ordered[1] - ordered[0]
    edge_2 = ordered[2] - ordered[1]
    cross = float(edge_1[0] * edge_2[1] - edge_1[1] * edge_2[0])
    if cross < 0:
        ordered = ordered[[0, 3, 2, 1]]

    return ordered.astype(np.float32)


def _validate_image(image: Image) -> None:
    if not isinstance(image, np.ndarray) or image.size == 0:
        raise PerspectiveCorrectionError("Input image must be a non-empty array.")
    if image.ndim not in (2, 3):
        raise PerspectiveCorrectionError("Input image must be grayscale or color.")
    if image.ndim == 3 and image.shape[2] not in (1, 3, 4):
        raise PerspectiveCorrectionError("Unsupported number of image channels.")


def _validate_corner_bounds(corners: PointArray, image: Image) -> None:
    height, width = image.shape[:2]
    x_values = corners[:, 0]
    y_values = corners[:, 1]
    if (
        np.any(x_values < 0)
        or np.any(x_values > width - 1)
        or np.any(y_values < 0)
        or np.any(y_values > height - 1)
    ):
        raise PerspectiveCorrectionError("Corner points must lie inside the image.")


def _output_size(corners: PointArray) -> tuple[int, int]:
    top_left, top_right, bottom_right, bottom_left = corners
    top_width = np.linalg.norm(top_right - top_left)
    bottom_width = np.linalg.norm(bottom_right - bottom_left)
    left_height = np.linalg.norm(bottom_left - top_left)
    right_height = np.linalg.norm(bottom_right - top_right)

    width = int(round(max(top_width, bottom_width))) + 1
    height = int(round(max(left_height, right_height))) + 1
    if width < 2 or height < 2:
        raise PerspectiveCorrectionError("Corrected image would be too small.")
    return width, height


def correct_perspective(
    image: Image,
    points: Iterable[Iterable[float]],
    *,
    interpolation: int = cv2.INTER_LINEAR,
    output_size: tuple[int, int] | None = None,
) -> PerspectiveResult:
    """Rectify the quadrilateral selected around an electronic device.

    The source image is not modified. The output contains only the selected
    quadrilateral, mapped to a front-facing rectangle.
    """
    _validate_image(image)
    corners = order_corners(points)
    _validate_corner_bounds(corners, image)
    output_width, output_height = _output_size(corners)
    if output_size is not None:
        output_width, output_height = output_size
        if (not all(isinstance(x, int) and x >= 2 for x in output_size)
                or max(output_size) > 20000):
            raise PerspectiveCorrectionError('Invalid target surface dimensions.')

    destination = np.array(
        [
            [0, 0],
            [output_width - 1, 0],
            [output_width - 1, output_height - 1],
            [0, output_height - 1],
        ],
        dtype=np.float32,
    )

    started_at = perf_counter()
    transform = cv2.getPerspectiveTransform(corners, destination)
    corrected = cv2.warpPerspective(
        image,
        transform,
        (output_width, output_height),
        flags=interpolation,
        borderMode=cv2.BORDER_CONSTANT,
    )
    elapsed_ms = (perf_counter() - started_at) * 1000.0

    return PerspectiveResult(
        image=corrected,
        ordered_corners=corners,
        transform_matrix=transform,
        output_width=output_width,
        output_height=output_height,
        elapsed_ms=elapsed_ms,
    )


def draw_corners(image: Image, points: Iterable[Iterable[float]]) -> Image:
    """Draw the ordered quadrilateral and corner labels on a copy."""
    _validate_image(image)
    corners = order_corners(points)
    _validate_corner_bounds(corners, image)
    preview = image.copy()
    labels = ("TL", "TR", "BR", "BL")
    colors = ((0, 255, 0), (255, 180, 0), (0, 0, 255), (255, 0, 255))

    polygon = np.round(corners).astype(np.int32).reshape((-1, 1, 2))
    cv2.polylines(preview, [polygon], True, (0, 255, 255), 2, cv2.LINE_AA)
    for point, label, color in zip(corners, labels, colors):
        x, y = np.round(point).astype(int)
        cv2.circle(preview, (x, y), 6, color, -1, cv2.LINE_AA)
        cv2.putText(
            preview,
            label,
            (x + 8, max(18, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )
    return preview


def make_before_after(before: Image, after: Image) -> Image:
    """Create a labeled side-by-side visualization without changing outputs."""
    _validate_image(before)
    _validate_image(after)

    before_bgr = _to_bgr(before)
    after_bgr = _to_bgr(after)
    target_height = max(before_bgr.shape[0], after_bgr.shape[0])
    left = _resize_to_height(before_bgr, target_height)
    right = _resize_to_height(after_bgr, target_height)

    cv2.putText(
        left,
        "BEFORE",
        (16, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        right,
        "AFTER",
        (16, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )
    separator = np.full((target_height, 4, 3), 255, dtype=np.uint8)
    return np.hstack((left, separator, right))


def _to_bgr(image: Image) -> Image:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 1:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image.copy()


def _resize_to_height(image: Image, target_height: int) -> Image:
    if image.shape[0] == target_height:
        return image.copy()
    scale = target_height / image.shape[0]
    target_width = max(1, int(round(image.shape[1] * scale)))
    return cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)


def detect_device_corners(
    image: Image,
    *,
    min_area_ratio: float = 0.05,
    blur_ksize: int = 5,
    segmentation_model: str | None = None,
    model_id: str = "phone-segmentation-uiymg/1",
    api_key: str | None = None,
) -> PointArray | None:
    """Automatically detect the 4 corners of an electronic device quadrilateral.

    Supports:
    1. Local weights: If ``segmentation_model`` is provided or found locally, uses RF-DETR.
    2. Auto-download: If API key is provided or found in environment, uses Roboflow Inference.
    3. Fallback: Uses edge detection and contour polygon approximation.
    """
    _validate_image(image)

    if segmentation_model is not None or api_key is not None:
        try:
            from .phone_segmenter import DEFAULT_PHONE_MODEL, PhoneSegmenterError, detect_phone_corners_segmentation

            seg_corners = detect_phone_corners_segmentation(
                image,
                model_path=segmentation_model or DEFAULT_PHONE_MODEL,
                model_id=model_id,
                api_key=api_key,
            )
            if seg_corners is not None:
                return seg_corners
            print("[Perspective] Notice: Segmentation model detected no device. Falling back to heuristic contour detection.")
        except PhoneSegmenterError as pse:
            print(f"[Perspective] Notice: Segmentation unavailable ({pse}). Falling back to heuristic contour detection.")
        except Exception as exc:
            print(f"[Perspective] Warning: Segmentation model unavailable ({exc}). Falling back to heuristic contour detection.")



    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    h, w = gray.shape[:2]
    total_area = float(h * w)
    min_contour_area = total_area * min_area_ratio

    ksize = blur_ksize if blur_ksize % 2 == 1 else blur_ksize + 1
    blurred = cv2.GaussianBlur(gray, (ksize, ksize), 0)

    candidate_quads: list[tuple[float, np.ndarray]] = []

    # Strategy 1: Multi-threshold Canny edge detection
    edges = cv2.Canny(blurred, 40, 140)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edges, kernel, iterations=1)
    contours_a, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Strategy 2: Otsu thresholding
    _, thresh_otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours_b, _ = cv2.findContours(thresh_otsu, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    all_contours = list(contours_a) + list(contours_b)
    all_contours = sorted(all_contours, key=cv2.contourArea, reverse=True)

    for c in all_contours:
        area = cv2.contourArea(c)
        if area < min_contour_area or area > total_area * 0.98:
            continue

        peri = cv2.arcLength(c, True)
        for factor in (0.02, 0.03, 0.015, 0.04):
            approx = cv2.approxPolyDP(c, factor * peri, True)
            if len(approx) == 4 and cv2.isContourConvex(approx):
                candidate_quads.append((area, approx.reshape(-1, 2).astype(np.float32)))
                break

    if candidate_quads:
        candidate_quads.sort(key=lambda item: item[0], reverse=True)
        best_corners = candidate_quads[0][1]
        try:
            return order_corners(best_corners)
        except Exception:
            pass

    return None


