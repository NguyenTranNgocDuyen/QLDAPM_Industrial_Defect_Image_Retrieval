"""Validated offline filters that preserve uint8 image layout."""
from __future__ import annotations

import cv2
import numpy as np


def _image(image: np.ndarray) -> np.ndarray:
    if not isinstance(image, np.ndarray) or image.size == 0 or image.dtype != np.uint8:
        raise ValueError("image must be a non-empty uint8 numpy array")
    if image.ndim not in (2, 3) or image.ndim == 3 and image.shape[2] not in (1, 3, 4):
        raise ValueError("image must be grayscale, BGR/RGB, or BGRA/RGBA")
    return image


def _kernel(kernel_size: int, *, minimum: int = 1) -> None:
    if isinstance(kernel_size, bool) or not isinstance(kernel_size, int) or kernel_size < minimum or kernel_size % 2 == 0:
        raise ValueError(f"kernel_size must be an odd integer >= {minimum}")


def gaussian_filter(image: np.ndarray, kernel_size: int = 5, sigma: float = 1.0) -> np.ndarray:
    """Apply Gaussian blur, leaving an alpha channel untouched."""
    image = _image(image); _kernel(kernel_size)
    if not isinstance(sigma, (int, float)) or isinstance(sigma, bool) or sigma <= 0:
        raise ValueError("sigma must be positive")
    if image.ndim == 3 and image.shape[2] == 4:
        return np.dstack((cv2.GaussianBlur(image[..., :3], (kernel_size, kernel_size), sigma), image[..., 3]))
    return cv2.GaussianBlur(image, (kernel_size, kernel_size), sigma)


def median_filter(image: np.ndarray, kernel_size: int = 3) -> np.ndarray:
    """Apply median blur with an odd kernel of at least three pixels."""
    image = _image(image); _kernel(kernel_size, minimum=3)
    if image.ndim == 3 and image.shape[2] == 4:
        return np.dstack((cv2.medianBlur(image[..., :3], kernel_size), image[..., 3]))
    return cv2.medianBlur(image, kernel_size)
