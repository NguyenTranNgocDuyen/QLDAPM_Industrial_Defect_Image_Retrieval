"""Generate a synthetic uneven-lighting image and compare corrections."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from .demo import create_front_view
from .illumination_cli import run


def create_uneven_lighting_image() -> np.ndarray:
    base = create_front_view().astype(np.float32)
    height, width = base.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)

    horizontal = 0.38 + 0.82 * (xx / max(width - 1, 1))
    shadow = 0.32 * np.exp(
        -(((xx - width * 0.20) / (width * 0.22)) ** 2)
        - (((yy - height * 0.72) / (height * 0.32)) ** 2)
    )
    highlight = 0.60 * np.exp(
        -(((xx - width * 0.78) / (width * 0.13)) ** 2)
        - (((yy - height * 0.24) / (height * 0.22)) ** 2)
    )
    illumination = np.clip(horizontal - shadow + highlight, 0.20, 1.55)
    uneven = np.clip(base * illumination[:, :, None], 0, 255).astype(np.uint8)

    # A small saturated reflection is intentionally unrecoverable. It
    # demonstrates why illumination correction cannot restore clipped detail.
    overlay = uneven.copy()
    cv2.ellipse(
        overlay,
        (int(width * 0.80), int(height * 0.18)),
        (42, 16),
        -12,
        0,
        360,
        (255, 255, 255),
        -1,
        cv2.LINE_AA,
    )
    return cv2.addWeighted(overlay, 0.75, uneven, 0.25, 0)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the illumination demo.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/illumination-demo"),
    )
    args = parser.parse_args(argv)

    image = create_uneven_lighting_image()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    input_path = args.output_dir / "demo_input.png"
    if not cv2.imwrite(str(input_path), image):
        raise OSError(f"Could not write demo image: {input_path}")

    metrics = run(input_path, args.output_dir, method="all")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
