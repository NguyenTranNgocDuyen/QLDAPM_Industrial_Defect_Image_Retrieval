"""Data augmentation module for electronic-device surface defect detection.

Supports spatial transformations (flips, slight rotations, scaling, affine)
with synchronized bounding box transformation (normalized xywh format for YOLO),
and pixel-level perturbations (brightness, contrast, Gaussian noise, blur).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Sequence

import cv2
import numpy as np
from numpy.typing import NDArray

Image = NDArray[np.uint8]


class AugmentationError(ValueError):
    """Raised when augmentation parameters or input formats are invalid."""


@dataclass(frozen=True)
class BoundingBox:
    """YOLO format bounding box with class label and normalized coordinates.
    
    class_id: integer identifier for class
    x_center: normalized center x in [0.0, 1.0]
    y_center: normalized center y in [0.0, 1.0]
    width: normalized box width in [0.0, 1.0]
    height: normalized box height in [0.0, 1.0]
    """

    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            "class_id": self.class_id,
            "x_center": round(float(self.x_center), 6),
            "y_center": round(float(self.y_center), 6),
            "width": round(float(self.width), 6),
            "height": round(float(self.height), 6),
        }

    def to_yolo_line(self) -> str:
        return f"{self.class_id} {self.x_center:.6f} {self.y_center:.6f} {self.width:.6f} {self.height:.6f}"

    def to_pixels(self, img_w: int, img_h: int) -> tuple[int, int, int, int]:
        """Convert to pixel coordinates (x1, y1, x2, y2)."""
        xc = self.x_center * img_w
        yc = self.y_center * img_h
        bw = self.width * img_w
        bh = self.height * img_h
        x1 = max(0, int(round(xc - bw / 2)))
        y1 = max(0, int(round(yc - bh / 2)))
        x2 = min(img_w - 1, int(round(xc + bw / 2)))
        y2 = min(img_h - 1, int(round(yc + bh / 2)))
        return x1, y1, x2, y2


@dataclass(frozen=True)
class AugmentedSample:
    """Result of an augmentation transformation on an image and its boxes."""

    image: Image
    boxes: list[BoundingBox]
    transform_name: str


def _validate_image(image: Image) -> None:
    if not isinstance(image, np.ndarray) or image.size == 0:
        raise AugmentationError("Input image must be a non-empty numpy array.")
    if image.dtype != np.uint8:
        raise AugmentationError("Input image must have dtype uint8.")
    if image.ndim not in (2, 3):
        raise AugmentationError("Input image must be 2D (grayscale) or 3D (color).")


def _clip_box(x_min: float, y_min: float, x_max: float, y_max: float, class_id: int) -> BoundingBox | None:
    """Clips box to [0.0, 1.0] and returns BoundingBox if valid area remains."""
    x1 = max(0.0, min(1.0, x_min))
    y1 = max(0.0, min(1.0, y_min))
    x2 = max(0.0, min(1.0, x_max))
    y2 = max(0.0, min(1.0, y_max))

    w = x2 - x1
    h = y2 - y1

    # Filter out collapsed boxes
    if w <= 0.005 or h <= 0.005:
        return None

    xc = x1 + w / 2.0
    yc = y1 + h / 2.0
    return BoundingBox(class_id=class_id, x_center=xc, y_center=yc, width=w, height=h)


# ==========================================
# 1. SPATIAL AUGMENTATIONS (Synchronized with BBoxes)
# ==========================================

def horizontal_flip(image: Image, boxes: Sequence[BoundingBox]) -> AugmentedSample:
    """Horizontally mirror the image and adjust x_center coordinates."""
    _validate_image(image)
    flipped_img = cv2.flip(image, 1)

    new_boxes: list[BoundingBox] = []
    for b in boxes:
        new_xc = 1.0 - b.x_center
        new_boxes.append(
            BoundingBox(
                class_id=b.class_id,
                x_center=new_xc,
                y_center=b.y_center,
                width=b.width,
                height=b.height,
            )
        )
    return AugmentedSample(image=flipped_img, boxes=new_boxes, transform_name="horizontal_flip")


def vertical_flip(image: Image, boxes: Sequence[BoundingBox]) -> AugmentedSample:
    """Vertically mirror the image and adjust y_center coordinates."""
    _validate_image(image)
    flipped_img = cv2.flip(image, 0)

    new_boxes: list[BoundingBox] = []
    for b in boxes:
        new_yc = 1.0 - b.y_center
        new_boxes.append(
            BoundingBox(
                class_id=b.class_id,
                x_center=b.x_center,
                y_center=new_yc,
                width=b.width,
                height=b.height,
            )
        )
    return AugmentedSample(image=flipped_img, boxes=new_boxes, transform_name="vertical_flip")


def rotate_image_and_boxes(
    image: Image,
    boxes: Sequence[BoundingBox],
    angle_degrees: float,
) -> AugmentedSample:
    """Rotate image by an angle with bounding boxes recomputed from transformed 4 corners."""
    _validate_image(image)
    h, w = image.shape[:2]
    center = (w / 2.0, h / 2.0)

    rot_mat = cv2.getRotationMatrix2D(center, angle_degrees, 1.0)
    rotated_img = cv2.warpAffine(
        image,
        rot_mat,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT101,
    )

    new_boxes: list[BoundingBox] = []
    for b in boxes:
        # 4 corners in pixel space
        px1, py1, px2, py2 = b.to_pixels(w, h)
        corners = np.array(
            [
                [px1, py1],
                [px2, py1],
                [px2, py2],
                [px1, py2],
            ],
            dtype=np.float32,
        )

        # Apply affine transformation to corners
        transformed_corners = cv2.transform(corners.reshape(-1, 1, 2), rot_mat).reshape(-1, 2)

        # Normalized coordinates of enclosing rectangle
        norm_xs = transformed_corners[:, 0] / w
        norm_ys = transformed_corners[:, 1] / h

        x_min, x_max = float(np.min(norm_xs)), float(np.max(norm_xs))
        y_min, y_max = float(np.min(norm_ys)), float(np.max(norm_ys))

        clipped = _clip_box(x_min, y_min, x_max, y_max, b.class_id)
        if clipped:
            new_boxes.append(clipped)

    return AugmentedSample(
        image=rotated_img,
        boxes=new_boxes,
        transform_name=f"rotate_{int(angle_degrees)}deg",
    )


# ==========================================
# 2. PIXEL-LEVEL AUGMENTATIONS (Boxes Unchanged)
# ==========================================

def adjust_brightness_contrast(
    image: Image,
    boxes: Sequence[BoundingBox],
    alpha: float = 1.0,  # contrast multiplier
    beta: int = 0,       # brightness offset
) -> AugmentedSample:
    """Simulate variations in ambient lighting and camera exposure."""
    _validate_image(image)
    adjusted = cv2.convertScaleAbs(image, alpha=alpha, beta=beta)
    return AugmentedSample(
        image=adjusted,
        boxes=list(boxes),
        transform_name=f"brightness_contrast_a{alpha:.2f}_b{beta}",
    )


def add_gaussian_noise(
    image: Image,
    boxes: Sequence[BoundingBox],
    mean: float = 0.0,
    sigma: float = 12.0,
) -> AugmentedSample:
    """Simulate electronic camera sensor noise."""
    _validate_image(image)
    noise = np.random.normal(mean, sigma, image.shape).astype(np.float32)
    noisy_img = np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    return AugmentedSample(
        image=noisy_img,
        boxes=list(boxes),
        transform_name=f"gaussian_noise_s{int(sigma)}",
    )


def apply_motion_blur(
    image: Image,
    boxes: Sequence[BoundingBox],
    kernel_size: int = 5,
) -> AugmentedSample:
    """Simulate camera movement or vibration during production line scanning."""
    _validate_image(image)
    if kernel_size % 2 == 0 or kernel_size < 3:
        raise AugmentationError("kernel_size must be an odd integer >= 3.")

    kernel = np.zeros((kernel_size, kernel_size), dtype=np.float32)
    # Diagonal motion blur kernel
    np.fill_diagonal(kernel, 1.0 / kernel_size)
    blurred = cv2.filter2D(image, -1, kernel)

    return AugmentedSample(
        image=blurred,
        boxes=list(boxes),
        transform_name=f"motion_blur_k{kernel_size}",
    )


# ==========================================
# 3. PIPELINE & VISUALIZATION
# ==========================================

def generate_defect_augmentation_batch(
    image: Image,
    boxes: Sequence[BoundingBox],
) -> list[AugmentedSample]:
    """Generate a standard realistic augmentation batch for electronic defect inspection.

    Includes:
    - Original baseline
    - Horizontal flip (devices can be scanned left-to-right or right-to-left)
    - Vertical flip (devices upside down)
    - Slight rotation (+8 deg, -8 deg for handheld camera tilt)
    - Low lighting simulation (darker)
    - High lighting simulation (brighter exposure)
    - Sensor noise
    - Motion blur
    """
    batch = [
        AugmentedSample(image=image.copy(), boxes=list(boxes), transform_name="original"),
        horizontal_flip(image, boxes),
        vertical_flip(image, boxes),
        rotate_image_and_boxes(image, boxes, angle_degrees=8.0),
        rotate_image_and_boxes(image, boxes, angle_degrees=-8.0),
        adjust_brightness_contrast(image, boxes, alpha=0.85, beta=-25),  # Underexposed
        adjust_brightness_contrast(image, boxes, alpha=1.15, beta=30),   # Overexposed
        add_gaussian_noise(image, boxes, sigma=10.0),
        apply_motion_blur(image, boxes, kernel_size=5),
    ]
    return batch


def draw_bounding_boxes(
    image: Image,
    boxes: Sequence[BoundingBox],
    class_names: dict[int, str] | None = None,
) -> Image:
    """Draw bounding boxes with label tags on the image for visual verification."""
    annotated = image.copy()
    if annotated.ndim == 2:
        annotated = cv2.cvtColor(annotated, cv2.COLOR_GRAY2BGR)

    h, w = annotated.shape[:2]
    colors = [
        (0, 0, 255),    # Red
        (0, 255, 0),    # Green
        (255, 128, 0),  # Orange
        (255, 0, 255),  # Magenta
    ]

    for b in boxes:
        x1, y1, x2, y2 = b.to_pixels(w, h)
        color = colors[b.class_id % len(colors)]
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        c_name = class_names.get(b.class_id, f"class_{b.class_id}") if class_names else f"class_{b.class_id}"
        label_text = f"{c_name}"

        (lw, lh), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        tag_y1 = max(0, y1 - lh - 4)
        tag_y2 = y1
        cv2.rectangle(annotated, (x1, tag_y1), (x1 + lw + 4, tag_y2), color, -1)
        cv2.putText(
            annotated,
            label_text,
            (x1 + 2, tag_y2 - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    return annotated


def make_augmentation_grid(
    samples: Sequence[AugmentedSample],
    class_names: dict[int, str] | None = None,
    tile_size: tuple[int, int] = (260, 260),
    cols: int = 3,
) -> Image:
    """Assemble augmented samples with their bounding boxes into a comparison grid."""
    w_t, h_t = tile_size
    tiles: list[Image] = []

    for s in samples:
        drawn = draw_bounding_boxes(s.image, s.boxes, class_names)
        resized = cv2.resize(drawn, (w_t, h_t))

        # Title bar
        cv2.rectangle(resized, (0, 0), (w_t, 24), (25, 25, 25), -1)
        cv2.putText(
            resized,
            s.transform_name,
            (6, 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        tiles.append(resized)

    rows = (len(tiles) + cols - 1) // cols
    blank_tile = np.zeros((h_t, w_t, 3), dtype=np.uint8)
    row_images: list[Image] = []

    for r in range(rows):
        cur_row: list[Image] = []
        for c in range(cols):
            idx = r * cols + c
            if idx < len(tiles):
                cur_row.append(tiles[idx])
            else:
                cur_row.append(blank_tile)
        row_images.append(np.hstack(cur_row))

    return np.vstack(row_images)
