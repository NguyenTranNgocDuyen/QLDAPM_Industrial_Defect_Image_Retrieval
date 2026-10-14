import numpy as np
import pytest

from defect_vision.comparison import (
    ComparisonError,
    ImageQualityMetrics,
    compute_defect_cnr,
    compute_entropy,
    compute_image_quality_metrics,
    compute_tenengrad,
    estimate_background_noise,
    evaluate_enhancement_pair,
    make_before_after_comparison_board,
)


@pytest.fixture
def sample_pair() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    orig = np.full((100, 100), 50, dtype=np.uint8)
    orig[40:60, 40:60] = 70  # Faint defect

    enh = np.full((100, 100), 50, dtype=np.uint8)
    enh[40:60, 40:60] = 150  # Enhanced defect

    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[40:60, 40:60] = 255

    return orig, enh, mask


def test_compute_entropy():
    # Uniform image -> zero entropy
    uniform = np.full((50, 50), 100, dtype=np.uint8)
    assert compute_entropy(uniform) == pytest.approx(0.0, abs=1e-5)

    # Random noise -> high entropy
    noisy = np.random.randint(0, 256, (50, 50), dtype=np.uint8)
    assert compute_entropy(noisy) > 5.0


def test_compute_tenengrad():
    flat = np.full((50, 50), 100, dtype=np.uint8)
    assert compute_tenengrad(flat) == 0.0

    # Step edge
    edge = np.zeros((50, 50), dtype=np.uint8)
    edge[:, 25:] = 255
    assert compute_tenengrad(edge) > 0.0


def test_compute_defect_cnr(sample_pair: tuple[np.ndarray, np.ndarray, np.ndarray]):
    orig, enh, mask = sample_pair
    cnr_orig = compute_defect_cnr(orig, mask)
    cnr_enh = compute_defect_cnr(enh, mask)
    assert cnr_enh > cnr_orig


def test_evaluate_enhancement_pair(sample_pair: tuple[np.ndarray, np.ndarray, np.ndarray]):
    orig, enh, mask = sample_pair
    record = evaluate_enhancement_pair(
        original=orig,
        enhanced=enh,
        technique_name="TestEnhancement",
        elapsed_ms=5.2,
        defect_mask=mask,
    )
    assert record.technique_name == "TestEnhancement"
    assert record.contrast_gain_ratio > 1.0
    assert record.defect_cnr_after > record.defect_cnr_before
    assert "Beneficial" in record.recommendation


def test_make_before_after_comparison_board(sample_pair: tuple[np.ndarray, np.ndarray, np.ndarray]):
    orig, enh, mask = sample_pair
    record = evaluate_enhancement_pair(orig, enh, "Test", defect_mask=mask)
    board = make_before_after_comparison_board(orig, enh, record, tile_size=(100, 100))
    assert board.ndim == 3
    assert board.shape[2] == 3
    assert board.shape[1] == 200
    assert board.shape[0] > 100
