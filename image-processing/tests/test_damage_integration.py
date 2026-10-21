from concurrent.futures import ThreadPoolExecutor
import io
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

import cv2
import numpy as np
import pytest
from PIL import Image

from defect_vision.damage_service import DamageWorker, decode_upright, rectify_masks
from defect_vision.damage_api import DamageHTTPServer, make_handler
from defect_vision.perspective import correct_perspective
from phone_damage_v3_kit.phone_damage_v3 import PhoneNotFound


class Engine:
    threshold, alarm_pixels, variant = 0.4, 200, 'native'
    def __init__(self): self.calls = 0; self.seen = []
    def predict_with_body(self, rgb, mask):
        self.calls += 1
        self.seen.append(rgb.copy())
        d = np.zeros(mask.shape, bool)
        d[40, 30:170] = True
        return d, int(d.sum())


class Segmenter:
    last_instance_count = 1
    def __init__(self): self.calls = 0
    def predict_mask(self, bgr):
        self.calls += 1
        mask = np.zeros(bgr.shape[:2], np.uint8)
        mask[20:180, 20:180] = 255
        return mask, 0.9


def image_bytes():
    rgb = np.zeros((200, 200, 3), np.uint8)
    rgb[..., 0] = 230
    stream = io.BytesIO()
    Image.fromarray(rgb).save(stream, format='PNG')
    return stream.getvalue()


def worker(tmp_path):
    return DamageWorker(output_dir=tmp_path, engine=Engine(), segmenter=Segmenter())


def test_exif_and_rgb():
    rgb = np.zeros((30, 50, 3), np.uint8)
    rgb[..., 0] = 240
    stream = io.BytesIO()
    exif = Image.Exif(); exif[274] = 6
    Image.fromarray(rgb).save(stream, format='JPEG', exif=exif)
    decoded = decode_upright(stream.getvalue())
    assert decoded.shape == (50, 30, 3)
    assert decoded[0, 0, 0] > 230 and decoded[0, 0, 2] < 10


def test_warped_masks_match_rgb_target_and_source_is_unchanged():
    mask = np.zeros((120, 150), np.uint8)
    cv2.fillConvexPoly(mask, np.int32([[30, 10], [120, 20], [130, 100], [20, 100]]), 255)
    damage = np.zeros_like(mask); damage[50:55, 55:90] = 255
    rgb = np.repeat(damage[..., None], 3, axis=2)
    p = correct_perspective(rgb, [[30,10],[120,20],[130,100],[20,100]], interpolation=cv2.INTER_NEAREST)
    warped, surface = rectify_masks(damage, mask, p.transform_matrix, (p.output_width, p.output_height))
    np.testing.assert_array_equal(warped, p.image[..., 0] != 0)
    assert surface.shape == p.image.shape[:2]
    assert set(np.unique(warped)).issubset({False, True})
    with pytest.raises(ValueError): rectify_masks(damage, mask[:100], p.transform_matrix, (50,50))
    with pytest.raises(ValueError): rectify_masks(damage, mask, np.zeros((3,3)), (50,50))


def test_worker_reuses_models_one_detector_call_per_image_and_preserves_small_candidates(tmp_path):
    w = worker(tmp_path)
    model_id = id(w.engine)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: w.analyze(image_bytes(), surface='front',
            surface_aspect_ratio=1, full_surface_confirmed=True), range(3)))
    assert w.engine.calls == w.segmenter.calls == w.detector_calls == 3
    assert id(w.engine) == model_id
    for r in results:
        assert r['damage']['status'] == 'below_alarm_threshold'
        assert r['damage']['candidate_pixels_original'] == 140
        assert r['damage']['found'] is False
        assert r['severity']['needs_review'] is True
        assert r['severity']['estimated_severity'] is not None
        assert r['severity']['skeleton_length_ratio'] > 0.5
        path = tmp_path / r['scanId'] / 'damage_original.png'
        assert np.count_nonzero(cv2.imread(str(path), 0)) == 140
        assert r['displayImage']['width'] == r['displayImage']['height']
        json.dumps(r, allow_nan=False)
    np.testing.assert_array_equal(w.engine.seen[0][0,0], [230,0,0])


