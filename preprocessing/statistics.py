"""Train-split statistics for reproducible normalization."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from .pipeline import PreprocessConfig, preprocess_uint8


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def compute_train_mean_std(root: str | Path, config: PreprocessConfig) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Compute RGB mean/std after deterministic preprocessing, from train only."""
    paths = sorted(path for path in Path(root).rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES)
    if not paths:
        raise ValueError(f"No images found in training directory: {root}")
    pixel_sum = np.zeros(3, dtype=np.float64)
    squared_sum = np.zeros(3, dtype=np.float64)
    pixel_count = 0
    for path in paths:
        with Image.open(path) as image:
            array = preprocess_uint8(image, config).astype(np.float64) / 255.0
        flat = array.reshape(-1, 3)
        pixel_sum += flat.sum(axis=0)
        squared_sum += np.square(flat).sum(axis=0)
        pixel_count += len(flat)
    mean = pixel_sum / pixel_count
    variance = np.maximum(squared_sum / pixel_count - np.square(mean), 1e-12)
    return tuple(float(value) for value in mean), tuple(float(value) for value in np.sqrt(variance))
