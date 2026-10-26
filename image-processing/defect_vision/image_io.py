"""Unicode-safe image output helpers for Windows paths."""

from __future__ import annotations

from pathlib import Path
import io

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from numpy.typing import NDArray


def write_image(path: str | Path, image: NDArray[np.generic]) -> bool:
    """Write an image without relying on OpenCV's narrow Windows file paths.

    ``cv2.imwrite`` may return ``False`` when the destination contains
    Vietnamese or other non-ASCII characters. Encoding in memory and letting
    :class:`pathlib.Path` write the bytes preserves the normal OpenCV codec
    behavior while supporting Unicode paths.
    """
    destination = Path(path)
    extension = destination.suffix or ".png"
    success, encoded = cv2.imencode(extension, image)
    if not success:
        return False
    destination.write_bytes(encoded.tobytes())
    return True


def read_image(path: str | Path, flags: int = cv2.IMREAD_COLOR) -> NDArray[np.uint8] | None:
    """Read an image from a Unicode-safe path on every supported platform."""
    try:
        payload = np.fromfile(Path(path), dtype=np.uint8)
    except OSError:
        return None
    if payload.size == 0:
        return None
    return cv2.imdecode(payload, flags)

MAX_DECODE_PIXELS = 40_000_000

def decode_upright_rgb(data: bytes, *, max_pixels: int = MAX_DECODE_PIXELS) -> NDArray[np.uint8]:
    """Decode safely into EXIF-upright source-resolution RGB, without resizing."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ValueError("Image payload is empty.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > max_pixels:
                raise ValueError(f"Image dimensions exceed {max_pixels} pixels.")
            upright = ImageOps.exif_transpose(image)
            return np.asarray(upright.convert("RGB"), dtype=np.uint8)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Could not decode image safely.") from exc
