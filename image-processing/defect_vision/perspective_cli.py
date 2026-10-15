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
        description="Correct device perspective from four selected corners."
    )
    parser.add_argument("--input", required=True, type=Path, help="Input image path")
    parser.add_argument(
        "--points",
        required=True,
        type=parse_points,
        help='Four corners, for example "80,50;520,70;500,400;60,380"',
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
    args = build_parser().parse_args(argv)
    try:
        metrics = run(args.input, args.points, args.output_dir)
    except (PerspectiveCorrectionError, OSError) as error:
        print(f"Error: {error}")
        return 1

    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
