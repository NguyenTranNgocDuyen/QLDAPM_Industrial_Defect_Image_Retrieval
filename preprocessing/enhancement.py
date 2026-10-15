"""Contrast enhancement operations."""

from __future__ import annotations

import cv2
import numpy as np


def equalize_luminance(image: np.ndarray) -> np.ndarray:
    """Enhance contrast by equalizing only the luminance channel (YCrCb)."""
    ycrcb = cv2.cvtColor(image, cv2.COLOR_RGB2YCrCb)
    ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
    return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2RGB)
