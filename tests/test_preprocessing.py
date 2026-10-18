from __future__ import annotations

import numpy as np
from PIL import Image

from preprocessing.enhancement import equalize_luminance
from preprocessing.pipeline import PreprocessConfig, preprocess_image, preprocess_uint8
from preprocessing.statistics import compute_train_mean_std


def test_preprocessing_applies_train_statistics() -> None:
    image = Image.fromarray(np.full((12, 10, 3), 128, dtype=np.uint8), "RGB")
    config = PreprocessConfig(image_size=8, normalization_mean=(0.5, 0.5, 0.5), normalization_std=(0.25, 0.25, 0.25))
    result = preprocess_image(image, config)
    assert result.shape == (8, 8, 3)
    assert result.dtype == np.float32
    assert np.allclose(result, (128 / 255 - 0.5) / 0.25)


def test_clahe_and_uint8_pipeline_keep_rgb_uint8() -> None:
    gradient = np.tile(np.arange(32, dtype=np.uint8), (32, 1))
    rgb = np.stack([gradient, gradient, gradient], axis=-1)
    enhanced = equalize_luminance(rgb)
    result = preprocess_uint8(Image.fromarray(rgb, "RGB"), PreprocessConfig(image_size=16, contrast_enhancement=True))
    assert enhanced.shape == rgb.shape
    assert enhanced.dtype == np.uint8
    assert result.shape == (16, 16, 3)


def test_train_statistics_use_only_provided_train_directory(tmp_path) -> None:
    (tmp_path / "normal").mkdir()
    Image.fromarray(np.zeros((4, 4, 3), dtype=np.uint8)).save(tmp_path / "normal" / "black.png")
    mean, std = compute_train_mean_std(tmp_path, PreprocessConfig(image_size=4))
    assert mean == (0.0, 0.0, 0.0)
    assert all(value > 0 for value in std)
