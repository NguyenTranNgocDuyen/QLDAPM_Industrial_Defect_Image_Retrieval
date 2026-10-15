"""Phone segmentation and corner-guided perspective correction module.

Uses the trained RF-DETR segmentation model (weights.pt) to segment the smartphone
body/screen, extracts its 4 geometric corners with sub-pixel edge refinement, and
applies perspective correction to produce front-facing, rectified device images.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Sequence

import cv2
import numpy as np
from numpy.typing import NDArray

from .perspective import (
    Image,
    PerspectiveCorrectionError,
    PerspectiveResult,
    PointArray,
    correct_perspective,
    draw_corners,
    make_before_after,
    order_corners,
)


class PhoneSegmenterError(ValueError):
    """Raised when phone segmentation or corner detection fails."""


@dataclass(frozen=True)
class PhoneSegmentationResult:
    """Full results from segmentation, corner extraction, and perspective rectification."""

    image: Image
    mask: Image
    confidence: float
    corners: PointArray
    perspective_result: PerspectiveResult
    corner_preview: Image
    mask_overlay: Image
    before_after: Image
    timings_ms: dict[str, float]

    def to_dict(self) -> dict[str, object]:
        return {
            "confidence": round(float(self.confidence), 4),
            "corners": self.corners.round(3).tolist(),
            "outputWidth": self.perspective_result.output_width,
            "outputHeight": self.perspective_result.output_height,
            "timings_ms": {k: round(v, 3) for k, v in self.timings_ms.items()},
            "transformMatrix": self.perspective_result.transform_matrix.round(8).tolist(),
        }


def _intersect_lines(l1: NDArray[np.float32], l2: NDArray[np.float32]) -> NDArray[np.float32] | None:
    """Intersect two 2D lines given in (vx, vy, x0, y0) format."""
    vx1, vy1, x1, y1 = [float(v) for v in l1]
    vx2, vy2, x2, y2 = [float(v) for v in l2]
    a1, b1 = vy1, -vx1
    c1 = vy1 * x1 - vx1 * y1
    a2, b2 = vy2, -vx2
    c2 = vy2 * x2 - vx2 * y2
    det = a1 * b2 - a2 * b1
    if abs(det) < 1e-5:
        return None
    x = (c1 * b2 - c2 * b1) / det
    y = (a1 * c2 - a2 * c1) / det
    return np.array([x, y], dtype=np.float32)


def refine_corners_via_edges(
    contour: NDArray[np.int32],
    quad: PointArray,
    margin_ratio: float = 0.15,
    dist_threshold: float = 8.0,
) -> PointArray:
    """Refine initial polygon corners by fitting lines to straight edges and intersecting them.

    This overcomes rounded corners and bevels on modern smartphones by finding the
    true physical intersection of the four device edges.
    """
    pts = contour.reshape(-1, 2).astype(np.float32)
    lines: list[NDArray[np.float32]] = []

    for i in range(4):
        p1 = quad[i]
        p2 = quad[(i + 1) % 4]
        v = p2 - p1
        v_norm = float(np.linalg.norm(v))
        if v_norm < 1e-3:
            return quad
        u = v / v_norm
        dists_along = np.dot(pts - p1, u)
        perp_vec = np.array([-u[1], u[0]], dtype=np.float32)
        dists_perp = np.abs(np.dot(pts - p1, perp_vec))

        edge_mask = (
            (dists_along > margin_ratio * v_norm)
            & (dists_along < (1.0 - margin_ratio) * v_norm)
            & (dists_perp < dist_threshold)
        )
        edge_pts = pts[edge_mask]

        if len(edge_pts) >= 6:
            line = cv2.fitLine(edge_pts, cv2.DIST_L2, 0, 0.01, 0.01).flatten()
            lines.append(line.astype(np.float32))
        else:
            lines.append(np.array([u[0], u[1], p1[0], p1[1]], dtype=np.float32))

    refined: list[list[float]] = []
    for i in range(4):
        pt = _intersect_lines(lines[(i - 1) % 4], lines[i])
        if pt is None:
            return quad
        refined.append([float(pt[0]), float(pt[1])])

    refined_arr = np.array(refined, dtype=np.float32)
    try:
        ordered = order_corners(refined_arr)
        orig_area = abs(cv2.contourArea(quad))
        ref_area = abs(cv2.contourArea(ordered))
        if 0.80 <= ref_area / max(orig_area, 1.0) <= 1.20:
            return ordered
    except Exception:
        pass
    return quad


def extract_corners_from_mask(
    mask: Image,
    image_shape: tuple[int, int] | None = None,
    *,
    refine_edges: bool = True,
    min_area: float = 1000.0,
) -> PointArray | None:
    """Extract the 4 corners of a smartphone from its segmentation mask.

    Multi-tier algorithm:
    1. Morphological closing to seal internal cracks or holes.
    2. Convex hull calculation on the dominant contour.
    3. Multi-factor adaptive `approxPolyDP` to identify the 4-vertex quadrilateral.
    4. Fallback to extremal diagonal projection or minimum area bounding box.
    5. Sub-pixel straight-edge line fitting (`refine_corners_via_edges`) to eliminate rounded corner error.
    6. Clockwise ordering [TL, TR, BR, BL] and boundary clipping.
    """
    if not isinstance(mask, np.ndarray) or mask.size == 0:
        return None

    bin_mask = (mask > 0).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    closed = cv2.morphologyEx(bin_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(contour)
    if area < min_area:
        return None

    hull = cv2.convexHull(contour)
    peri = cv2.arcLength(hull, True)
    if peri < 10.0:
        return None

    quad: PointArray | None = None

    # Step 1: Adaptive polygon approximation across epsilon factors
    for factor in np.linspace(0.015, 0.085, 30):
        approx = cv2.approxPolyDP(hull, factor * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            quad = approx.reshape(4, 2).astype(np.float32)
            break

    # Step 2: Extremal projection fallback
    if quad is None:
        pts = hull.reshape(-1, 2).astype(np.float32)
        if len(pts) >= 4:
            s = pts.sum(axis=1)
            d = pts[:, 0] - pts[:, 1]
            candidate = np.array(
                [pts[np.argmin(s)], pts[np.argmax(d)], pts[np.argmax(s)], pts[np.argmin(d)]],
                dtype=np.float32,
            )
            try:
                quad = order_corners(candidate)
            except Exception:
                quad = None

    # Step 3: Minimum area bounding box fallback
    if quad is None:
        box = cv2.boxPoints(cv2.minAreaRect(hull)).astype(np.float32)
        try:
            quad = order_corners(box)
        except Exception:
            return None

    try:
        quad = order_corners(quad)
    except Exception:
        return None

    # Step 4: Optional straight edge refinement
    if refine_edges:
        quad = refine_corners_via_edges(contour, quad)

    # Step 5: Coordinate boundary clipping if image_shape provided
    if image_shape is not None:
        h, w = image_shape[:2]
        quad[:, 0] = np.clip(quad[:, 0], 0, w - 1)
        quad[:, 1] = np.clip(quad[:, 1], 0, h - 1)

    return quad


def make_mask_overlay(image: Image, mask: Image, alpha: float = 0.45) -> Image:
    """Create a translucent color overlay of the segmentation mask on the image."""
    bgr = image.copy()
    if bgr.ndim == 2:
        bgr = cv2.cvtColor(bgr, cv2.COLOR_GRAY2BGR)
    elif bgr.shape[2] == 4:
        bgr = cv2.cvtColor(bgr, cv2.COLOR_BGRA2BGR)

    color_mask = np.zeros_like(bgr)
    color_mask[mask > 0] = [0, 255, 128]  # Light emerald green

    overlay = cv2.addWeighted(color_mask, alpha, bgr, 1.0 - alpha, 0)
    binary_mask = (mask > 0).astype(np.uint8) * 255
    contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(overlay, contours, -1, (0, 255, 0), 2, cv2.LINE_AA)
    return overlay


class PhoneSegmenter:
    """Manages the RF-DETR phone segmentation model and corner rectification."""

    def __init__(
        self,
        model_path: str | Path = "models/weights.pt",
        *,
        confidence: float = 0.25,
        device: str = "cpu",
        num_classes: int = 1,
        refine_edges: bool = True,
    ) -> None:
        self.model_path = Path(model_path)
        self.confidence = float(confidence)
        self.device = device
        self.num_classes = int(num_classes)
        self.refine_edges = bool(refine_edges)
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return self._model

        if not self.model_path.is_file():
            # Try resolving relative to project root or image-processing package directory
            candidates = [
                Path("image-processing") / self.model_path,
                Path(__file__).parent.parent / self.model_path,
            ]
            for candidate in candidates:
                if candidate.is_file():
                    self.model_path = candidate
                    break

        if not self.model_path.is_file():
            raise PhoneSegmenterError(
                f"Phone segmentation model file not found at: {self.model_path}"
            )

        try:
            rfdetr = importlib.import_module("rfdetr")
        except ImportError as exc:
            raise PhoneSegmenterError(
                "The 'rfdetr' package is required for phone segmentation. "
                "Install it using: pip install rfdetr supervision torch torchvision"
            ) from exc

        RFDETRSegSmall = getattr(rfdetr, "RFDETRSegSmall", None)
        if RFDETRSegSmall is None:
            raise PhoneSegmenterError("RFDETRSegSmall class not found in rfdetr package.")

        self._model = RFDETRSegSmall(
            pretrain_weights=str(self.model_path),
            num_classes=self.num_classes,
        )
        return self._model

    def predict_mask(self, image: Image) -> tuple[Image | None, float]:
        """Run segmentation model and return binary mask and confidence score."""
        model = self._load_model()
        bgr = image
        if image.ndim == 2:
            bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        elif image.shape[2] == 4:
            bgr = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

        detections = model.predict(bgr, threshold=self.confidence)
        if len(detections.xyxy) == 0 or detections.mask is None:
            return None, 0.0

        best_idx = int(np.argmax(detections.confidence))
        best_conf = float(detections.confidence[best_idx])
        raw_mask = detections.mask[best_idx]
        mask_uint8 = (raw_mask.astype(np.uint8) * 255)
        return mask_uint8, best_conf

    def segment_and_correct(self, image: Image) -> PhoneSegmentationResult:
        """End-to-end pipeline: segment phone -> extract 4 corners -> perspective correct."""
        timings: dict[str, float] = {}

        # Stage 1: Segmentation
        t0 = perf_counter()
        mask, conf = self.predict_mask(image)
        timings["segmentation_ms"] = (perf_counter() - t0) * 1000.0

        if mask is None:
            raise PhoneSegmenterError("No phone detected by the segmentation model.")

        # Stage 2: Corner extraction
        t0 = perf_counter()
        corners = extract_corners_from_mask(
            mask,
            image_shape=image.shape[:2],
            refine_edges=self.refine_edges,
        )
        timings["corner_extraction_ms"] = (perf_counter() - t0) * 1000.0

        if corners is None:
            raise PhoneSegmenterError(
                "Could not extract 4 quadrilateral corners from phone segmentation mask."
            )

        # Stage 3: Perspective correction
        t0 = perf_counter()
        persp_res = correct_perspective(image, corners)
        timings["perspective_ms"] = (perf_counter() - t0) * 1000.0
        timings["total_ms"] = sum(timings.values())

        # Stage 4: Visualizations
        corner_preview = draw_corners(image, corners)
        mask_overlay = make_mask_overlay(image, mask)
        before_after = make_before_after(corner_preview, persp_res.image)

        return PhoneSegmentationResult(
            image=image,
            mask=mask,
            confidence=conf,
            corners=corners,
            perspective_result=persp_res,
            corner_preview=corner_preview,
            mask_overlay=mask_overlay,
            before_after=before_after,
            timings_ms=timings,
        )


def detect_phone_corners_segmentation(
    image: Image,
    model_path: str | Path = "models/weights.pt",
    *,
    confidence: float = 0.25,
    refine_edges: bool = True,
) -> PointArray | None:
    """Convenience helper to extract phone corners using the trained segmentation model."""
    segmenter = PhoneSegmenter(
        model_path=model_path,
        confidence=confidence,
        refine_edges=refine_edges,
    )
    mask, _ = segmenter.predict_mask(image)
    if mask is None:
        return None
    return extract_corners_from_mask(
        mask,
        image_shape=image.shape[:2],
        refine_edges=refine_edges,
    )
