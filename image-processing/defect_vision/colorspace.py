"""Color space transformations and channel analysis for defect detection.

This module provides conversion between BGR, RGB, Grayscale, HSV, and LAB
color spaces, channel extraction, defect contrast analysis, and comparison
visualizations specifically tailored for electronic-device surface inspection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Literal

import cv2
import numpy as np
from numpy.typing import NDArray

Image = NDArray[np.uint8]
ColorSpaceName = Literal["bgr", "rgb", "gray", "hsv", "lab"]
SUPPORTED_COLOR_SPACES: tuple[ColorSpaceName, ...] = ("bgr", "rgb", "gray", "hsv", "lab")


class ColorSpaceError(ValueError):
    """Raised when color-space inputs or arguments are invalid."""


@dataclass(frozen=True)
class ChannelStats:
    """Statistical summary of a single color channel."""

    name: str
    mean: float
    std: float
    min_val: int
    max_val: int
    dynamic_range: int

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "name": self.name,
            "mean": round(float(self.mean), 4),
            "std": round(float(self.std), 4),
            "min_val": int(self.min_val),
            "max_val": int(self.max_val),
            "dynamic_range": int(self.dynamic_range),
        }


@dataclass(frozen=True)
class DefectContrastMetric:
    """Quantitative contrast between a defect region and its surrounding background.
    
    Weber contrast: (mean_defect - mean_bg) / (mean_bg + 1e-5)
    Michelson contrast: abs(mean_defect - mean_bg) / (mean_defect + mean_bg + 1e-5)
    CNR (Contrast-to-Noise Ratio): abs(mean_defect - mean_bg) / sqrt(std_defect^2 + std_bg^2 + 1e-5)
    """

    channel_name: str
    defect_mean: float
    bg_mean: float
    defect_std: float
    bg_std: float
    michelson_contrast: float
    weber_contrast: float
    cnr: float

    def to_dict(self) -> dict[str, float | str]:
        return {
            "channel_name": self.channel_name,
            "defect_mean": round(float(self.defect_mean), 4),
            "bg_mean": round(float(self.bg_mean), 4),
            "defect_std": round(float(self.defect_std), 4),
            "bg_std": round(float(self.bg_std), 4),
            "michelson_contrast": round(float(self.michelson_contrast), 4),
            "weber_contrast": round(float(self.weber_contrast), 4),
            "cnr": round(float(self.cnr), 4),
        }


@dataclass(frozen=True)
class ColorSpaceAnalysisResult:
    """Result of multi-color-space decomposition and channel statistics."""

    color_space: ColorSpaceName
    converted_image: Image
    channels: dict[str, Image]
    channel_stats: dict[str, ChannelStats]
    elapsed_ms: float


def _validate_image(image: Image) -> None:
    if not isinstance(image, np.ndarray) or image.size == 0:
        raise ColorSpaceError("Input image must be a non-empty numpy array.")
    if image.dtype != np.uint8:
        raise ColorSpaceError("Input image must have dtype uint8.")
    if image.ndim not in (2, 3):
        raise ColorSpaceError("Input image must be 2D (grayscale) or 3D (color).")
    if image.ndim == 3 and image.shape[2] not in (1, 3, 4):
        raise ColorSpaceError(f"Unsupported channel count: {image.shape[2]}. Expected 1, 3, or 4.")


def _ensure_bgr(image: Image) -> Image:
    """Normalize input image to 3-channel BGR."""
    _validate_image(image)
    if image.ndim == 2 or (image.ndim == 3 and image.shape[2] == 1):
        gray = image if image.ndim == 2 else image[:, :, 0]
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image.copy()


def convert_color_space(image: Image, target_space: ColorSpaceName) -> Image:
    """Convert a BGR (or grayscale) input image to the specified color space."""
    target_lower = target_space.lower()
    if target_lower not in SUPPORTED_COLOR_SPACES:
        raise ColorSpaceError(
            f"Unsupported color space: '{target_space}'. Must be one of {SUPPORTED_COLOR_SPACES}."
        )

    bgr = _ensure_bgr(image)

    if target_lower == "bgr":
        return bgr
    if target_lower == "rgb":
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    if target_lower == "gray":
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    if target_lower == "hsv":
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    if target_lower == "lab":
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)

    raise ColorSpaceError(f"Unhandled color space: '{target_space}'")


def compute_channel_stats(channel: Image, name: str) -> ChannelStats:
    """Calculate statistical distribution for a single 2D channel."""
    if channel.ndim != 2:
        raise ColorSpaceError("Channel must be a 2D array.")
    min_v, max_v = int(np.min(channel)), int(np.max(channel))
    return ChannelStats(
        name=name,
        mean=float(np.mean(channel)),
        std=float(np.std(channel)),
        min_val=min_v,
        max_val=max_v,
        dynamic_range=max_v - min_v,
    )


def split_channels(image: Image, space_name: ColorSpaceName) -> dict[str, Image]:
    """Split an image into its individual 2D channels with meaningful names."""
    space_lower = space_name.lower()
    if space_lower == "gray":
        if image.ndim == 3 and image.shape[2] == 1:
            return {"Gray": image[:, :, 0]}
        return {"Gray": image}

    if image.ndim != 3 or image.shape[2] != 3:
        raise ColorSpaceError(f"Expected 3-channel image for space '{space_name}'.")

    channel_names: dict[str, tuple[str, str, str]] = {
        "bgr": ("B", "G", "R"),
        "rgb": ("R", "G", "B"),
        "hsv": ("H", "S", "V"),
        "lab": ("L", "A", "B_channel"),
    }
    names = channel_names.get(space_lower)
    if not names:
        raise ColorSpaceError(f"Unsupported 3-channel space: '{space_name}'")

    c0, c1, c2 = cv2.split(image)
    return {names[0]: c0, names[1]: c1, names[2]: c2}


def analyze_color_space(image: Image, target_space: ColorSpaceName) -> ColorSpaceAnalysisResult:
    """Convert an image to a target color space and compute per-channel distributions."""
    start = perf_counter()
    converted = convert_color_space(image, target_space)
    channels = split_channels(converted, target_space)
    stats = {name: compute_channel_stats(ch, name) for name, ch in channels.items()}
    elapsed_ms = (perf_counter() - start) * 1000.0

    return ColorSpaceAnalysisResult(
        color_space=target_space,
        converted_image=converted,
        channels=channels,
        channel_stats=stats,
        elapsed_ms=round(elapsed_ms, 3),
    )


def extract_all_defect_channels(image: Image) -> dict[str, Image]:
    """Extract standard single channels from BGR, HSV, and LAB spaces for defect detection.

    Returns a dictionary of:
    - 'Gray': Standard grayscale luminance
    - 'H': Hue (color tone)
    - 'S': Saturation (color intensity/purity)
    - 'V': Value (brightness in HSV)
    - 'L': Lightness (perceptual luminance in LAB)
    - 'A': Green-to-Red opponent channel
    - 'B_channel': Blue-to-Yellow opponent channel
    """
    bgr = _ensure_bgr(image)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)

    h, s, v = cv2.split(hsv)
    l, a, b_ch = cv2.split(lab)

    return {
        "Gray": gray,
        "H": h,
        "S": s,
        "V": v,
        "L": l,
        "A": a,
        "B_channel": b_ch,
    }


def evaluate_defect_contrast(
    channels: dict[str, Image],
    defect_mask: Image,
) -> dict[str, DefectContrastMetric]:
    """Quantitatively compare contrast metrics for a defect region across multiple channels.

    defect_mask: 2D binary uint8 mask where 255 indicates defect pixels, 0 is background.
    """
    if defect_mask.ndim != 2:
        raise ColorSpaceError("defect_mask must be a 2D binary mask.")

    defect_bool = defect_mask > 0
    bg_bool = ~defect_bool

    defect_count = int(np.count_nonzero(defect_bool))
    bg_count = int(np.count_nonzero(bg_bool))

    if defect_count == 0 or bg_count == 0:
        raise ColorSpaceError("defect_mask must contain both defect (>0) and background (0) pixels.")

    metrics: dict[str, DefectContrastMetric] = {}

    for name, channel in channels.items():
        if channel.shape != defect_mask.shape:
            raise ColorSpaceError(
                f"Channel '{name}' shape {channel.shape} does not match mask shape {defect_mask.shape}."
            )

        defect_pixels = channel[defect_bool].astype(np.float64)
        bg_pixels = channel[bg_bool].astype(np.float64)

        d_mean, d_std = float(np.mean(defect_pixels)), float(np.std(defect_pixels))
        b_mean, b_std = float(np.mean(bg_pixels)), float(np.std(bg_pixels))

        michelson = abs(d_mean - b_mean) / (d_mean + b_mean + 1e-5)
        weber = (d_mean - b_mean) / (b_mean + 1e-5)
        cnr = abs(d_mean - b_mean) / float(np.sqrt(d_std**2 + b_std**2 + 1e-5))

        metrics[name] = DefectContrastMetric(
            channel_name=name,
            defect_mean=d_mean,
            bg_mean=b_mean,
            defect_std=d_std,
            bg_std=b_std,
            michelson_contrast=michelson,
            weber_contrast=weber,
            cnr=cnr,
        )

    return metrics


def make_channel_comparison_grid(
    original_bgr: Image,
    channels: dict[str, Image],
    metrics: dict[str, DefectContrastMetric] | None = None,
    tile_size: tuple[int, int] = (280, 280),
) -> Image:
    """Create a multi-tile visual overview comparing original BGR with extracted channels.

    Includes CNR (Contrast-to-Noise Ratio) overlays if metrics are supplied.
    """
    bgr = _ensure_bgr(original_bgr)
    w_t, h_t = tile_size

    tiles: list[tuple[str, Image]] = [("Original BGR", cv2.resize(bgr, (w_t, h_t)))]

    for name, ch in channels.items():
        ch_resized = cv2.resize(ch, (w_t, h_t))
        ch_bgr = cv2.cvtColor(ch_resized, cv2.COLOR_GRAY2BGR)

        label = name
        if metrics and name in metrics:
            m = metrics[name]
            label = f"{name} (CNR: {m.cnr:.2f})"

        tiles.append((label, ch_bgr))

    # Layout: arrange tiles into a grid of 4 columns
    cols = 4
    rows = (len(tiles) + cols - 1) // cols

    blank_tile = np.zeros((h_t, w_t, 3), dtype=np.uint8)
    row_images: list[Image] = []

    for r in range(rows):
        cur_row: list[Image] = []
        for c in range(cols):
            idx = r * cols + c
            if idx < len(tiles):
                title, tile_img = tiles[idx]
                annotated = tile_img.copy()
                # Draw header banner
                cv2.rectangle(annotated, (0, 0), (w_t, 26), (20, 20, 20), -1)
                cv2.putText(
                    annotated,
                    title,
                    (6, 18),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )
                cur_row.append(annotated)
            else:
                cur_row.append(blank_tile)
        row_images.append(np.hstack(cur_row))

    return np.vstack(row_images)
