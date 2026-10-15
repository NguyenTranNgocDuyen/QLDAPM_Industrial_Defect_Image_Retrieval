"""YOLO baseline inference adapter for Phase 7.

The module keeps the image-processing package usable without downloading a
model.  ``MockYoloDetector`` is deterministic and is intended for demos and
contract tests; ``UltralyticsYoloDetector`` loads the model supplied by TV2
when the optional ``ultralytics`` dependency and a ``.pt`` file are present.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable, Protocol, Sequence
from uuid import uuid4

import cv2
import numpy as np
from numpy.typing import NDArray

Image = NDArray[np.uint8]


class YoloBaselineError(ValueError):
    """Raised for invalid baseline configuration, input, or model output."""


@dataclass(frozen=True)
class YoloDetection:
    """One detection in absolute pixel coordinates."""

    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float

    def to_dict(self) -> dict[str, object]:
        return {
            "class": self.class_name,
            "confidence": round(float(self.confidence), 6),
            "x1": round(float(self.x1), 3),
            "y1": round(float(self.y1), 3),
            "x2": round(float(self.x2), 3),
            "y2": round(float(self.y2), 3),
        }


@dataclass(frozen=True)
class YoloBaselineConfig:
    """Runtime options shared by the real and mock detectors."""

    model_path: str = "models/yolo-baseline.pt"
    confidence: float = 0.25
    iou: float = 0.45
    imgsz: int = 640
    device: str = "cpu"
    class_names: tuple[str, ...] = ("defect",)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise YoloBaselineError("confidence must be between 0 and 1.")
        if not 0.0 <= self.iou <= 1.0:
            raise YoloBaselineError("iou must be between 0 and 1.")
        if self.imgsz < 32:
            raise YoloBaselineError("imgsz must be at least 32 pixels.")
        if not self.device:
            raise YoloBaselineError("device must not be empty.")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class Detector(Protocol):
    """Interface implemented by a production model and the test detector."""

    def predict(self, image: Image) -> Sequence[YoloDetection]:
        ...


def _validate_image(image: Image) -> None:
    if not isinstance(image, np.ndarray) or image.size == 0:
        raise YoloBaselineError("image must be a non-empty numpy array.")
    if image.dtype != np.uint8:
        raise YoloBaselineError("image must have dtype uint8.")
    if image.ndim not in (2, 3):
        raise YoloBaselineError("image must be 2D or 3D.")
    if image.ndim == 3 and image.shape[2] not in (1, 3, 4):
        raise YoloBaselineError("color image must have 1, 3, or 4 channels.")


def _clip_detection(detection: YoloDetection, width: int, height: int) -> YoloDetection | None:
    if not detection.class_name or not 0.0 <= detection.confidence <= 1.0:
        return None
    x1 = min(max(float(detection.x1), 0.0), float(width))
    y1 = min(max(float(detection.y1), 0.0), float(height))
    x2 = min(max(float(detection.x2), 0.0), float(width))
    y2 = min(max(float(detection.y2), 0.0), float(height))
    if x2 <= x1 or y2 <= y1:
        return None
    return YoloDetection(detection.class_name, detection.confidence, x1, y1, x2, y2)


class UltralyticsYoloDetector:
    """Adapter around ``ultralytics.YOLO`` with a small stable output surface."""

    def __init__(self, config: YoloBaselineConfig) -> None:
        self.config = config
        try:
            ultralytics = importlib.import_module("ultralytics")
        except ImportError as exc:
            raise YoloBaselineError(
                "ultralytics is not installed. Install image-processing/requirements-yolo.txt "
                "or run the CLI with --mock."
            ) from exc

        model_path = Path(config.model_path)
        if not model_path.is_file():
            raise YoloBaselineError(f"YOLO model file does not exist: {model_path}")
        self._model = ultralytics.YOLO(str(model_path))

    def predict(self, image: Image) -> Sequence[YoloDetection]:
        _validate_image(image)
        result = self._model.predict(
            source=image,
            conf=self.config.confidence,
            iou=self.config.iou,
            imgsz=self.config.imgsz,
            device=self.config.device,
            verbose=False,
        )[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []

        xyxy = boxes.xyxy.cpu().numpy()
        confidences = boxes.conf.cpu().numpy()
        class_ids = boxes.cls.cpu().numpy().astype(int)
        names = getattr(result, "names", {})
        height, width = image.shape[:2]
        detections: list[YoloDetection] = []
        for box, confidence, class_id in zip(xyxy, confidences, class_ids):
            class_name = names.get(int(class_id), str(class_id)) if isinstance(names, dict) else str(class_id)
            detection = _clip_detection(
                YoloDetection(class_name, float(confidence), *map(float, box)), width, height
            )
            if detection is not None:
                detections.append(detection)
        return detections


class MockYoloDetector:
    """Deterministic contour detector used for a runnable baseline simulation."""

    def __init__(self, config: YoloBaselineConfig | None = None, min_area: int = 40) -> None:
        self.config = config or YoloBaselineConfig()
        if min_area <= 0:
            raise YoloBaselineError("min_area must be positive.")
        self.min_area = min_area

    def predict(self, image: Image) -> Sequence[YoloDetection]:
        _validate_image(image)
        gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # A high threshold makes the mock deterministic for synthetic bright defect marks.
        _, mask = cv2.threshold(gray, 205, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        height, width = gray.shape[:2]
        detections: list[YoloDetection] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.min_area:
                continue
            x, y, box_width, box_height = cv2.boundingRect(contour)
            confidence = min(0.99, 0.55 + (area / max(width * height, 1)) * 4.0)
            detections.append(YoloDetection("defect", confidence, x, y, x + box_width, y + box_height))
        return sorted(detections, key=lambda item: item.confidence, reverse=True)


def build_detector(config: YoloBaselineConfig, *, mock: bool = False) -> Detector:
    """Create the configured detector, selecting mock mode explicitly."""
    return MockYoloDetector(config) if mock else UltralyticsYoloDetector(config)


def annotate_detections(image: Image, detections: Sequence[YoloDetection]) -> Image:
    """Draw detections without changing the image dimensions or coordinate space."""
    _validate_image(image)
    canvas = image.copy()
    if canvas.ndim == 2:
        canvas = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
    if canvas.shape[2] == 4:
        canvas = cv2.cvtColor(canvas, cv2.COLOR_BGRA2BGR)
    for detection in detections:
        x1, y1, x2, y2 = map(int, (detection.x1, detection.y1, detection.x2, detection.y2))
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 165, 255), 2)
        label = f"{detection.class_name} {detection.confidence:.2f}"
        cv2.putText(canvas, label, (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1, cv2.LINE_AA)
    return canvas


def run_baseline_inference(
    image: Image,
    detector: Detector,
    *,
    scan_id: str | None = None,
    source_url: str = "source",
    display_url: str = "processed",
    preprocess: Callable[[Image], Image] | None = None,
) -> tuple[dict[str, object], Image]:
    """Run preprocessing, detection, and postprocessing using the shared contract."""
    _validate_image(image)
    started = perf_counter()
    processed = preprocess(image) if preprocess is not None else image.copy()
    _validate_image(processed)
    preprocessing_ms = (perf_counter() - started) * 1000.0

    inference_started = perf_counter()
    raw_detections = detector.predict(processed)
    inference_ms = (perf_counter() - inference_started) * 1000.0

    post_started = perf_counter()
    height, width = processed.shape[:2]
    detections = [
        clipped
        for item in raw_detections
        if (clipped := _clip_detection(item, width, height)) is not None
    ]
    detections.sort(key=lambda item: item.confidence, reverse=True)
    annotated = annotate_detections(processed, detections)
    postprocessing_ms = (perf_counter() - post_started) * 1000.0
    total_ms = (perf_counter() - started) * 1000.0

    source_height, source_width = image.shape[:2]
    result = {
        "scanId": scan_id or str(uuid4()),
        "success": True,
        "hasDefect": bool(detections),
        "sourceImage": {"width": int(source_width), "height": int(source_height)},
        "displayImage": {
            "width": int(width),
            "height": int(height),
            "url": display_url,
            "coordinateSpace": "processed",
        },
        "processing": {
            "preprocessingMs": round(preprocessing_ms, 3),
            "inferenceMs": round(inference_ms, 3),
            "postprocessingMs": round(postprocessing_ms, 3),
            "totalMs": round(total_ms, 3),
        },
        "detections": [item.to_dict() for item in detections],
    }
    # Keep the parameter visible to callers while respecting the strict shared schema.
    if not source_url:
        raise YoloBaselineError("source_url must not be empty.")
    return result, annotated


def save_result(result: dict[str, object], output_path: str | Path) -> None:
    """Write a baseline result using UTF-8 JSON."""
    Path(output_path).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

