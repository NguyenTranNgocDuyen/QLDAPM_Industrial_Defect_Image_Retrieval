"""No-model smoke test for phone/keyboard-safe image decoding.

Creates only temporary synthetic fixtures: landscape, portrait, EXIF rotations,
grayscale, RGBA, corrupt payload and an over-limit metadata image.  No image
artifact is committed or retained.
"""
from __future__ import annotations
import io
from pathlib import Path
import sys
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from defect_vision.image_io import decode_upright_rgb

def payload(image: Image.Image, fmt: str = "PNG", orientation: int | None = None) -> bytes:
    stream = io.BytesIO(); options = {}
    if orientation is not None:
        exif = Image.Exif(); exif[274] = orientation; options["exif"] = exif
    image.save(stream, fmt, **options); return stream.getvalue()

def main() -> None:
    cases = [
        ("landscape", payload(Image.new("RGB", (80, 40)), "JPEG"), (40, 80, 3)),
        ("portrait", payload(Image.new("RGB", (40, 80)), "JPEG"), (80, 40, 3)),
        ("exif_6", payload(Image.new("RGB", (80, 40)), "JPEG", 6), (80, 40, 3)),
        ("exif_8", payload(Image.new("RGB", (80, 40)), "JPEG", 8), (80, 40, 3)),
        ("exif_3", payload(Image.new("RGB", (80, 40)), "JPEG", 3), (40, 80, 3)),
        ("grayscale", payload(Image.new("L", (20, 10))), (10, 20, 3)),
        ("rgba", payload(Image.new("RGBA", (20, 10))), (10, 20, 3)),
    ]
    for name, data, shape in cases:
        assert decode_upright_rgb(data).shape == shape, name
    for name, data, limit in (("corrupt", b"not-an-image", None), ("large-metadata", payload(Image.new("RGB", (11, 10))), 100)):
        try:
            decode_upright_rgb(data, max_pixels=limit) if limit else decode_upright_rgb(data)
        except ValueError:
            continue
        raise AssertionError(f"{name} was accepted")
    print("TV1 decode smoke test passed (synthetic fixtures only).")

if __name__ == "__main__":
    main()
