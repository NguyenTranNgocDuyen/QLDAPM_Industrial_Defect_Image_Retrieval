"""Adapter example for an application that already owns phone_detect and H."""
from pathlib import Path

import cv2
import numpy as np

from phone_damage_v3 import ROIDamageEngine


WEIGHTS = Path(__file__).resolve().parent / 'phone_damage_v3' / 'weights'


def create_engine(device=None):
    # Call once when the worker/application starts, not once per request.
    return ROIDamageEngine(WEIGHTS, device=device, load_phone_detector=False)


def analyze_original(engine, rgb_original, phone_mask_original):
    """RGB uint8 HxWx3; phone mask bool or integer 0/1/255, same upright HxW."""
    mask, pixels = engine.predict_with_body(rgb_original, phone_mask_original)
    return dict(damage_mask=mask, candidate_pixels_original=pixels,
                found=pixels >= engine.alarm_pixels, threshold=engine.threshold,
                severity=None, severity_status='not_implemented')


def rectify_masks(damage_mask, visible_surface_mask, H, output_size):
    """Use the SAME validated H/size as the app's corrected RGB; size=(W,H).

    The caller supplies a visible planar surface, not all sides of a 3D phone.
    This function does not validate the app's homography or observation quality.
    """
    h, w = damage_mask.shape
    surface = np.asarray(visible_surface_mask) != 0
    if surface.shape != (h, w) or not surface.any():
        raise ValueError('A nonempty original-coordinate surface mask is required.')
    H = np.asarray(H, dtype=np.float64)
    if H.shape != (3, 3) or not np.isfinite(H).all() or np.linalg.matrix_rank(H) < 3:
        raise ValueError('Expected a finite, nonsingular homography.')
    projected = []
    for mask in (np.asarray(damage_mask, dtype=bool) & surface, surface):
        projected.append(cv2.warpPerspective(mask.astype(np.uint8), H, output_size,
                          flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT) != 0)
    damage, surface = projected
    if not surface.any():
        raise ValueError('No visible surface remains after rectification.')
    return damage & surface, surface