def test_no_phone_wrong_shape_and_model_errors_do_not_mean_healthy(tmp_path):
    w = worker(tmp_path)
    w.segmenter.predict_mask = lambda _: (None, 0)
    r = w.analyze(image_bytes())
    assert r['damage']['status'] == 'phone_not_found'
    assert r['hasDefect'] is None and w.engine.calls == 0
    w.segmenter.predict_mask = lambda _: (np.ones((5,5), bool), 0.9)
    r = w.analyze(image_bytes())
    assert r['damage']['status'] == 'processing_error'
    assert r['hasDefect'] is None and r['severity']['area_ratio'] is None
    w.segmenter = Segmenter()
    def broken(*_): raise RuntimeError('model failed')
    w.engine.predict_with_body = broken
    r = w.analyze(image_bytes())
    assert not r['success'] and r['hasDefect'] is None
    assert r['severity']['estimated_severity'] is None
    def not_found(*_): raise PhoneNotFound('no phone')
    w.engine.predict_with_body = not_found
    r = w.analyze(image_bytes())
    assert r['damage']['status'] == 'phone_not_found' and r['hasDefect'] is None


def test_multiple_phones_and_unknown_or_incomplete_geometry_need_review(tmp_path):
    w = worker(tmp_path)
    w.segmenter.last_instance_count = 2
    r = w.analyze(image_bytes(), surface='front', surface_aspect_ratio=1, full_surface_confirmed=True)
    assert r['success']
    assert r['severity']['estimated_severity'] is not None
    assert r['severity']['needs_review']
    assert 'target_automatically_selected' in r['severity']['limitations']
    assert 'multiple_phones_need_target_confirmation' in r['severity']['reasons']
    w.segmenter.last_instance_count = 1
    r = w.analyze(image_bytes(), surface='edgeTop', surface_aspect_ratio=1, full_surface_confirmed=True)
    assert r['severity']['estimated_severity'] is None


def test_http_api_and_png_roundtrip(tmp_path):
    w = worker(tmp_path)
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(w))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        request = Request(base + '/analyze?surface=front&aspect=1&complete=true', data=image_bytes(),
                          headers={'Content-Type': 'application/octet-stream'})
        with urlopen(request) as response: r = json.load(response)
        with urlopen(base + r['assets']['damage_original']) as response:
            assert response.headers['Content-Type'] == 'image/png'
            assert response.read().startswith(b'\x89PNG')
        with urlopen(base + '/health') as response: health = json.load(response)
        assert health['detector_calls'] == 1 and health['requests_processed'] == 1
        assert not health['detector_loaded_in_damage_engine']
        assert health['corner_config_version'] == 'corner-expansion-v2-unvalidated'
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_active_worker_port_cannot_be_shared_with_another_worker(tmp_path):
    server = DamageHTTPServer(('127.0.0.1', 0), make_handler(worker(tmp_path)))
    try:
        with pytest.raises(OSError):
            DamageHTTPServer(server.server_address, make_handler(worker(tmp_path)))
    finally:
        server.server_close()


def test_image_estimate_needs_no_handset_or_dimensions_and_retains_limitations(tmp_path):
    w = worker(tmp_path)
    original_predict = w.engine.predict_with_body
    def predict(rgb, body):
        d, _ = original_predict(rgb, body)
        d[41, 30:170] = True
        return d, int(d.sum())
    w.engine.predict_with_body = predict
    result = w.analyze(image_bytes())
    severity = result['severity']
    assert severity['status'] == 'estimated'
    assert severity['estimated_severity'] == 'minor'
    assert severity['estimation_basis'] == 'image_geometry'
    assert severity['needs_review'] is True  # Unverified aspect/visibility remain explicit.
    assert severity['heuristic_unvalidated'] is True
    assert set(severity['limitations']) == {'aspect_approximated_from_image', 'visibility_not_verified'}
    assert severity['geometry_diagnostics']['usable'] is True
    mask = cv2.imread(str(tmp_path / result['scanId'] / 'damage_rectified.png'), 0) != 0
    surface = cv2.imread(str(tmp_path / result['scanId'] / 'surface_rectified.png'), 0) != 0
    assert sum(item['candidate_pixels_rectified'] for item in severity['locations']) == int((mask & surface).sum())
    assert sum(item['candidate_share'] for item in severity['locations']) == pytest.approx(1)
    assert w.engine.seen[0].shape == (200, 200, 3)
    assert w.engine.calls == w.segmenter.calls == 1


