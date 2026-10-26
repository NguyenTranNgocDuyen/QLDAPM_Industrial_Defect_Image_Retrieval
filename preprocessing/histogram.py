"""Histogram data and PNG artifact generation."""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

def histogram_data(image: np.ndarray) -> dict[str, list[int]]:
    """Return 256-bin histogram data for gray or RGB-like image arrays."""
    if not isinstance(image, np.ndarray) or image.size == 0 or image.dtype != np.uint8: raise ValueError("image must be non-empty uint8")
    if image.ndim == 2: return {"gray": np.bincount(image.ravel(), minlength=256).tolist()}
    if image.ndim != 3 or image.shape[2] not in (1,3,4): raise ValueError("unsupported channel layout")
    names = ("gray",) if image.shape[2] == 1 else ("blue", "green", "red")
    return {n: np.bincount(image[..., i].ravel(), minlength=256).tolist() for i,n in enumerate(names)}

def save_histogram(image: np.ndarray, output: str | Path, title: str = "Histogram") -> dict[str, list[int]]:
    """Write a PNG histogram and sidecar JSON, returning its values."""
    data = histogram_data(image); output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(); colors = {"gray":"black", "blue":"b", "green":"g", "red":"r"}
    for name, values in data.items(): ax.plot(values, color=colors[name], label=name)
    ax.set(title=title, xlabel="pixel value", ylabel="count"); ax.legend(); fig.tight_layout(); fig.savefig(output); plt.close(fig)
    output.with_suffix(".json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data
