"""Offline luminance enhancement utilities."""
from __future__ import annotations
import cv2
import numpy as np

def equalize_luminance(image: np.ndarray, clip_limit: float = 2.0, grid_size: int = 8) -> np.ndarray:
    """CLAHE only the luminance channel; preserve alpha and source channel count."""
    if not isinstance(image, np.ndarray) or image.size == 0 or image.dtype != np.uint8:
        raise ValueError("image must be a non-empty uint8 numpy array")
    if clip_limit <= 0 or grid_size < 2: raise ValueError("clip_limit must be > 0 and grid_size >= 2")
    clahe = cv2.createCLAHE(clipLimit=float(clip_limit), tileGridSize=(grid_size, grid_size))
    if image.ndim == 2: return clahe.apply(image)
    if image.ndim != 3 or image.shape[2] not in (1, 3, 4): raise ValueError("unsupported channel layout")
    if image.shape[2] == 1: return clahe.apply(image[..., 0])[..., None]
    color, alpha = image[..., :3], image[..., 3:] if image.shape[2] == 4 else None
    lab = cv2.cvtColor(color, cv2.COLOR_BGR2LAB); lab[..., 0] = clahe.apply(lab[..., 0])
    result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    return np.dstack((result, alpha)) if alpha is not None else result
