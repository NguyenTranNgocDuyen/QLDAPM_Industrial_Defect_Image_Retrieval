from __future__ import annotations

import unittest

import numpy as np

from defect_vision.illumination import (
    IlluminationCorrectionError,
    analyze_luminance,
    background_correction,
    clahe_correction,
    correct_illumination,
    gamma_correction,
)


class GammaCorrectionTests(unittest.TestCase):
    def test_auto_gamma_brightens_dark_image(self) -> None:
        image = np.full((80, 120, 3), 45, dtype=np.uint8)

        corrected, gamma = gamma_correction(image)

        self.assertLess(gamma, 1.0)
        self.assertGreater(analyze_luminance(corrected).mean, 100.0)

    def test_gamma_above_one_darkens_image(self) -> None:
        image = np.full((60, 80), 190, dtype=np.uint8)

        corrected, gamma = gamma_correction(image, 1.6)

        self.assertEqual(gamma, 1.6)
        self.assertLess(float(corrected.mean()), float(image.mean()))

    def test_rejects_invalid_gamma(self) -> None:
        image = np.full((20, 20), 100, dtype=np.uint8)

        with self.assertRaises(IlluminationCorrectionError):
            gamma_correction(image, 0)


class LocalCorrectionTests(unittest.TestCase):
    def test_clahe_increases_low_local_contrast(self) -> None:
        image = np.full((128, 128), 110, dtype=np.uint8)
        image[32:96, 32:96] = 118

        corrected = clahe_correction(image, clip_limit=2.0, grid_size=8)

        self.assertGreater(float(corrected.std()), float(image.std()))

    def test_background_correction_reduces_slow_gradient(self) -> None:
        gradient = np.linspace(45, 210, 320, dtype=np.float32)
        image = np.tile(gradient, (180, 1)).astype(np.uint8)

        corrected = background_correction(image, kernel_size=81)

        before_variation = float(image.mean(axis=0).std())
        after_variation = float(corrected.mean(axis=0).std())
        self.assertLess(after_variation, before_variation * 0.35)

    def test_rejects_even_background_kernel(self) -> None:
        image = np.full((40, 40), 100, dtype=np.uint8)

        with self.assertRaises(IlluminationCorrectionError):
            background_correction(image, kernel_size=20)


class IlluminationPipelineTests(unittest.TestCase):
    def test_combined_preserves_shape_and_source(self) -> None:
        image = np.full((90, 140, 3), (80, 100, 120), dtype=np.uint8)
        original = image.copy()

        result = correct_illumination(
            image, "combined", background_kernel=31, grid_size=4
        )

        self.assertEqual(result.image.shape, image.shape)
        np.testing.assert_array_equal(image, original)
        self.assertGreaterEqual(result.elapsed_ms, 0.0)

    def test_preserves_alpha_channel(self) -> None:
        image = np.zeros((50, 60, 4), dtype=np.uint8)
        image[:, :, :3] = 70
        image[:, :, 3] = np.arange(60, dtype=np.uint8)[None, :]

        result = correct_illumination(image, "gamma")

        np.testing.assert_array_equal(result.image[:, :, 3], image[:, :, 3])

    def test_rejects_unknown_method(self) -> None:
        image = np.full((20, 20), 100, dtype=np.uint8)

        with self.assertRaises(IlluminationCorrectionError):
            correct_illumination(image, "retinex")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
