"""Command-line runner for illumination-correction experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import cv2

from .illumination import (
    SUPPORTED_METHODS,
    IlluminationCorrectionError,
    analyze_luminance,
    correct_illumination,
    make_comparison_grid,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare illumination correction methods on one image."
    )
    parser.add_argument("--input", required=True, type=Path, help="Input image path")
    parser.add_argument(
        "--method",
        choices=(*SUPPORTED_METHODS, "all"),
        default="all",
        help="Correction method to run",
    )
    parser.add_argument(
        "--gamma",
        type=float,
        default=None,
        help="Explicit gamma; omit to estimate it from mean luminance",
    )
    parser.add_argument("--target-mean", type=float, default=128.0)
    parser.add_argument("--clip-limit", type=float, default=2.0)
    parser.add_argument("--grid-size", type=int, default=8)
    parser.add_argument("--background-kernel", type=int, default=201)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/illumination"),
    )
    return parser


def _write_image(path: Path, image) -> None:
    if not cv2.imwrite(str(path), image):
        raise OSError(f"Could not write image: {path}")


def run(
    input_path: Path,
    output_dir: Path,
    *,
    method: str = "all",
    gamma: float | None = None,
    target_mean: float = 128.0,
    clip_limit: float = 2.0,
    grid_size: int = 8,
    background_kernel: int = 201,
) -> dict:
    image = cv2.imread(str(input_path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise IlluminationCorrectionError(f"Could not decode image: {input_path}")

    methods = SUPPORTED_METHODS if method == "all" else (method,)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_image(output_dir / "01_original.png", image)

    comparison_images = [("Original", image)]
    results = {}
    for index, current_method in enumerate(methods, start=2):
        result = correct_illumination(
            image,
            current_method,
            gamma=gamma,
            target_mean=target_mean,
            clip_limit=clip_limit,
            grid_size=grid_size,
            background_kernel=background_kernel,
        )
        _write_image(output_dir / f"{index:02d}_{current_method}.png", result.image)
        comparison_images.append((current_method, result.image))
        results[current_method] = {
            "elapsedMs": round(result.elapsed_ms, 3),
            "parameters": result.parameters,
            "before": result.before.to_dict(),
            "after": result.after.to_dict(),
        }

    comparison = make_comparison_grid(comparison_images)
    _write_image(output_dir / "comparison.png", comparison)

    metrics = {
        "inputPath": str(input_path),
        "inputWidth": int(image.shape[1]),
        "inputHeight": int(image.shape[0]),
        "inputLuminance": analyze_luminance(image).to_dict(),
        "results": results,
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    return metrics


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        metrics = run(
            args.input,
            args.output_dir,
            method=args.method,
            gamma=args.gamma,
            target_mean=args.target_mean,
            clip_limit=args.clip_limit,
            grid_size=args.grid_size,
            background_kernel=args.background_kernel,
        )
    except (IlluminationCorrectionError, OSError, cv2.error) as error:
        print(f"Error: {error}")
        return 1

    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
