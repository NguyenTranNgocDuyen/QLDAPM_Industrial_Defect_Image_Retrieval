"""Frozen RF-DETR phone-body segmentation; source RGB and damage labels stay intact.

The supplied phone_detect.pt is an RFDETRSegSmall state dict, not a YOLO model.
No-detection is an explicit failure, never a full-image or empty healthy fallback.
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
import torch

from .phone_data import ROOT, digest


DEFAULT_PHONE_MODEL = ROOT / 'models/phone_detect.pt'


class PhoneNotFound(ValueError):
    pass


def expanded_body(mask, margin_fraction=0.005):
    """Small outward allowance for segmentation boundary error and chipped edges."""
    mask = np.asarray(mask, dtype=bool)
    if mask.ndim != 2 or not mask.any():
        raise PhoneNotFound('No usable phone-body mask.')
    if not 0 <= margin_fraction <= 0.05:
        raise ValueError('margin_fraction must be between 0 and 0.05.')
    ys, xs = np.nonzero(mask)
    radius = int(np.ceil(min(np.ptp(xs) + 1, np.ptp(ys) + 1) * margin_fraction))
    if not radius:
        return mask.copy()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*radius+1, 2*radius+1))
    return cv2.dilate(mask.astype(np.uint8), kernel).astype(bool)


class PhoneBodySegmenter:
    def __init__(self, model_path=DEFAULT_PHONE_MODEL, device='cpu', threshold=0.3):
        from rfdetr import RFDETRSegSmall

        self.path = Path(model_path).resolve()
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        if not 0 < threshold < 1:
            raise ValueError('Invalid phone confidence threshold.')
        self.sha256 = digest(self.path)
        self.threshold = threshold
        self.model = RFDETRSegSmall(pretrain_weights=str(self.path), num_classes=1,
                                    device=str(device))
        # Reject architecture mismatches rather than accepting randomly initialized layers.
        weights = torch.load(self.path, map_location='cpu', weights_only=True)['model']
        incompatible = self.model.model.model.load_state_dict(weights, strict=False)
        # New RF-DETR versions add this deterministic keypoint schema buffer;
        # it is not a learned weight and is unused by this segmentation model.
        missing = set(incompatible.missing_keys) - {'_kp_active_mask'}
        if missing or incompatible.unexpected_keys:
            raise ValueError(f'Phone architecture mismatch: {missing}, {incompatible.unexpected_keys}')
        self.model.model.model.requires_grad_(False)

    def predict(self, rgb):
        detections = self.model.predict(Image.fromarray(rgb), threshold=self.threshold)
        if detections.mask is None or not len(detections):
            raise PhoneNotFound('Phone body not detected; inspect image or select ROI manually.')
        # This checkpoint has one foreground class (RF-DETR id 1). Preserve all
        # detected phones, rather than silently discarding smaller devices.
        masks = np.asarray(detections.mask, dtype=bool)
        if masks.shape[1:] != rgb.shape[:2]:
            raise ValueError('Phone mask is not in original image coordinates.')
        body = masks.any(axis=0)
        if not body.any():
            raise PhoneNotFound('Detected phone has an empty mask.')
        return body, dict(instances=len(detections),
                          confidences=detections.confidence.astype(float).tolist())
