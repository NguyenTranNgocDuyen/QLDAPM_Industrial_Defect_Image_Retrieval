"""Worker-owned v3 engine; reuse one segmentation for damage and preprocessing."""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import threading
from time import perf_counter
import uuid

import cv2
import numpy as np
from PIL import Image, ImageOps

from .damage_severity import binary_mask, evaluate_geometry, evaluate_observed_area, load_config, unavailable
from .corner_expansion import load_expansion_config
from .perspective import correct_perspective, PerspectiveCorrectionError
from .phone_segmenter import PhoneSegmenter, extract_corners_from_mask
from .pipeline import PipelineConfig, run_preprocessing_pipeline
from .surface_geometry import assess_surface_geometry
from phone_damage_v3_kit.phone_damage_v3.phone_body_roi import PhoneNotFound

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHTS = ROOT / 'phone_damage_v3_kit' / 'phone_damage_v3' / 'weights'


def decode_upright(data):
    with Image.open(io.BytesIO(data)) as image:
        return np.array(ImageOps.exif_transpose(image).convert('RGB'), dtype=np.uint8)


def rectify_masks(damage, surface, transform, size):
    damage = binary_mask(damage)
    surface = binary_mask(surface, damage.shape)
    transform = np.asarray(transform, dtype=np.float64)
    if transform.shape != (3, 3) or not np.isfinite(transform).all() or np.linalg.matrix_rank(transform) != 3:
        raise ValueError('Invalid homography.')
    warped = [cv2.warpPerspective(mask.astype(np.uint8), transform, size, flags=cv2.INTER_NEAREST,
                                 borderMode=cv2.BORDER_CONSTANT) != 0 for mask in (damage, surface)]
    return warped[0], warped[1]


def rectification_candidate(bgr, body, corners, aspect, surface, quality_config):
    """A geometry failure must not discard already valid source-model evidence."""
    try:
        rectified = correct_perspective(bgr, corners)
        if aspect is not None and surface in ('front', 'back', 'unknown'):
            height = rectified.output_height
            width = max(2, round((height - 1) * aspect) + 1)
            rectified = correct_perspective(bgr, corners, output_size=(width, height))
        matrix = rectified.transform_matrix
        if not np.isfinite(matrix).all() or np.linalg.matrix_rank(matrix) != 3:
            raise PerspectiveCorrectionError('Invalid homography')
        size = (rectified.output_width, rectified.output_height)
        quality = (assess_surface_geometry(body, corners, size, quality_config)
                   if quality_config else dict(usable=True, measurements={}, reasons=[]))
        return rectified, quality
    except (PerspectiveCorrectionError, cv2.error, np.linalg.LinAlgError) as exc:
        return None, dict(usable=False, measurements={}, reasons=['invalid_surface_geometry'],
                          error=f'{type(exc).__name__}: {exc}')


