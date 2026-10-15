import json

import cv2
import numpy as np
import pytest

from defect_vision.yolo_baseline import (
    MockYoloDetector,
    YoloBaselineConfig,
    YoloBaselineError,
    run_baseline_inference,
    save_result,
)


def test_mock_detector_finds_bright_regions():
    image = np.full((120, 160, 3), 40, dtype=np.uint8)
    cv2.rectangle(image, (20, 30), (70, 80), (240, 240, 240), -1)
    detections = MockYoloDetector().predict(image)
    assert len(detections) == 1
    assert detections[0].class_name == "defect"
    assert detections[0].confidence > 0.5
    assert detections[0].x1 == pytest.approx(20)


def test_baseline_result_matches_contract_shape(tmp_path):
    image = np.full((80, 100, 3), 30, dtype=np.uint8)
    image[20:40, 50:75] = 255
    result, annotated = run_baseline_inference(
        image,
        MockYoloDetector(),
        scan_id="00000000-0000-0000-0000-000000000001",
        source_url="input.png",
        display_url="annotated.png",
    )
    assert result["success"] is True
    assert result["hasDefect"] is True
    assert result["sourceImage"] == {"width": 100, "height": 80}
    assert result["displayImage"]["coordinateSpace"] == "processed"
    assert result["detections"][0]["x1"] >= 0
    assert result["processing"]["totalMs"] >= result["processing"]["inferenceMs"]
    assert annotated.shape == image.shape

    output_path = tmp_path / "result.json"
    save_result(result, output_path)
    assert json.loads(output_path.read_text(encoding="utf-8"))["scanId"] == result["scanId"]


def test_config_rejects_invalid_thresholds():
    with pytest.raises(YoloBaselineError):
        YoloBaselineConfig(confidence=1.1)
    with pytest.raises(YoloBaselineError):
        YoloBaselineConfig(iou=-0.1)

