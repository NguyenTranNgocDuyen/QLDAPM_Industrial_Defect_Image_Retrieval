"""Optional scale views. Shared by validation and the live engine; no GT access."""
import cv2
import numpy as np

from .phone_body_roi import expanded_body
from .phone_damage_roi import body_bbox, roi_probability


VARIANTS = ('native', 'phone1024', 'native_phone1024_max')


def phone_scale_probability(model, rgb, body, patch_size, overlap, context_size, device, margin):
    x0, y0, x1, y1 = body_bbox(body)
    view = rgb[y0:y1, x0:x1]
    mask = body[y0:y1, x0:x1]
    h, w = mask.shape
    scale = min(1., 1024/max(h, w))
    if scale < 1:
        size = (max(1, round(w*scale)), max(1, round(h*scale)))
        view = cv2.resize(view, size, interpolation=cv2.INTER_AREA)
        mask = cv2.resize(mask.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST) > 0
    prob = roi_probability(model, view, mask, patch_size, overlap, context_size, device, margin)
    prob = cv2.resize(prob, (w, h), interpolation=cv2.INTER_LINEAR)
    result = np.zeros(body.shape, dtype=np.float32)
    result[y0:y1, x0:x1] = prob
    result[~expanded_body(body, margin)] = 0
    return result


def probability(model, rgb, body, patch_size, overlap, context_size, device, margin=0, variant='native'):
    if variant not in VARIANTS:
        raise ValueError('Unknown inference variant.')
    if variant == 'phone1024':
        return phone_scale_probability(model, rgb, body, patch_size, overlap, context_size, device, margin)
    native = roi_probability(model, rgb, body, patch_size, overlap, context_size, device, margin)
    if variant == 'native':
        return native
    scaled = phone_scale_probability(model, rgb, body, patch_size, overlap, context_size, device, margin)
    return np.maximum(native, scaled)
