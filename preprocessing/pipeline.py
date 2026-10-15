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

    def __post_init__(self) -> None:
        if self.filter_name not in {"none", "gaussian", "median"}:
            raise ValueError("filter_name must be 'none', 'gaussian', or 'median'.")


def preprocess_image(image: Image.Image, config: PreprocessConfig = PreprocessConfig()) -> np.ndarray:
    """Resize, optionally filter/enhance, then normalize an image to [0, 1] RGB."""
    result = np.asarray(resize_image(image, config.image_size), dtype=np.uint8)
    if config.filter_name == "gaussian":
        result = gaussian_filter(result, config.filter_kernel)
    elif config.filter_name == "median":
        result = median_filter(result, config.filter_kernel)
    if config.contrast_enhancement:
        result = equalize_luminance(result)
    return normalize_pixels(result)
