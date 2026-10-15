"""CLI and demo script for Phase 4: Color Space Analysis.

Usage:
    python -m defect_vision.colorspace_cli --input <path_to_image> --output-dir <path_to_output>
    python -m defect_vision.colorspace_cli --demo
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from defect_vision.colorspace import (
    analyze_color_space,
    evaluate_defect_contrast,
    extract_all_defect_channels,
    make_channel_comparison_grid,
)


def create_synthetic_defect_sample() -> tuple[np.ndarray, np.ndarray]:
    """Generate a realistic test image of an electronic device back cover.
    
    Contains:
    1. A scratch defect (subtle brightness change, best in L/Gray).
    2. A chemical stain / discoloration defect (color change, best in S/A/B_channel).
    3. A crack defect (dark linear pattern).
    """
    h, w = 480, 640
    # Base metallic gray-blue chassis
    img = np.full((h, w, 3), (120, 115, 110), dtype=np.uint8)

    # Subtle gradient lighting across chassis
    y_coords, x_coords = np.mgrid[0:h, 0:w]
    lighting = 20 * np.sin(x_coords / 120.0)
    img = np.clip(img.astype(np.float32) + lighting[:, :, None], 0, 255).astype(np.uint8)

    # Defect mask
    mask = np.zeros((h, w), dtype=np.uint8)

    # 1. Chemical stain / yellowish discoloration (Strong in S and B_channel, subtle in Gray)
    cv2.circle(img, (220, 240), 45, (80, 160, 200), -1)  # yellowish-amber stain in BGR
    cv2.circle(mask, (220, 240), 45, 255, -1)

    # 2. Fine scratch (Bright thin line, strong in Gray & L)
    cv2.line(img, (360, 120), (520, 200), (225, 225, 230), 2)
    cv2.line(mask, (360, 120), (520, 200), 255, 2)

    # 3. Micro-crack (Dark thin jagged line)
    pts = np.array([[380, 320], [420, 350], [450, 340], [500, 400]], np.int32)
    cv2.polylines(img, [pts], False, (35, 30, 25), 2)
    cv2.polylines(mask, [pts], False, 255, 2)

    return img, mask


def run_colorspace_pipeline(
    input_path: str | None = None,
    output_dir: str = "outputs/colorspace-demo",
) -> None:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if input_path:
        img = cv2.imread(input_path)
        if img is None:
            raise FileNotFoundError(f"Could not read input image from: {input_path}")
        mask = None
    else:
        print("[Phase 4 Demo] Generating synthetic electronic device sample with defects...")
        img, mask = create_synthetic_defect_sample()
        cv2.imwrite(str(out_dir / "00_synthetic_mask.png"), mask)

    # Save original input
    cv2.imwrite(str(out_dir / "01_original_bgr.png"), img)

    # 1. Extract all target channels
    channels = extract_all_defect_channels(img)

    for ch_name, ch_data in channels.items():
        cv2.imwrite(str(out_dir / f"channel_{ch_name}.png"), ch_data)

    # 2. Quantitative defect contrast evaluation if mask is available
    metrics_data = {}
    metrics_obj = None
    if mask is not None:
        metrics_obj = evaluate_defect_contrast(channels, mask)
        metrics_data = {name: m.to_dict() for name, m in metrics_obj.items()}

        with open(out_dir / "defect_contrast_metrics.json", "w", encoding="utf-8") as f:
            json.dump(metrics_data, f, indent=2)

        print("\n--- Defect Contrast & CNR Analysis across Color Spaces ---")
        print(f"{'Channel':<12} | {'Defect Mean':<12} | {'BG Mean':<10} | {'Michelson':<10} | {'CNR':<8}")
        print("-" * 62)
        for name, m in metrics_obj.items():
            print(
                f"{name:<12} | {m.defect_mean:<12.2f} | {m.bg_mean:<10.2f} | "
                f"{m.michelson_contrast:<10.3f} | {m.cnr:<8.2f}"
            )

        # Highlight best channel
        best_channel = max(metrics_obj.items(), key=lambda item: item[1].cnr)
        print("-" * 62)
        print(f"-> Optimal defect separation channel: [{best_channel[0]}] with CNR = {best_channel[1].cnr:.2f}\n")

    # 3. Create visual comparison grid
    grid = make_channel_comparison_grid(img, channels, metrics=metrics_obj)
    cv2.imwrite(str(out_dir / "comparison_grid.png"), grid)
    print(f"[Done] Artifacts saved to: {out_dir.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 4: Color Space Analysis for Defect Inspection")
    parser.add_argument("--input", type=str, default=None, help="Path to input device image")
    parser.add_argument("--output-dir", type=str, default="outputs/colorspace-demo", help="Output directory")
    parser.add_argument("--demo", action="store_true", help="Run with synthetic defect sample")

    args = parser.parse_args()
    run_colorspace_pipeline(input_path=args.input, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
