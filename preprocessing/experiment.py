"""Create visual preprocessing comparisons for the report."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from preprocessing.enhancement import equalize_luminance
from preprocessing.filtering import gaussian_filter, median_filter
from preprocessing.histogram import save_histogram
from preprocessing.resize import letterbox_resize


def create_experiment(image_path: str | Path, output_dir: str | Path, image_size: int = 224) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    original = Image.open(image_path).convert("RGB")
    # This is a report preview only.  It intentionally never feeds v3 inference.
    resized = np.asarray(letterbox_resize(original, (image_size, image_size))[0])
    variants = {
        "original": np.asarray(original),
        "resized": resized,
        "gaussian": gaussian_filter(resized),
        "median": median_filter(resized),
        "contrast_enhanced": equalize_luminance(resized),
    }
    for name, array in variants.items():
        Image.fromarray(array).save(output_dir / f"{name}.png")
    save_histogram(resized, output_dir / "histogram_original.png", "Histogram: resized image")
    save_histogram(variants["contrast_enhanced"], output_dir / "histogram_enhanced.png", "Histogram: enhanced image")

    fig, axes = plt.subplots(1, len(variants), figsize=(18, 4))
    for axis, (name, array) in zip(axes, variants.items()):
        axis.imshow(array)
        axis.set_title(name.replace("_", " ").title())
        axis.axis("off")
    fig.tight_layout()
    fig.savefig(output_dir / "comparison.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate preprocessing experiment artifacts.")
    parser.add_argument("image", help="Path to an input image")
    parser.add_argument("--output-dir", default="outputs/preprocessing_experiment")
    parser.add_argument("--image-size", type=int, default=224)
    args = parser.parse_args()
    create_experiment(args.image, args.output_dir, args.image_size)
