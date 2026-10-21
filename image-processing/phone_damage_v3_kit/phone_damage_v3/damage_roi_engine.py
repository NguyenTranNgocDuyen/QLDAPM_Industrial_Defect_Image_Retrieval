"""Live inference uses exactly the phone/context/detail protocol of training."""
import json
from pathlib import Path
import threading

import numpy as np
import torch

from .phone_body_roi import PhoneBodySegmenter, PhoneNotFound
from .phone_damage_roi import ARCHITECTURE
from .damage_roi_inference import probability, VARIANTS
from .phone_data import digest
from .train_damage_roi import load_model


class ROIDamageEngine:
    def __init__(self, model_dir, threshold=None, device=None, *, load_phone_detector=True,
                 phone_model_path=None):
        self.model_dir = Path(model_dir)
        protocol = json.loads((self.model_dir/'protocol.json').read_text(encoding='utf-8'))
        if protocol['architecture'] != ARCHITECTURE:
            raise ValueError('This bundle is not a phone-context damage model.')
        model_path = self.model_dir/'model.pt'
        phone_path = Path(phone_model_path) if phone_model_path is not None else self.model_dir/protocol['phone_model_file']
        if digest(model_path) != protocol['model_sha256']:
            raise ValueError('Damage model hash does not match its protocol.')
        self.phone_model_sha256 = protocol['phone_model_sha256']
        if load_phone_detector and digest(phone_path) != self.phone_model_sha256:
            raise ValueError('Phone model hash does not match its protocol.')
        torch.set_num_threads(4)
        self.device = torch.device(device or ('cuda:0' if torch.cuda.is_available() else 'cpu'))
        self.model, saved = load_model(model_path, self.device)
        for key in ('patch_size', 'overlap', 'context_size', 'body_margin', 'phone_model_sha256'):
            if saved[key] != protocol[key]:
                raise ValueError('Inference protocol differs from checkpoint: '+key)
        self.patch_size, self.overlap = saved['patch_size'], saved['overlap']
        self.context_size, self.margin = saved['context_size'], saved['body_margin']
        self.variant = protocol.get('inference_variant','native')
        if self.variant not in VARIANTS or saved.get('inference_variant','native') != self.variant:
            raise ValueError('Inference scale variant mismatch.')
        self.threshold = float(protocol['threshold'] if threshold is None else threshold)
        self.alarm_pixels = int(protocol.get('alarm_pixels',200))
        if self.alarm_pixels < 1:
            raise ValueError('Invalid image alarm threshold.')
        if not np.isfinite(self.threshold) or not 0 < self.threshold < 1:
            raise ValueError('Invalid damage threshold.')
        self.phone = (PhoneBodySegmenter(phone_path, device='cpu', threshold=protocol['phone_confidence'])
                      if load_phone_detector else None)
        self.lock = threading.Lock()

    def _threshold(self, threshold):
        threshold = self.threshold if threshold is None else threshold
        if not np.isfinite(threshold) or not 0 < threshold < 1:
            raise ValueError('Invalid damage threshold.')
        return float(threshold)

    @staticmethod
    def _rgb(rgb):
        if not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3 or min(rgb.shape[:2]) < 1:
            raise ValueError('Expected an upright RGB uint8 image, shape H,W,3.')

    @staticmethod
    def _body(rgb, body):
        body = np.asarray(body)
        if body.ndim != 2 or body.shape != rgb.shape[:2]:
            raise ValueError('Phone mask must match the original RGB image coordinates.')
        if body.dtype != np.bool_ and (not np.issubdtype(body.dtype, np.integer) or not np.isin(body,[0,1,255]).all()):
            raise ValueError('Phone mask must be binary bool or integer values 0/1/255, not a probability map.')
        body = body != 0
        if not body.any():
            raise PhoneNotFound('The supplied phone mask is empty.')
        return body

    def _damage_mask(self, rgb, body, threshold):
        prob = probability(self.model, rgb, body, self.patch_size, self.overlap,
                           self.context_size, self.device, self.margin, self.variant)
        prediction = prob >= threshold
        return prediction, int(prediction.sum())

    def predict_with_body(self, rgb, body_mask, threshold=None):
        """Reuse the app's phone mask on the SAME upright, unwarped RGB image.

        This method never runs the phone detector. The caller should use the
        same detector weights identified by self.phone_model_sha256. Four
        corners alone do not replace the original phone segmentation mask.
        """
        self._rgb(rgb)
        threshold = self._threshold(threshold)
        body = self._body(rgb, body_mask)
        with self.lock:
            return self._damage_mask(rgb, body, threshold)

    def predict(self, rgb, threshold=None):
        self._rgb(rgb)
        threshold = self._threshold(threshold)
        if self.phone is None:
            raise ValueError('Phone detector is disabled; use predict_with_body(rgb, body_mask).')
        with self.lock:
            body, _ = self.phone.predict(rgb)
            return self._damage_mask(rgb, body, threshold)
