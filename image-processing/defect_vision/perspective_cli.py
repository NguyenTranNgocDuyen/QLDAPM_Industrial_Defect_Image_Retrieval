"""Command-line runner for perspective-correction experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import cv2

from .perspective import (
    PerspectiveCorrectionError,
    correct_perspective,
    detect_device_corners,
    draw_corners,
    make_before_after,
)


def parse_points(value: str) -> list[tuple[float, float]]:
    """Parse `x,y;x,y;x,y;x,y` into four points."""
    try:
        pairs = [item.strip() for item in value.split(";") if item.strip()]
        points = []
        for pair in pairs:
            x_text, y_text = pair.split(",")
            points.append((float(x_text), float(y_text)))
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError(
            "Points must use the format x,y;x,y;x,y;x,y."
        ) from error

    if len(points) != 4:
        raise argparse.ArgumentTypeError("Exactly four points are required.")
    return points


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Correct device perspective from four selected corners or phone segmentation."
    )
    parser.add_argument("--input", required=True, type=Path, help="Input image path")
    parser.add_argument(
        "--points",
        type=parse_points,
        default=None,
        help='Four corners, for example "80,50;520,70;500,400;60,380"',
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Automatically detect device contour corners without manual coordinates.",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=None,
        help="Path to trained phone segmentation model (e.g. models/weights.pt).",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.25,
        help="Confidence threshold for segmentation model (default: 0.25).",
    )
    parser.add_argument(
        "--no-refine",
        action="store_true",
        help="Disable sub-pixel edge-fitting corner refinement.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/perspective"),
        help="Directory for images and metrics",
    )
    return parser


def _write_image(path: Path, image) -> None:
    if not cv2.imwrite(str(path), image):
        raise OSError(f"Could not write image: {path}")


def run_segmentation_perspective(
    input_path: Path,
    model_path: Path,
    confidence: float,
    output_dir: Path,
    refine_edges: bool = True,
) -> dict:
    from .phone_segmenter import PhoneSegmenter

    image = cv2.imread(str(input_path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise PerspectiveCorrectionError(f"Could not decode image: {input_path}")

    segmenter = PhoneSegmenter(
        model_path=model_path,
        confidence=confidence,
        refine_edges=refine_edges,
    )
    result = segmenter.segment_and_correct(image)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_image(output_dir / "01_original.png", image)
    _write_image(output_dir / "02_mask.png", result.mask)
    _write_image(output_dir / "03_mask_overlay.png", result.mask_overlay)
    _write_image(output_dir / "04_selected_corners.png", result.corner_preview)
    _write_image(output_dir / "05_corrected.png", result.perspective_result.image)
    _write_image(output_dir / "06_before_after.png", result.before_after)

    metrics = {
        "inputPath": str(input_path),
        "modelPath": str(model_path),
        "confidence": round(float(result.confidence), 4),
        "inputWidth": int(image.shape[1]),
        "inputHeight": int(image.shape[0]),
        "outputWidth": result.perspective_result.output_width,
        "outputHeight": result.perspective_result.output_height,
        "timingsMs": {k: round(v, 3) for k, v in result.timings_ms.items()},
        "orderedCorners": result.corners.round(3).tolist(),
        "transformMatrix": result.perspective_result.transform_matrix.round(8).tolist(),
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    return metrics


def run(input_path: Path, points, output_dir: Path) -> dict:
    image = cv2.imread(str(input_path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise PerspectiveCorrectionError(f"Could not decode image: {input_path}")

    result = correct_perspective(image, points)
    corner_preview = draw_corners(image, result.ordered_corners)
    comparison = make_before_after(corner_preview, result.image)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_image(output_dir / "01_original.png", image)
    _write_image(output_dir / "02_selected_corners.png", corner_preview)
    _write_image(output_dir / "03_corrected.png", result.image)
    _write_image(output_dir / "04_before_after.png", comparison)

    metrics = {
        "inputPath": str(input_path),
        "inputWidth": int(image.shape[1]),
        "inputHeight": int(image.shape[0]),
        "outputWidth": result.output_width,
        "outputHeight": result.output_height,
        "elapsedMs": round(result.elapsed_ms, 3),
        "orderedCorners": result.ordered_corners.round(3).tolist(),
        "transformMatrix": result.transform_matrix.round(8).tolist(),
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    return metrics


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        model_path = args.model
        if model_path is None and args.auto:
            # Check default model locations
            candidates = [
                Path("models/weights.pt"),
                Path("image-processing/models/weights.pt"),
            ]
            for cand in candidates:
                if cand.is_file():
                    model_path = cand
                    break

        if model_path is not None:
            metrics = run_segmentation_perspective(
                input_path=args.input,
                model_path=model_path,
                confidence=args.confidence,
                output_dir=args.output_dir,
                refine_edges=not args.no_refine,
            )
        else:
            points = args.points
            if points is None:
                if not args.auto:
                    raise PerspectiveCorrectionError(
                        "Either --points, --auto, or --model is required."
                    )
                image = cv2.imread(str(args.input), cv2.IMREAD_UNCHANGED)
                if image is None:
                    raise PerspectiveCorrectionError(f"Could not decode image: {args.input}")
                detected = detect_device_corners(image)
                if detected is None:
                    raise PerspectiveCorrectionError(
                        "Could not automatically detect 4 device corners from contour."
                    )
                points = detected

            metrics = run(args.input, points, args.output_dir)
    except (PerspectiveCorrectionError, OSError, ValueError) as error:
        print(f"Error: {error}")
        return 1

    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
