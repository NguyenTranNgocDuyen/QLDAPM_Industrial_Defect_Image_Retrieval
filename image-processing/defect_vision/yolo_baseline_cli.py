"""CLI for the Phase 7 YOLO baseline pipeline.

Examples:
    python -m defect_vision.yolo_baseline_cli --mock
    python -m defect_vision.yolo_baseline_cli --input photo.jpg --model models/tv2.pt
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from .yolo_baseline import (
    YoloBaselineConfig,
    YoloBaselineError,
    build_detector,
    run_baseline_inference,
    save_result,
)


def _make_demo_image() -> np.ndarray:
    image = np.full((480, 640, 3), 55, dtype=np.uint8)
    cv2.rectangle(image, (70, 70), (570, 410), (100, 100, 100), -1)
    cv2.rectangle(image, (180, 150), (270, 205), (235, 235, 235), -1)
    cv2.circle(image, (450, 300), 34, (245, 245, 245), -1)
    return image


def run_cli(args: argparse.Namespace) -> Path:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.input:
        input_path = Path(args.input)
        image = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
        if image is None:
            raise YoloBaselineError(f"Could not read input image: {input_path}")
        source_url = input_path.name
    else:
        image = _make_demo_image()
        source_url = "synthetic-demo"

    config = YoloBaselineConfig(
        model_path=args.model,
        confidence=args.confidence,
        iou=args.iou,
        imgsz=args.imgsz,
        device=args.device,
    )
    detector = build_detector(config, mock=args.mock)
    result, annotated = run_baseline_inference(
        image,
        detector,
        source_url=source_url,
        display_url="annotated.png",
    )
    image_path = output_dir / "annotated.png"
    result_path = output_dir / "baseline_result.json"
    if not cv2.imwrite(str(image_path), annotated):
        raise YoloBaselineError(f"Could not write output image: {image_path}")
    save_result(result, result_path)
    print(f"[Done] detections={len(result['detections'])} total_ms={result['processing']['totalMs']}")
    print(f"[Output] {result_path}")
    return result_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 7: YOLO baseline inference")
    parser.add_argument("--input", help="Input image; omitted to use a synthetic demo image")
    parser.add_argument("--model", default="models/yolo-baseline.pt", help="TV2 YOLO .pt model path")
    parser.add_argument("--output-dir", default="outputs/yolo-baseline", help="Output directory")
    parser.add_argument("--mock", action="store_true", help="Use deterministic mock detector")
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    run_cli(parser.parse_args())


if __name__ == "__main__":
    main()