@pytest.mark.parametrize('case', ['clipped', 'occluded', 'multiple', 'edge'])
def test_geometry_problems_keep_warnings_but_allow_observed_estimate(tmp_path, case):
    w = worker(tmp_path)
    if case in ('clipped', 'occluded'):
        body, _ = w.segmenter.predict_mask(np.zeros((200,200,3), np.uint8))
        if case == 'clipped': body[:30, 20:180] = 255
        if case == 'occluded': body[70:130, 100:180] = 0
        w.segmenter.predict_mask = lambda _: (body, 0.9)
    if case == 'multiple': w.segmenter.last_instance_count = 2
    result = w.analyze(image_bytes(), surface='edgeTop' if case == 'edge' else 'front')
    assert result['success']
    severity = result['severity']
    if case == 'edge':
        assert severity['estimated_severity'] is None
    elif case == 'multiple':
        assert severity['estimated_severity'] is not None
        assert 'target_automatically_selected' in severity['limitations']
    else:
        assert severity['estimated_severity'] is not None
        assert severity['estimation_basis'] == 'observed_area_only'
        assert severity['skeleton_length_ratio'] is None and severity['width_ratio'] is None
        assert result['displayImage']['coordinateSpace'] == 'source'
        assert result['transformMatrix'] is None
        assert 'damage_rectified' not in result['assets']
        source = cv2.imread(str(tmp_path / result['scanId'] / 'source.png'))
        display = cv2.imread(str(tmp_path / result['scanId'] / 'display.png'))
        np.testing.assert_array_equal(source, display)
        assert sum(v['candidate_pixels_source'] for v in severity['locations']) == 140
        assert 'below_alarm_threshold' in severity['reasons']
    assert result['severity']['needs_review'] is True


def test_missing_corners_uses_source_area_without_repeating_inference(tmp_path, monkeypatch):
    w = worker(tmp_path)
    monkeypatch.setattr('defect_vision.damage_service.extract_corners_from_mask', lambda *a, **k: None)
    result = w.analyze(image_bytes(), surface='front')
    assert result['success'] and result['severity']['estimated_severity'] is not None
    assert result['severity']['estimation_basis'] == 'observed_area_only'
    assert 'missing_surface_corners' in result['severity']['reasons']
    assert result['displayImage']['coordinateSpace'] == 'source'
    assert w.engine.calls == w.segmenter.calls == 1


def test_previous_strict_config_can_disable_partial_and_selected_target_estimates(tmp_path):
    from defect_vision.damage_severity import load_config
    w = worker(tmp_path)
    w.config = load_config('defect_vision/severity.v2.json')
    w.segmenter.last_instance_count = 2
    result = w.analyze(image_bytes(), surface='front')
    assert result['success'] and result['severity']['estimated_severity'] is None


def test_invalid_homography_preserves_model_result_and_source_overlay(tmp_path, monkeypatch):
    from defect_vision.perspective import PerspectiveCorrectionError
    def fail(*args, **kwargs):
        raise PerspectiveCorrectionError('degenerate geometry')
    w = worker(tmp_path)
    monkeypatch.setattr('defect_vision.damage_service.correct_perspective', fail)
    result = w.analyze(image_bytes(), surface='front')
    assert result['success'] and result['severity']['estimated_severity'] is not None
    assert result['severity']['estimation_basis'] == 'observed_area_only'
    assert 'invalid_surface_geometry' in result['severity']['reasons']
    assert result['displayImage']['coordinateSpace'] == 'source'
    assert w.engine.calls == w.segmenter.calls == 1
