"""Replay saved captures through BE/worker/database and audit source-mask parity.

Example: python scripts/verify_corner_expansion.py --case front outputs/damage-api/ID/result.json
Creates marked test scans; leaves previous captures and results untouched.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np

from verify_backend_postgres import get_json, upload
from defect_vision.corner_expansion import load_expansion_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', nargs=2, action='append', required=True, metavar=('SURFACE', 'OLD_RESULT'))
    parser.add_argument('--base-url', default='http://127.0.0.1:8080')
    parser.add_argument('--worker-url', default='http://127.0.0.1:8000')
    parser.add_argument('--output-dir', type=Path, default=Path('outputs/corner-expansion-verification'))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    before = get_json(args.worker_url + '/health')
    assert before['corner_config_version'] == load_expansion_config()['version'], 'Restart the worker first'
    cases = []
    for surface, old_file in args.case:
        old_path = Path(old_file)
        old = json.loads(old_path.read_text('utf-8'))
        source = old_path.parent / 'source.png'
        result = upload(args.base_url, source.read_bytes(), 'corner-replay-' + surface + '.png',
                        dict(surface=surface, deviceInfo='corner-expansion-verification'))
        assert result['success'], result
        assert get_json(args.base_url + '/api/scans/' + result['scanId']) == result
        assert get_json(args.base_url + '/api/detections/' + result['scanId']) == result
        severity = result['severity']
        quality = severity['geometry_diagnostics']
        audit = quality['corner_expansion']
        assert audit['applied'] and quality['usable']
        assert audit['after']['mask_coverage'] >= 0.98
        assert audit['after']['background_ratio'] <= 0.08
        assert severity['estimated_severity'] is not None
        assert severity['needs_review'] and severity['heuristic_unvalidated']
        assert severity['estimation_basis'] == 'image_geometry'
        assert 'surface_corners_approximated_from_mask' in severity['limitations']
        assert result['damage']['candidate_pixels_original'] == old['damage']['candidate_pixels_original']
        assert not result['damage']['detector_loaded_in_damage_engine']
        folder = args.output_dir / result['scanId']
        folder.mkdir(exist_ok=True)
        (folder / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
        assets = {}
        for name, url in result['assets'].items():
            with urlopen(args.base_url + url, timeout=30) as response:
                png = response.read()
                assert response.headers['Content-Type'] == 'image/png'
            assert png.startswith(b'\x89PNG')
            (folder / (name + '.png')).write_bytes(png)
            assets[name] = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED)
        for name in ('body_original', 'damage_original'):
            saved = cv2.imread(str(old_path.parent / (name + '.png')), 0)
            np.testing.assert_array_equal(assets[name], saved)
        size = (result['displayImage']['width'], result['displayImage']['height'])
        transform = np.asarray(result['transformMatrix'], np.float64)
        for source_name, target_name in [('body_original', 'surface_rectified'),
                                         ('damage_original', 'damage_rectified')]:
            expected = cv2.warpPerspective(assets[source_name], transform, size, flags=cv2.INTER_NEAREST)
            np.testing.assert_array_equal(assets[target_name], expected)
            assert set(np.unique(expected)) <= {0, 255}
        assert assets['display'].shape[:2] == assets['damage_rectified'].shape
        assert assets['overlay'].shape == assets['display'].shape
        assert assets['corners'].shape == assets['source'].shape
        cases.append(dict(surface=surface, scan_id=result['scanId'],
                          previous_scan_artifact=old['scanId'], expansion=audit,
                          estimated_severity=severity['estimated_severity'],
                          candidate_pixels_original=result['damage']['candidate_pixels_original'],
                          source_masks_identical=True, masks_exactly_match_warp=True,
                          damage_array_sha256=hashlib.sha256(assets['damage_original'].tobytes()).hexdigest()))
    after = get_json(args.worker_url + '/health')
    assert after['requests_processed'] - before['requests_processed'] == len(cases)
    assert after['detector_calls'] - before['detector_calls'] == len(cases)
    report = dict(cases=cases, worker_before=before, worker_after=after,
                  severity_accuracy_evaluated=False)
    path = args.output_dir / 'backend-replay.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))
    print(f'Report: {path.resolve()}')


if __name__ == '__main__':
    main()
