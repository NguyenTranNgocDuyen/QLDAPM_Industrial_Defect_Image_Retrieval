"""CLI and demonstration script for Phase 6: Before & After Comparison Suite.

Usage:
    python -m defect_vision.comparison_cli --output-dir outputs/comparison-demo
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np

from defect_vision.comparison import (
    EnhancementComparisonRecord,
    evaluate_enhancement_pair,
    make_before_after_comparison_board,
)
from defect_vision.illumination import clahe_correction, gamma_correction


def synthesize_low_contrast_defect_image() -> tuple[np.ndarray, np.ndarray]:
    """Create a dark, low-contrast device image with a fine scratch and a faint stain."""
    h, w = 480, 640
    # Dark metallic phone back (underexposed)
    img = np.full((h, w, 3), (45, 42, 40), dtype=np.uint8)

    # Defect mask
    mask = np.zeros((h, w), dtype=np.uint8)

    # Scratch (slight brightness difference)
    cv2.line(img, (260, 140), (420, 220), (70, 68, 65), 2)
    cv2.line(mask, (260, 140), (420, 220), 255, 2)

    # Chemical stain
    cv2.circle(img, (200, 300), 38, (58, 52, 46), -1)
    cv2.circle(mask, (200, 300), 38, 255, -1)

    # Add realistic low-light camera sensor noise
    noise = np.random.normal(0, 4, img.shape).astype(np.float32)
    noisy_img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    return noisy_img, mask


def run_comparison_benchmark(output_dir: str = "outputs/comparison-demo") -> None:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[Phase 6 Demo] Synthesizing low-contrast inspection sample...")
    original, mask = synthesize_low_contrast_defect_image()
    cv2.imwrite(str(out_dir / "00_original_sample.png"), original)
    cv2.imwrite(str(out_dir / "00_defect_mask.png"), mask)

    # Techniques to compare:
    techniques = [
        ("Gamma Correction (auto)", lambda im: gamma_correction(im)[0]),
        ("CLAHE (clip=2.0)", lambda im: clahe_correction(im, clip_limit=2.0)),
        ("CLAHE Aggressive (clip=6.0)", lambda im: clahe_correction(im, clip_limit=6.0)),
    ]

    records: list[EnhancementComparisonRecord] = []

    print("\n--- Running Before & After Defect Detection Evaluation ---")
    for name, func in techniques:
        t0 = perf_counter()
        enh_img = func(original)
        elapsed_ms = (perf_counter() - t0) * 1000.0

        record = evaluate_enhancement_pair(
            original=original,
            enhanced=enh_img,
            technique_name=name,
            elapsed_ms=elapsed_ms,
            defect_mask=mask,
        )
        records.append(record)

        # Generate visual comparison board
        board = make_before_after_comparison_board(original, enh_img, record)

        safe_name = name.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("=", "")
        cv2.imwrite(str(out_dir / f"compare_{safe_name}.png"), board)

    # Export records to JSON
    summary_data = [r.to_dict() for r in records]
    with open(out_dir / "enhancement_benchmark_report.json", "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    # Print clean console table
    print(f"{'Technique':<28} | {'Latency':<8} | {'Contrast Gain':<13} | {'Noise Gain':<10} | {'Defect CNR':<16} | {'Verdict'}")
    print("-" * 105)
    for r in records:
        cnr_str = f"{r.defect_cnr_before:.2f} -> {r.defect_cnr_after:.2f}" if r.defect_cnr_before else "N/A"
        print(
            f"{r.technique_name:<28} | {r.elapsed_ms:>5.1f} ms | {r.contrast_gain_ratio:>12.2f}x | "
            f"{r.noise_gain_ratio:>9.2f}x | {cnr_str:<16} | {r.recommendation}"
        )
    print("-" * 105)
    print(f"\n[Done] Benchmark reports and visual boards saved to: {out_dir.resolve()}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 6: Before & After Comparison Benchmark")
    parser.add_argument("--output-dir", type=str, default="outputs/comparison-demo", help="Output directory")
    args = parser.parse_args()
    run_comparison_benchmark(output_dir=args.output_dir)


if __name__ == "__main__":
    main()
