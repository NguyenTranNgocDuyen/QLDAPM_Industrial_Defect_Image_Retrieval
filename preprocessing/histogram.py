"""Histogram calculation and visualization."""

from __future__ import annotations

from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np


def grayscale_histogram(image: np.ndarray) -> np.ndarray:
    """Return the 256-bin grayscale intensity histogram of an RGB image."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    return cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()


def save_histogram(image: np.ndarray, output_path: str | Path, title: str = "Grayscale histogram") -> Path:
    """Save a histogram chart and return its path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    hist = grayscale_histogram(image)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(np.arange(256), hist, color="#2563eb")
    ax.set(xlim=(0, 255), xlabel="Intensity", ylabel="Pixel count", title=title)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path