class DamageWorker:
    def __init__(self, weights_dir=None, device=None, output_dir=None, *, engine=None, segmenter=None):
        self.weights = Path(weights_dir or os.environ.get('PHONE_DAMAGE_WEIGHTS', DEFAULT_WEIGHTS)).resolve()
        self.config = load_config(os.environ.get('DAMAGE_SEVERITY_CONFIG'))
        self.corner_config = load_expansion_config()
        self.output = Path(output_dir or os.environ.get('DAMAGE_OUTPUT_DIR', ROOT / 'outputs' / 'damage-api')).resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        if engine is None:
            from phone_damage_v3_kit.phone_damage_v3 import ROIDamageEngine
            protocol = json.loads((self.weights / 'protocol.json').read_text('utf-8'))
            expected = dict(threshold=0.4, patch_size=512, overlap=128, context_size=512,
                            body_margin=0, inference_variant='native', phone_confidence=0.3)
            if any(protocol.get(k) != v for k, v in expected.items()):
                raise ValueError('Unsupported inference protocol; do not override v3 parameters.')
            phone = (self.weights / protocol['phone_model_file']).resolve()
            with phone.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != protocol['phone_model_sha256']:
                    raise ValueError('Phone checkpoint SHA256 differs from protocol.')
            engine = ROIDamageEngine(self.weights, load_phone_detector=False,
                                     device=device or os.environ.get('DAMAGE_DEVICE', 'cpu'))
            segmenter = PhoneSegmenter(phone, confidence=protocol['phone_confidence'],
                                       expected_sha256=engine.phone_model_sha256, device=str(engine.device))
            segmenter._load_model()
        self.engine, self.segmenter = engine, segmenter
        self.requests_processed = 0
        self.detector_calls = 0

    def analyze(self, data, *, surface='unknown', surface_aspect_ratio=None,
                full_surface_confirmed=False):
        # RF-DETR and preprocessing also share worker state: serialize the whole path.
        with self.lock:
            self.requests_processed += 1
            return self._analyze(data, surface, surface_aspect_ratio, full_surface_confirmed)

    def _analyze(self, data, surface, aspect, complete):
        start = perf_counter()
        rgb = decode_upright(data)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        h, w = rgb.shape[:2]
        if aspect is not None and (not math.isfinite(aspect) or not 0.1 <= aspect <= 10):
            raise ValueError('Surface width/height ratio must be finite, between 0.1 and 10.')
        scan_id = str(uuid.uuid4())
        folder = self.output / scan_id
        folder.mkdir()
        assets = {}

        def save(name, image):
            if not cv2.imwrite(str(folder / f'{name}.png'), image):
                raise OSError('Could not write PNG artifact.')
            assets[name] = f'/api/damage-assets/{scan_id}/{name}.png'

        save('source', bgr)
        detection = dict(status='not_processed', candidate_pixels_original=None, found=None,
                         threshold=self.engine.threshold, alarm_pixels=self.engine.alarm_pixels,
                         detector_loaded_in_damage_engine=False, inference_variant=self.engine.variant,
                         observed_surface=surface)
        severity = unavailable('not_processed', config=self.config)
        display = bgr
        coordinate_space = 'source'
        transform = None
        inference_ms = preprocessing_ms = postprocessing_ms = 0.0
        try:
            t = perf_counter()
            self.detector_calls += 1
            mask, confidence = self.segmenter.predict_mask(bgr)
            preprocessing_ms = (perf_counter() - t) * 1000
            if mask is None or not np.any(mask):
                detection['status'] = 'phone_not_found'
                severity = unavailable('phone_not_found', config=self.config)
            else:
                body = binary_mask(mask, rgb.shape[:2])
                save('body_original', body.astype(np.uint8) * 255)
                t = perf_counter()
                damage, pixels = self.engine.predict_with_body(rgb, body)
                inference_ms = (perf_counter() - t) * 1000
                damage = binary_mask(damage, body.shape)
                if pixels != int(np.count_nonzero(damage)):
                    raise ValueError('Damage count does not match source mask.')
                detection.update(status='candidates' if pixels else 'no_candidates',
                                 candidate_pixels_original=pixels, found=pixels >= self.engine.alarm_pixels,
                                 phone_confidence=float(confidence),
                                 phone_instances=self.segmenter.last_instance_count,
                                 target_selection='highest_confidence_single_instance')
                save('damage_original', damage.astype(np.uint8) * 255)
                clipped = bool(body[0].any() or body[-1].any() or body[:, 0].any() or body[:, -1].any())
                single = self.segmenter.last_instance_count == 1
                planar = surface in ('front', 'back', 'unknown')
                quality_config = self.config.get('image_geometry')
                selected_allowed = bool(quality_config and quality_config.get('allow_selected_target_estimate'))
                observation_reasons = []
                if clipped:
                    observation_reasons.append('phone_touches_source_border')
                if not single:
                    observation_reasons.append('multiple_phones_need_target_confirmation')
                if not planar:
                    observation_reasons.append('surface_not_a_confirmed_planar_face')

                def observed_fallback(reasons):
                    if planar and (single or selected_allowed) and self.config.get('observed_area_fallback', {}).get('enabled'):
                        return evaluate_observed_area(damage, body, reasons=reasons, config=self.config)
                    result = unavailable(reasons[0], 'needs_review', self.config)
                    result['reasons'] = reasons
                    return result

                corner_diagnostics = {}
                try:
                    corners = extract_corners_from_mask(mask, image_shape=body.shape,
                                                        corner_diagnostics=corner_diagnostics)
                except (PerspectiveCorrectionError, cv2.error, np.linalg.LinAlgError):
                    corners = None
                t = perf_counter()
                if corners is None:
                    severity = observed_fallback(['missing_surface_corners'] + observation_reasons)
                    overlay_mask = damage
                else:
                    # Audit in source coordinates: green mask boundary, yellow
                    # crop, red pixels of the original mask outside the crop.
                    polygon = np.zeros(body.shape, np.uint8)
                    cv2.fillConvexPoly(polygon, np.round(corners).astype(np.int32), 1)
                    preview = bgr.copy()
                    preview[body & (polygon == 0)] = (0, 0, 255)
                    contours, _ = cv2.findContours(body.astype(np.uint8), cv2.RETR_EXTERNAL,
                                                  cv2.CHAIN_APPROX_SIMPLE)
                    cv2.drawContours(preview, contours, -1, (0, 255, 0), 1)
                    cv2.polylines(preview, [np.round(corners).astype(np.int32)], True, (0, 255, 255), 2)
                    save('corners', preview)
                    # Keep the existing corner estimator; use a supplied physical aspect
                    # only for planar faces. No inferred aspect from an occluded bbox.
                    rectified, quality = rectification_candidate(bgr, body, corners, aspect, surface, quality_config)
                    usable = rectified is not None and planar and (single or selected_allowed) and not clipped and quality['usable']
                    image_estimate = bool(usable and quality_config and quality_config['enabled'])
                    expanded = corner_diagnostics.get('applied', False)
                    if usable:
                        size = (rectified.output_width, rectified.output_height)
                        warped_damage, warped_surface = rectify_masks(damage, body, rectified.transform_matrix, size)
                        display = rectified.image
                        coordinate_space = 'processed'
                        transform = rectified.transform_matrix.tolist()
                        save('damage_rectified', warped_damage.astype(np.uint8) * 255)
                        save('surface_rectified', warped_surface.astype(np.uint8) * 255)
                        severity = evaluate_geometry(warped_damage, warped_surface,
                            full_surface_size=size if aspect is not None or image_estimate else None,
                            geometry_confirmed=single and aspect is not None and not expanded,
                            observation_complete=complete, config=self.config,
                            allow_image_estimate=image_estimate)
                        overlay_mask = warped_damage
                    else:
                        # Preserve ALL source candidates when a crop/homography
                        # cannot support full-face L/W; do not display a clipped crop.
                        severity = observed_fallback(quality['reasons'] + observation_reasons)
                        display = bgr
                        overlay_mask = damage
                    severity['geometry_diagnostics'] = quality
                    quality['corner_expansion'] = corner_diagnostics
                    if expanded:
                        severity['limitations'].append('surface_corners_approximated_from_mask')
                    severity['reasons'] = list(dict.fromkeys(severity['reasons'] + quality['reasons'] + observation_reasons))
                    # Reuse existing illumination/channels AFTER inference. Never feed
                    # these enhanced pixels, or rectified pixels, into the v3 engine.
                    preprocessed = run_preprocessing_pipeline(display,
                        PipelineConfig(auto_perspective=False, illumination_method='clahe'))
                    save('preprocessed', preprocessed.preprocessed_image)
                if not single and severity['estimation_basis'] is not None:
                    severity['needs_review'] = True
                    severity['limitations'].append('target_automatically_selected')
                if pixels and not detection['found']:
                    detection['status'] = 'below_alarm_threshold'
                    severity.update(status='needs_review', needs_review=True)
                    severity['reasons'].append('below_alarm_threshold')
                overlay = display.copy()
                overlay[overlay_mask] = np.round(overlay[overlay_mask] * 0.55 + np.array([0, 64, 255]) * 0.45).astype(np.uint8)
                save('overlay', overlay)
                postprocessing_ms = (perf_counter() - t) * 1000
        except PhoneNotFound:
            detection.update(status='phone_not_found', found=None)
            severity = unavailable('phone_not_found', config=self.config)
        except Exception as exc:
            # A failed computation always carries an explicit non-healthy state.
            detection['status'] = 'processing_error'
            detection['found'] = None
            severity = unavailable('processing_error', config=self.config)
            detection['error'] = f'{type(exc).__name__}: {exc}'
        save('display', display)
        result = dict(scanId=scan_id, success=detection['status'] != 'processing_error',
                      hasDefect=detection['found'], status=severity['status'],
                      sourceImage=dict(width=w, height=h, url=assets['source'], coordinateSpace='source'),
                      displayImage=dict(width=display.shape[1], height=display.shape[0],
                                        url=assets.get('overlay', assets['display']), coordinateSpace=coordinate_space),
                      processing=dict(preprocessingMs=preprocessing_ms, inferenceMs=inference_ms,
                                      postprocessingMs=postprocessing_ms, totalMs=(perf_counter()-start)*1000),
                      detections=[], damage=detection, severity=severity, assets=assets,
                      transformMatrix=transform)
        (folder / 'result.json').write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2), 'utf-8')
        return result
