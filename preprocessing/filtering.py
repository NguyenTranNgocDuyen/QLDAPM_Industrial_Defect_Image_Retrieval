"""Noise-reduction filters. Select one filter experimentally, not both by default."""

from __future__ import annotations

import cv2
import numpy as np


def gaussian_filter(image: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    """Apply Gaussian blur with an odd positive kernel size."""
    _validate_kernel(kernel_size)
    return cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)


def median_filter(image: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    """Apply median filtering with an odd positive kernel size."""
    _validate_kernel(kernel_size)
    return cv2.medianBlur(image, kernel_size)


def _validate_kernel(kernel_size: int) -> None:
    if kernel_size < 3 or kernel_size % 2 == 0:
        raise ValueError("kernel_size must be an odd integer greater than or equal to 3.")
