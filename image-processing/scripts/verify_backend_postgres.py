"""Exercise running Spring Boot + real damage worker + PostgreSQL, without mocks.

Leaves marked integration scans in history and PNG/JSON evidence in outputs.
Never invents physical aspect or confirms visibility of unverified source photos.
"""
import argparse
import io
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from PIL import Image
from defect_vision.damage_severity import evaluate_geometry

ROOT = Path(__file__).resolve().parents[1]


def get_json(url):
    with urlopen(url, timeout=300) as response:
        return json.load(response)


def upload(base, data, filename, fields):
    boundary = 'damage-test-' + uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode())
    parts.extend((data, f'\r\n--{boundary}--\r\n'.encode()))
    request = Request(base + '/api/detections', data=b''.join(parts),
                      headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    with urlopen(request, timeout=300) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8080')
    parser.add_argument('--worker-url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    output = ROOT / 'outputs' / 'backend-postgres-verification'
    output.mkdir(parents=True, exist_ok=True)
    start_health = get_json(args.worker_url + '/health')
    blank = io.BytesIO(); Image.new('RGB', (640, 480), 'white').save(blank, format='PNG')
    inputs = [(p.name, p.read_bytes()) for p in sorted((ROOT / 'data').glob('*.jpeg'))]
    inputs.append(('blank_white.png', blank.getvalue()))
    records = []
    for name, data in inputs:
        result = upload(args.base_url, data, 'integration-' + name,
                        dict(surface='front', deviceInfo='integration-test-postgres-20261020'))
        assert result['success'], result
        if name in ('123k.jpeg', '394k.jpeg'):
            assert result['severity']['estimated_severity'] is not None
            assert result['severity']['estimation_basis'] == 'image_geometry'
            assert result['severity']['locations']
        elif name == '329k.jpeg':
            assert result['severity']['estimation_basis'] == 'observed_area_only'
            assert result['severity']['estimated_severity'] is not None
        else:
            assert result['severity']['estimated_severity'] is None
        assert result['severity']['needs_review'] is True
        scan_id = result['scanId']
        reread = get_json(args.base_url + '/api/detections/' + scan_id)
        assert reread == result, 'Persistence changed result JSON'
        assert get_json(args.base_url + '/api/scans/' + scan_id) == result
        folder = output / scan_id
        folder.mkdir(exist_ok=True)
        for asset, path in result['assets'].items():
            with urlopen(args.base_url + path, timeout=30) as response:
                assert response.headers['Content-Type'] == 'image/png'
                png = response.read()
            assert png.startswith(b'\x89PNG')
            (folder / (asset + '.png')).write_bytes(png)
            decoded = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED)
            if asset in ('body_original', 'damage_original', 'source'):
                assert decoded.shape[:2] == (result['sourceImage']['height'], result['sourceImage']['width'])
            if asset in ('damage_rectified', 'surface_rectified', 'display', 'overlay'):
                assert decoded.shape[:2] == (result['displayImage']['height'], result['displayImage']['width'])
        if name == 'blank_white.png':
            assert result['hasDefect'] is None and result['damage']['found'] is None
            assert result['damage']['status'] == 'phone_not_found'
            assert result['severity']['area_ratio'] is None
        else:
            assert result['damage']['candidate_pixels_original'] > 0 and result['damage']['threshold'] == 0.4
        (folder / 'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), 'utf-8')
        records.append(dict(image=name, scan_id=scan_id, status=result['status'],
                            estimated_severity=result['severity']['estimated_severity'],
                            estimation_basis=result['severity']['estimation_basis'],
                            area_ratio=result['severity']['area_ratio'],
                            skeleton_length_ratio=result['severity']['skeleton_length_ratio'],
                            width_ratio=result['severity']['width_ratio'],
                            locations=result['severity']['locations'],
                            candidate_pixels=result['damage']['candidate_pixels_original'],
                            reasons=result['severity']['reasons'], persisted_exactly=True,
                            png_assets=len(result['assets'])))
        print(json.dumps(records[-1]), flush=True)
    history = get_json(args.base_url + '/api/scans?' + urlencode(dict(size=100)))
    history_ids = {item['scanId'] for item in history['content']}
    assert all(record['scan_id'] in history_ids for record in records)
    for fields, payload in [(dict(surface='front'), b''), (dict(surfaceAspectRatio='NaN'), b'x')]:
        try:
            upload(args.base_url, payload, 'integration-invalid.jpg', fields)
            raise AssertionError('Invalid upload accepted')
        except HTTPError as error:
            assert error.code == 400
    health = get_json(args.worker_url + '/health')
    assert health['detector_calls'] - start_health['detector_calls'] == len(records)
    assert health['requests_processed'] - start_health['requests_processed'] == len(records)
    # These are synthetic masks with known geometry, not estimates for the photos above.
    fixtures = {}
    for name, side, expected in [('point', 1, 'minor'), ('medium_thick_patch', 150, 'moderate'),
                                 ('wide_thick_patch', 250, 'severe')]:
        mask = np.zeros((1024, 1024), bool); mask[400:400+side, 400:400+side] = True
        result = evaluate_geometry(mask, np.ones_like(mask), full_surface_size=(1024, 1024),
                                   geometry_confirmed=True, observation_complete=True)
        assert result['estimated_severity'] == expected
        fixtures[name] = result
    report = dict(database='PostgreSQL Docker, no repository mocks', records=records,
                  worker_before=start_health, worker_after=health,
                  geometry_demonstrations_only=fixtures, severity_accuracy_evaluated=False)
    (output / 'verification.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), 'utf-8')
    print('PASS: real upload, persisted JSON, history, PNGs, null evidence, validation, detector reuse, three geometry levels.', flush=True)


if __name__ == '__main__':
    main()
