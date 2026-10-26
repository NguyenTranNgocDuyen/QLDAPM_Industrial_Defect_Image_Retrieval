from __future__ import annotations

import unittest

import cv2
import numpy as np

from defect_vision.perspective import (
    PerspectiveCorrectionError,
    correct_perspective,
    order_corners,
)


class OrderCornersTests(unittest.TestCase):
    def test_orders_random_input_clockwise_from_top_left(self) -> None:
        random_order = [(300, 200), (40, 30), (30, 210), (320, 20)]

        result = order_corners(random_order)

        expected = np.array(
            [[40, 30], [320, 20], [300, 200], [30, 210]], dtype=np.float32
        )
        np.testing.assert_array_equal(result, expected)

    def test_rejects_duplicate_points(self) -> None:
        with self.assertRaises(PerspectiveCorrectionError):
            order_corners([(0, 0), (10, 0), (10, 0), (0, 10)])

    def test_rejects_non_convex_points(self) -> None:
        with self.assertRaises(PerspectiveCorrectionError):
            order_corners([(0, 0), (20, 0), (10, 5), (0, 20)])


class CorrectPerspectiveTests(unittest.TestCase):
    def test_rectifies_a_synthetic_quadrilateral(self) -> None:
        front = np.zeros((180, 300, 3), dtype=np.uint8)
        front[:] = (180, 180, 180)
        cv2.rectangle(front, (0, 0), (299, 179), (255, 255, 255), 4)
        cv2.line(front, (40, 130), (250, 90), (0, 0, 255), 3)

        source = np.array(
            [[0, 0], [299, 0], [299, 179], [0, 179]], dtype=np.float32
        )
        target = np.array(
            [[60, 35], [360, 55], [335, 250], [40, 220]], dtype=np.float32
        )
        matrix = cv2.getPerspectiveTransform(source, target)
        perspective_view = cv2.warpPerspective(front, matrix, (420, 290))

        result = correct_perspective(perspective_view, target)

        self.assertGreaterEqual(result.output_width, 300)
        self.assertGreaterEqual(result.output_height, 180)
        self.assertEqual(
            result.image.shape[:2], (result.output_height, result.output_width)
        )
        self.assertGreater(float(result.image.mean()), 100.0)
        self.assertGreaterEqual(result.elapsed_ms, 0.0)

    def test_does_not_modify_source_image(self) -> None:
        image = np.full((100, 200, 3), 120, dtype=np.uint8)
        original = image.copy()

        correct_perspective(image, [(0, 0), (199, 0), (199, 99), (0, 99)])

        np.testing.assert_array_equal(image, original)

    def test_rejects_points_outside_image(self) -> None:
        image = np.zeros((100, 100, 3), dtype=np.uint8)

        with self.assertRaises(PerspectiveCorrectionError):
            correct_perspective(image, [(-1, 0), (99, 0), (99, 99), (0, 99)])

    def test_detect_device_corners_finds_quad(self) -> None:
        from defect_vision.demo import create_perspective_view
        from defect_vision.perspective import detect_device_corners

        image, true_corners = create_perspective_view()
        detected = detect_device_corners(image)

        self.assertIsNotNone(detected)
        self.assertEqual(detected.shape, (4, 2))

    def test_detect_device_corners_returns_none_for_flat_image(self) -> None:
        from defect_vision.perspective import detect_device_corners

        flat = np.full((100, 100, 3), 128, dtype=np.uint8)
        self.assertIsNone(detect_device_corners(flat))


if __name__ == "__main__":
    unittest.main()

