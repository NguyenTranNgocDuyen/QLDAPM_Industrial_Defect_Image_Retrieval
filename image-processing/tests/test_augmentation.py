import numpy as np
import pytest

from defect_vision.augmentation import (
    AugmentationError,
    AugmentedSample,
    BoundingBox,
    add_gaussian_noise,
    adjust_brightness_contrast,
    apply_motion_blur,
    draw_bounding_boxes,
    generate_defect_augmentation_batch,
    horizontal_flip,
    make_augmentation_grid,
    rotate_image_and_boxes,
    vertical_flip,
)


@pytest.fixture
def sample_image_and_box() -> tuple[np.ndarray, list[BoundingBox]]:
    img = np.zeros((100, 200, 3), dtype=np.uint8)
    # Box located in the left half: xc=0.25, yc=0.5, w=0.2, h=0.2
    # In pixel coords: x in [30, 70], y in [40, 60]
    box = BoundingBox(class_id=0, x_center=0.25, y_center=0.5, width=0.2, height=0.2)
    return img, [box]


def test_bounding_box_conversions():
    box = BoundingBox(class_id=1, x_center=0.5, y_center=0.5, width=0.4, height=0.4)
    x1, y1, x2, y2 = box.to_pixels(100, 100)
    assert x1 == 30
    assert y1 == 30
    assert x2 == 70
    assert y2 == 70
    assert box.to_yolo_line() == "1 0.500000 0.500000 0.400000 0.400000"


def test_horizontal_flip(sample_image_and_box: tuple[np.ndarray, list[BoundingBox]]):
    img, boxes = sample_image_and_box
    res = horizontal_flip(img, boxes)
    assert res.image.shape == img.shape
    assert len(res.boxes) == 1
    # xc becomes 1.0 - 0.25 = 0.75
    assert pytest.approx(res.boxes[0].x_center, abs=1e-5) == 0.75
    assert pytest.approx(res.boxes[0].y_center, abs=1e-5) == 0.5


def test_vertical_flip(sample_image_and_box: tuple[np.ndarray, list[BoundingBox]]):
    img, boxes = sample_image_and_box
    res = vertical_flip(img, boxes)
    assert res.image.shape == img.shape
    assert len(res.boxes) == 1
    # yc becomes 1.0 - 0.5 = 0.5
    assert pytest.approx(res.boxes[0].y_center, abs=1e-5) == 0.5


def test_rotate_image_and_boxes(sample_image_and_box: tuple[np.ndarray, list[BoundingBox]]):
    img, boxes = sample_image_and_box
    res = rotate_image_and_boxes(img, boxes, angle_degrees=10.0)
    assert res.image.shape == img.shape
    assert len(res.boxes) == 1
    assert 0.0 <= res.boxes[0].x_center <= 1.0
    assert 0.0 <= res.boxes[0].y_center <= 1.0


def test_adjust_brightness_contrast(sample_image_and_box: tuple[np.ndarray, list[BoundingBox]]):
    img = np.full((50, 50, 3), 100, dtype=np.uint8)
    boxes = [BoundingBox(class_id=0, x_center=0.5, y_center=0.5, width=0.2, height=0.2)]
    res = adjust_brightness_contrast(img, boxes, alpha=1.0, beta=20)
    assert np.all(res.image == 120)
    assert res.boxes == boxes


def test_add_gaussian_noise(sample_image_and_box: tuple[np.ndarray, list[BoundingBox]]):
    img, boxes = sample_image_and_box
    res = add_gaussian_noise(img, boxes, sigma=5.0)
    assert res.image.shape == img.shape
    assert res.image.dtype == np.uint8


def test_apply_motion_blur(sample_image_and_box: tuple[np.ndarray, list[BoundingBox]]):
    img, boxes = sample_image_and_box
    res = apply_motion_blur(img, boxes, kernel_size=5)
    assert res.image.shape == img.shape
    with pytest.raises(AugmentationError):
        apply_motion_blur(img, boxes, kernel_size=4)  # Even kernel size


def test_generate_defect_augmentation_batch(sample_image_and_box: tuple[np.ndarray, list[BoundingBox]]):
    img, boxes = sample_image_and_box
    batch = generate_defect_augmentation_batch(img, boxes)
    assert len(batch) >= 7
    grid = make_augmentation_grid(batch, tile_size=(100, 100))
    assert grid.ndim == 3
