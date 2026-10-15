from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from defect_vision.pipeline import (
    PipelineConfig,
    PipelineError,
    PipelineResult,
    run_preprocessing_pipeline,
    save_pipeline_artifacts,
)


def _make_sample_image() -> np.ndarray:
    img = np.full((120, 160, 3), 70, dtype=np.uint8)
    cv2.rectangle(img, (20, 20), (140, 100), (150, 150, 150), -1)
    cv2.line(img, (30, 30), (130, 90), (230, 230, 230), 2)
    return img


def test_pipeline_basic_execution() -> None:
    img = _make_sample_image()
    config = PipelineConfig(illumination_method="clahe")
    result = run_preprocessing_pipeline(img, config=config)

    assert isinstance(result, PipelineResult)
    assert result.preprocessed_image.shape == img.shape
    assert result.illumination_result is not None
    assert result.illumination_result.method == "clahe"
    assert result.perspective_result is None
    assert "total_pipeline_ms" in result.timings_ms
    assert result.comparison_record.contrast_gain_ratio > 0


def test_pipeline_with_perspective() -> None:
    img = _make_sample_image()
    corners = [(10.0, 10.0), (150.0, 15.0), (145.0, 105.0), (12.0, 95.0)]
    config = PipelineConfig(
        points=corners,
        illumination_method="gamma",
        gamma=1.2,
    )
    result = run_preprocessing_pipeline(img, config=config)

    assert result.perspective_result is not None
    assert result.perspective_result.output_width > 0
    assert result.illumination_result is not None
    assert result.illumination_result.method == "gamma"


def test_pipeline_with_mock_yolo() -> None:
    img = _make_sample_image()
    config = PipelineConfig(
        illumination_method="combined",
        run_yolo=True,
        mock_yolo=True,
    )
    result = run_preprocessing_pipeline(img, config=config)

    assert result.yolo_result is not None
    assert result.yolo_annotated_image is not None
    assert "detections" in result.yolo_result


def test_save_pipeline_artifacts() -> None:
    img = _make_sample_image()
    config = PipelineConfig(
        points=[(10.0, 10.0), (150.0, 15.0), (145.0, 105.0), (12.0, 95.0)],
        illumination_method="clahe",
        mock_yolo=True,
    )
    result = run_preprocessing_pipeline(img, config=config)

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_dir = Path(tmp_dir)
        saved = save_pipeline_artifacts(result, output_dir=out_dir)

        assert "original" in saved and saved["original"].exists()
        assert "perspective" in saved and saved["perspective"].exists()
        assert "perspective_board" in saved and saved["perspective_board"].exists()
        assert "illumination" in saved and saved["illumination"].exists()
        assert "colorspace_grid" in saved and saved["colorspace_grid"].exists()
        assert "comparison_board" in saved and saved["comparison_board"].exists()
        assert "final_preprocessed" in saved and saved["final_preprocessed"].exists()
        assert "yolo_annotated" in saved and saved["yolo_annotated"].exists()
        assert "report" in saved and saved["report"].exists()


def test_pipeline_auto_perspective() -> None:
    from defect_vision.demo import create_perspective_view

    img, _ = create_perspective_view()
    config = PipelineConfig(
        auto_perspective=True,
        illumination_method="none",
    )
    result = run_preprocessing_pipeline(img, config=config)

    assert result.perspective_result is not None
    assert result.perspective_result.output_width > 400
    assert result.perspective_result.output_height > 250


def test_pipeline_invalid_image() -> None:
    with pytest.raises(PipelineError):
        run_preprocessing_pipeline(np.zeros((0, 0), dtype=np.uint8))

