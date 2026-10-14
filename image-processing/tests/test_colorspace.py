import numpy as np
import pytest

from defect_vision.colorspace import (
    ColorSpaceError,
    analyze_color_space,
    compute_channel_stats,
    convert_color_space,
    evaluate_defect_contrast,
    extract_all_defect_channels,
    make_channel_comparison_grid,
    split_channels,
)


@pytest.fixture
def sample_bgr_image() -> np.ndarray:
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:50, :50] = (255, 0, 0)      # Blue patch
    img[:50, 50:] = (0, 255, 0)      # Green patch
    img[50:, :50] = (0, 0, 255)      # Red patch
    img[50:, 50:] = (128, 128, 128)  # Gray patch
    return img


def test_convert_color_space_supported_formats(sample_bgr_image: np.ndarray):
    hsv = convert_color_space(sample_bgr_image, "hsv")
    lab = convert_color_space(sample_bgr_image, "lab")
    gray = convert_color_space(sample_bgr_image, "gray")
    rgb = convert_color_space(sample_bgr_image, "rgb")

    assert hsv.shape == (100, 100, 3)
    assert lab.shape == (100, 100, 3)
    assert gray.shape == (100, 100)
    assert rgb.shape == (100, 100, 3)


def test_convert_color_space_invalid_space(sample_bgr_image: np.ndarray):
    with pytest.raises(ColorSpaceError, match="Unsupported color space"):
        convert_color_space(sample_bgr_image, "cmyk")  # type: ignore


def test_split_channels(sample_bgr_image: np.ndarray):
    hsv = convert_color_space(sample_bgr_image, "hsv")
    channels = split_channels(hsv, "hsv")
    assert set(channels.keys()) == {"H", "S", "V"}
    assert channels["H"].shape == (100, 100)


def test_compute_channel_stats():
    ch = np.array([[10, 20], [30, 40]], dtype=np.uint8)
    stats = compute_channel_stats(ch, "TestCh")
    assert stats.name == "TestCh"
    assert stats.min_val == 10
    assert stats.max_val == 40
    assert stats.dynamic_range == 30
    assert stats.mean == 25.0


def test_extract_all_defect_channels(sample_bgr_image: np.ndarray):
    channels = extract_all_defect_channels(sample_bgr_image)
    expected_channels = {"Gray", "H", "S", "V", "L", "A", "B_channel"}
    assert set(channels.keys()) == expected_channels
    for name, arr in channels.items():
        assert arr.shape == (100, 100)


def test_evaluate_defect_contrast():
    # Background: 50, Defect patch in center: 200
    ch = np.full((50, 50), 50, dtype=np.uint8)
    ch[20:30, 20:30] = 200

    mask = np.zeros((50, 50), dtype=np.uint8)
    mask[20:30, 20:30] = 255

    channels = {"Test": ch}
    metrics = evaluate_defect_contrast(channels, mask)

    assert "Test" in metrics
    m = metrics["Test"]
    assert m.defect_mean == 200.0
    assert m.bg_mean == 50.0
    assert m.michelson_contrast > 0
    assert m.cnr > 0


def test_evaluate_defect_contrast_invalid_mask():
    ch = np.full((50, 50), 50, dtype=np.uint8)
    empty_mask = np.zeros((50, 50), dtype=np.uint8)
    with pytest.raises(ColorSpaceError, match="must contain both defect"):
        evaluate_defect_contrast({"Test": ch}, empty_mask)


def test_make_channel_comparison_grid(sample_bgr_image: np.ndarray):
    channels = extract_all_defect_channels(sample_bgr_image)
    grid = make_channel_comparison_grid(sample_bgr_image, channels, tile_size=(100, 100))
    assert grid.ndim == 3
    assert grid.shape[2] == 3
    assert grid.shape[0] > 100
    assert grid.shape[1] > 100
