"""Pixel value normalization."""

from __future__ import annotations

import numpy as np


def normalize_pixels(image: np.ndarray) -> np.ndarray:
    """Convert uint8 RGB pixels in [0, 255] to float32 pixels in [0, 1]."""
    return image.astype(np.float32) / 255.0
