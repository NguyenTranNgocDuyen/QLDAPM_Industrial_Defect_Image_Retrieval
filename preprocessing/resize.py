"""Image resizing helpers."""

from __future__ import annotations

from PIL import Image


def resize_image(image: Image.Image, size: int | tuple[int, int] = 224) -> Image.Image:
    """Return an RGB image resized to ``size`` using high-quality resampling."""
    if isinstance(size, int):
        size = (size, size)
    if size[0] <= 0 or size[1] <= 0:
        raise ValueError("Resize dimensions must be positive.")
    return image.convert("RGB").resize(size, Image.Resampling.LANCZOS)
