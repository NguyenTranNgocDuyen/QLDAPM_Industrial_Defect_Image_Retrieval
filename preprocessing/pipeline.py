"""The single source of truth for preprocessing at training and inference time."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from .enhancement import equalize_luminance
from .filtering import gaussian_filter, median_filter
from .normalize import normalize_pixels
from .resize import resize_image


@dataclass(frozen=True)
class PreprocessConfig:
    image_size: int = 224
    filter_name: str = "none"  # one of: none, gaussian, median
    filter_kernel: int = 5
    contrast_enhancement: bool = False
    clahe_clip_limit: float = 2.0
    clahe_tile_grid_size: int = 8
    normalization_mean: tuple[float, float, float] | None = None
    normalization_std: tuple[float, float, float] | None = None

    def __post_init__(self) -> None:
        if self.filter_name not in {"none", "gaussian", "median"}:
            raise ValueError("filter_name must be 'none', 'gaussian', or 'median'.")
        if self.image_size <= 0:
            raise ValueError("image_size must be positive.")
        if (self.normalization_mean is None) != (self.normalization_std is None):
            raise ValueError("normalization_mean and normalization_std must both be set or None.")
        if self.normalization_mean is not None:
            if len(self.normalization_mean) != 3 or len(self.normalization_std or ()) != 3:
                raise ValueError("normalization statistics must contain three RGB values.")


def preprocess_uint8(image: Image.Image, config: PreprocessConfig) -> np.ndarray:
    """Run deterministic image operations and return an RGB uint8 image.

    This boundary lets training compute train-only statistics without applying
    them, and lets the API time preprocessing independently of model inference.
    """
    result = np.asarray(resize_image(image, config.image_size), dtype=np.uint8)
    if config.filter_name == "gaussian":
        result = gaussian_filter(result, config.filter_kernel)
    elif config.filter_name == "median":
        result = median_filter(result, config.filter_kernel)
    if config.contrast_enhancement:
        result = equalize_luminance(
            result, config.clahe_clip_limit, config.clahe_tile_grid_size
        )
    return result


def preprocess_image(image: Image.Image, config: PreprocessConfig = PreprocessConfig()) -> np.ndarray:
    """Return deterministic RGB preprocessing followed by checkpoint normalization."""
    result = preprocess_uint8(image, config)
    return normalize_pixels(result, config.normalization_mean, config.normalization_std)
