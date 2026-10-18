"""Pixel value normalization."""

from __future__ import annotations

import numpy as np


def normalize_pixels(
    image: np.ndarray,
    mean: tuple[float, float, float] | None = None,
    std: tuple[float, float, float] | None = None,
) -> np.ndarray:
    """Scale RGB pixels and, when supplied, standardize with train statistics.

    ``mean`` and ``std`` are measured after the deterministic image operations
    and on the training split only.  Omitting both deliberately preserves the
    legacy ``[0, 1]`` behaviour used by older checkpoints.
    """
    result = image.astype(np.float32) / 255.0
    if (mean is None) != (std is None):
        raise ValueError("mean and std must either both be set or both be None.")
    if mean is None:
        return result
    mean_array = np.asarray(mean, dtype=np.float32).reshape(1, 1, 3)
    std_array = np.asarray(std, dtype=np.float32).reshape(1, 1, 3)
    if np.any(std_array <= 0):
        raise ValueError("normalization std values must be positive.")
    return (result - mean_array) / std_array
