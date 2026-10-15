"""CLI runner for the end-to-end preprocessing pipeline.

Examples:
    # Full preprocessing on a real image:
    python -m defect_vision.pipeline_cli --input data/my_image.jpg

    # Full preprocessing with perspective correction + YOLO detection:
    python -m defect_vision.pipeline_cli `
        --input data/my_image.jpg `
        --points "80,50;520,70;500,400;60,380" `
        --method combined `
        --run-yolo --mock
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from .perspective_cli import parse_points
from .pipeline import (
    PipelineConfig,
    PipelineError,
    run_preprocessing_pipeline,
    save_pipeline_artifacts,
)


def _make_demo_device() -> np.ndarray:
    """Create a sample electronic component image for demonstration."""
    h, w = 480, 640
    img = np.full((h, w, 3), (90, 85, 80), dtype=np.uint8)

    # Chassis surface with subtle gradient
    y_coords, x_coords = np.mgrid[0:h, 0:w]
    gradient = (x_coords * 0.08 + y_coords * 0.05).astype(np.uint8)
    img = cv2.add(img, cv2.merge([gradient, gradient, gradient]))

    # Inner electronic board / IC area
    cv2.rectangle(img, (120, 80), (520, 400), (60, 55, 50), -1)
    cv2.rectangle(img, (140, 100), (500, 380), (45, 45, 45), -1)

    # Component pins & tracks
    for x in range(160, 480, 24):
        cv2.line(img, (x, 110), (x, 140), (180, 180, 190), 2)
        cv2.line(img, (x, 340), (x, 370), (180, 180, 190), 2)

    # Defect: Scratch (bright thin line)
    cv2.line(img, (220, 180), (380, 260), (220, 220, 230), 2)
    # Defect: Stain / discoloration (faint spot)
    cv2.circle(img, (420, 240), 32, (40, 110, 140), -1)

    return img


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="End-to-end Preprocessing Pipeline for Electronic Defect Inspection."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Input image path. If omitted, a synthetic device image is used.",
    )
    parser.add_argument(
        "--points",
        type=parse_points,
        default=None,
        help='Optional 4 corner coordinates (x1,y1;x2,y2;x3,y3;x4,y4) for perspective correction.',
    )
    parser.add_argument(
        "--auto-perspective",
        action="store_true",
        help="Automatically detect device contour and rectify perspective without manual coordinates.",
    )
    parser.add_argument(
        "--perspective-model",
        default=None,
        help="Path to phone segmentation model for auto-perspective (e.g. models/weights.pt).",
    )
    parser.add_argument(
        "--method",
        choices=("clahe", "gamma", "background", "combined", "none"),
        default="clahe",
        help="Illumination correction method (default: clahe).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/pipeline-run"),
        help="Directory to save pipeline steps and evaluation report.",
    )
    parser.add_argument(
        "--run-yolo",
        action="store_true",
        help="Run YOLO detection on the preprocessed image.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use deterministic mock YOLO detector (if model weights not yet available).",
    )
    parser.add_argument(
        "--model",
        default="models/yolo-baseline.pt",
        help="Path to YOLO .pt weights file (default: models/yolo-baseline.pt).",
    )
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    return parser


def run_cli(args: argparse.Namespace) -> Path:
    if args.input is not None:
        input_path = Path(args.input)
        if not input_path.exists():
            raise PipelineError(f"Input image not found: {input_path}")
        image = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
        if image is None:
            raise PipelineError(f"Could not decode input image: {input_path}")
        print(f"[Pipeline] Loaded image: {input_path} ({image.shape[1]}x{image.shape[0]})")
    else:
        print("[Pipeline] No --input provided. Generating synthetic electronic device sample...")
        image = _make_demo_device()

    should_run_yolo = args.run_yolo or args.mock
    perspective_model = args.perspective_model
    if perspective_model is None and args.auto_perspective:
        candidates = [Path("models/weights.pt"), Path("image-processing/models/weights.pt")]
        for cand in candidates:
            if cand.is_file():
                perspective_model = str(cand)
                break

    config = PipelineConfig(
        points=args.points,
        auto_perspective=args.auto_perspective,
        perspective_model_path=perspective_model,
        illumination_method=args.method,
        run_yolo=should_run_yolo,
        mock_yolo=args.mock,
        yolo_model_path=args.model,
        yolo_confidence=args.confidence,
        yolo_iou=args.iou,
        yolo_imgsz=args.imgsz,
        yolo_device=args.device,
    )

    print("\n--- Running End-to-End Defect Inspection Preprocessing Pipeline ---")
    if config.points:
        print(" [Step 1/5] Perspective Correction: Manual (4 corners provided)")
    elif config.auto_perspective:
        if config.perspective_model_path:
            print(f" [Step 1/5] Perspective Correction: Automatic with trained segmentation model ({config.perspective_model_path})")
        else:
            print(" [Step 1/5] Perspective Correction: Automatic contour & corner detection (heuristic)")
    else:
        print(" [Step 1/5] Perspective Correction: Skipped (use --auto-perspective or --points to enable)")

    print(f" [Step 2/5] Illumination Correction: Method = {config.illumination_method}")
    print(" [Step 3/5] Color Space Analysis: BGR, HSV, LAB, Grayscale channels")
    print(" [Step 4/5] Quantitative Image Quality Evaluation: Contrast, Sharpness, Noise")

    if should_run_yolo:
        mode_str = "Mock Detector" if args.mock else f"Model ({args.model})"
        print(f" [Step 5/5] YOLO Defect Detection: {mode_str}")
    else:
        print(" [Step 5/5] YOLO Defect Detection: Skipped (use --run-yolo or --mock to enable)")

    result = run_preprocessing_pipeline(image, config=config)
    output_dir = Path(args.output_dir)
    saved = save_pipeline_artifacts(result, output_dir=output_dir)

    print("\n--- Pipeline Execution Summary ---")
    for stage, t in result.timings_ms.items():
        print(f"  - {stage:<22}: {t:>6.2f} ms")

    rec = result.comparison_record
    print(f"\nImage Quality Gains:")
    print(f"  - Contrast gain    : {rec.contrast_gain_ratio:.2f}x")
    print(f"  - Sharpness gain   : {rec.sharpness_gain_ratio:.2f}x")
    print(f"  - Noise gain ratio : {rec.noise_gain_ratio:.2f}x")
    print(f"  - Recommendation   : {rec.recommendation}")

    if result.yolo_result is not None:
        detections = result.yolo_result.get("detections", [])
        print(f"\nYOLO Detection Result: {len(detections)} defect(s) detected")

    print(f"\nArtifacts saved to: {output_dir.resolve()}")
    for key, path in saved.items():
        print(f"  [{key}] -> {path.name}")

    return output_dir


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run_cli(args)


if __name__ == "__main__":
    main()
