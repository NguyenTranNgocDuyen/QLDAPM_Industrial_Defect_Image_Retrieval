"""Image resizing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from PIL import Image

@dataclass(frozen=True)
class LetterboxMetadata:
    original_width: int; original_height: int; resized_width: int; resized_height: int
    scale_x: float; scale_y: float; padding_left: int; padding_top: int; padding_right: int; padding_bottom: int
    output_width: int; output_height: int


def resize_image(image: Image.Image, size: int | tuple[int, int] = 224) -> Image.Image:
    """Return an RGB image resized to ``size`` using high-quality resampling."""
    if isinstance(size, int):
        size = (size, size)
    if size[0] <= 0 or size[1] <= 0:
        raise ValueError("Resize dimensions must be positive.")
    return image.convert("RGB").resize(size, Image.Resampling.LANCZOS)

def _size(size: tuple[int, int]) -> tuple[int, int]:
    if len(size) != 2 or min(size) <= 0: raise ValueError("size must contain two positive dimensions")
    return int(size[0]), int(size[1])

def resize_keep_aspect(image: Image.Image, max_size: tuple[int, int]) -> Image.Image:
    """Resize inside bounds without distortion (no padding)."""
    width, height = _size(max_size); source = image.convert("RGB")
    scale = min(width / source.width, height / source.height)
    return source.resize((max(1, round(source.width * scale)), max(1, round(source.height * scale))), Image.Resampling.LANCZOS)

def letterbox_resize(image: Image.Image, output_size: tuple[int, int], fill: tuple[int,int,int] = (0,0,0)) -> tuple[Image.Image, LetterboxMetadata]:
    """Aspect-preserving resize plus padding, with reversible coordinate metadata."""
    ow, oh = _size(output_size); source = image.convert("RGB"); scale = min(ow/source.width, oh/source.height)
    rw, rh = max(1, round(source.width*scale)), max(1, round(source.height*scale))
    left, top = (ow-rw)//2, (oh-rh)//2; right, bottom = ow-rw-left, oh-rh-top
    result = Image.new("RGB", (ow,oh), fill); result.paste(source.resize((rw,rh), Image.Resampling.LANCZOS), (left,top))
    return result, LetterboxMetadata(source.width,source.height,rw,rh,rw/source.width,rh/source.height,left,top,right,bottom,ow,oh)

def source_to_letterbox(x: float, y: float, meta: LetterboxMetadata) -> tuple[float,float]:
    return x * meta.scale_x + meta.padding_left, y * meta.scale_y + meta.padding_top

def letterbox_to_source(x: float, y: float, meta: LetterboxMetadata) -> tuple[float,float]:
    return (x-meta.padding_left)/meta.scale_x, (y-meta.padding_top)/meta.scale_y

def map_bbox_to_letterbox(bbox: tuple[float,float,float,float], meta: LetterboxMetadata) -> tuple[float,float,float,float]:
    x1,y1=source_to_letterbox(bbox[0],bbox[1],meta); x2,y2=source_to_letterbox(bbox[2],bbox[3],meta); return x1,y1,x2,y2

def map_bbox_to_source(bbox: tuple[float,float,float,float], meta: LetterboxMetadata) -> tuple[float,float,float,float]:
    x1,y1=letterbox_to_source(bbox[0],bbox[1],meta); x2,y2=letterbox_to_source(bbox[2],bbox[3],meta); return x1,y1,x2,y2

