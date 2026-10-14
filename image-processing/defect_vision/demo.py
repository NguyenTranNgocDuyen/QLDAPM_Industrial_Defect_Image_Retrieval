"""Generate and rectify a synthetic electronic-device image."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from .perspective_cli import run


def create_front_view(width: int = 640, height: int = 360) -> np.ndarray:
    """Create a simple device surface with visible synthetic defects."""
    image = np.full((height, width, 3), (190, 195, 200), dtype=np.uint8)
    cv2.rectangle(image, (2, 2), (width - 3, height - 3), (35, 35, 35), 5)

    for row in range(4):
        for column in range(10):
            x1 = 40 + column * 56
            y1 = 48 + row * 54
            cv2.rectangle(image, (x1, y1), (x1 + 42, y1 + 34), (65, 70, 75), -1)
            cv2.rectangle(image, (x1, y1), (x1 + 42, y1 + 34), (230, 230, 230), 1)

    # Thin red scratch and dark crack make geometric distortion easy to inspect.
    cv2.line(image, (110, 300), (300, 275), (20, 20, 220), 3, cv2.LINE_AA)
    crack = np.array([[470, 260], [455, 280], [478, 292], [460, 320]])
    cv2.polylines(image, [crack], False, (20, 20, 20), 3, cv2.LINE_AA)
    cv2.putText(
        image,
        "DEVICE SURFACE",
        (190, 335),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (45, 45, 45),
        2,
        cv2.LINE_AA,
    )
    return image


def create_perspective_view() -> tuple[np.ndarray, np.ndarray]:
    front = create_front_view()
    height, width = front.shape[:2]
    source = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    destination = np.array(
        [[130, 95], [690, 45], [740, 500], [75, 545]], dtype=np.float32
    )
    transform = cv2.getPerspectiveTransform(source, destination)
    canvas = cv2.warpPerspective(
        front,
        transform,
        (820, 620),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(245, 245, 245),
    )
    return canvas, destination


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the perspective demo.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/perspective-demo"),
    )
    args = parser.parse_args(argv)

    image, corners = create_perspective_view()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    input_path = args.output_dir / "demo_input.png"
    if not cv2.imwrite(str(input_path), image):
        raise OSError(f"Could not write demo image: {input_path}")

    metrics = run(input_path, corners, args.output_dir)
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
