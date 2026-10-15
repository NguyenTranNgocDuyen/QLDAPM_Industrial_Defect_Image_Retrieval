"""CLI and demonstration script for Phase 5: Image Augmentation.

Usage:
    python -m defect_vision.augmentation_cli --output-dir outputs/augmentation-demo
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from defect_vision.augmentation import (
    AugmentedSample,
    BoundingBox,
    draw_bounding_boxes,
    generate_defect_augmentation_batch,
    make_augmentation_grid,
)


def create_sample_with_boxes() -> tuple[np.ndarray, list[BoundingBox], dict[int, str]]:
    """Synthesize a sample device with scratch and stain defects and their true bounding boxes."""
    h, w = 480, 640
    # Metallic chassis
    img = np.full((h, w, 3), (130, 125, 120), dtype=np.uint8)

    # Defect 1: Scratch (top right)
    cv2.line(img, (380, 100), (520, 180), (220, 220, 230), 2)
    # Defect 2: Chemical Stain (center left)
    cv2.circle(img, (200, 260), 40, (80, 150, 190), -1)

    class_names = {0: "scratch", 1: "stain"}

    # YOLO normalized coordinates: class xc yc w h
    # Scratch: x from 380 to 520, y from 100 to 180
    box_scratch = BoundingBox(
        class_id=0,
        x_center=(380 + 520) / (2.0 * w),
        y_center=(100 + 180) / (2.0 * h),
        width=(520 - 380) / float(w),
        height=(180 - 100) / float(h),
    )

    # Stain: circle center 200, 260 with radius 40 -> box [160, 220, 240, 300]
    box_stain = BoundingBox(
        class_id=1,
        x_center=200.0 / w,
        y_center=260.0 / h,
        width=80.0 / w,
        height=80.0 / h,
    )

    return img, [box_scratch, box_stain], class_names


def run_augmentation_pipeline(output_dir: str = "outputs/augmentation-demo") -> None:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[Phase 5 Demo] Generating synthetic defect sample and synchronized augmentations...")
    img, boxes, class_names = create_sample_with_boxes()

    # Generate full augmentation batch
    samples: list[AugmentedSample] = generate_defect_augmentation_batch(img, boxes)

    summary_records = []
    for idx, s in enumerate(samples):
        # Save augmented image
        file_name = f"{idx:02d}_{s.transform_name}.png"
        annotated = draw_bounding_boxes(s.image, s.boxes, class_names)
        cv2.imwrite(str(out_dir / file_name), annotated)

        # Save YOLO annotation text
        txt_name = f"{idx:02d}_{s.transform_name}.txt"
        yolo_lines = [b.to_yolo_line() for b in s.boxes]
        with open(out_dir / txt_name, "w", encoding="utf-8") as f:
            f.write("\n".join(yolo_lines) + "\n")

        summary_records.append({
            "index": idx,
            "transform": s.transform_name,
            "box_count": len(s.boxes),
            "boxes": [b.to_dict() for b in s.boxes],
        })

    # Save summary metadata
    with open(out_dir / "augmentation_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_records, f, indent=2)

    # Save visual comparison grid
    grid = make_augmentation_grid(samples, class_names)
    cv2.imwrite(str(out_dir / "augmentation_comparison_grid.png"), grid)

    print(f"[Done] Generated {len(samples)} augmented samples with synchronized YOLO labels.")
    print(f"Results and visual grid saved to: {out_dir.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 5: Image Augmentation for Defect Detection")
    parser.add_argument("--output-dir", type=str, default="outputs/augmentation-demo", help="Output directory")
    args = parser.parse_args()
    run_augmentation_pipeline(output_dir=args.output_dir)


if __name__ == "__main__":
    main()
