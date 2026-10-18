"""Contrast enhancement operations."""

from __future__ import annotations

import cv2
import numpy as np


def equalize_luminance(
    image: np.ndarray, clip_limit: float = 2.0, tile_grid_size: int = 8
) -> np.ndarray:
    """Apply CLAHE to luminance only, preserving RGB chroma information."""
    if clip_limit <= 0:
        raise ValueError("clip_limit must be positive.")
    if tile_grid_size < 2:
        raise ValueError("tile_grid_size must be at least 2.")
    ycrcb = cv2.cvtColor(image, cv2.COLOR_RGB2YCrCb)
    clahe = cv2.createCLAHE(
        clipLimit=clip_limit, tileGridSize=(tile_grid_size, tile_grid_size)
    )
    ycrcb[:, :, 0] = clahe.apply(ycrcb[:, :, 0])
    return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2RGB)
