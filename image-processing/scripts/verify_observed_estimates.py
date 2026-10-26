"""Replay saved source PNG/masks through BE and verify flexible estimates.

--case takes a surface and saved before.json/result.json. That folder must also
contain source.png, body_original.png and damage_original.png. Leaves marked scans.
"""
import argparse
import json
from pathlib import Path
import sys
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from verify_backend_postgres import get_json, upload
from defect_vision.damage_severity import load_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', nargs=2, action='append', required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:8080')
    parser.add_argument('--worker-url', default='http://127.0.0.1:8000')
    parser.add_argument('--output-dir', type=Path, default=Path('outputs/partial-estimate-verification/replay'))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    before = get_json(args.worker_url + '/health')
    assert before['severity_config_version'] == load_config()['version']
    records = []
    for surface, path in args.case:
        old_path = Path(path)
        old = json.loads(old_path.read_text('utf-8-sig'))
        result = upload(args.base_url, (old_path.parent / 'source.png').read_bytes(),
                        'observed-replay-' + surface + '.png',
                        dict(surface=surface, deviceInfo='observed-estimate-verification'))
        assert result['success'] and result['severity']['estimated_severity'] is not None
        assert result['severity']['needs_review'] and result['severity']['heuristic_unvalidated']
        assert result['damage']['candidate_pixels_original'] == old['damage']['candidate_pixels_original']
        assert get_json(args.base_url + '/api/scans/' + result['scanId']) == result
        folder = args.output_dir / result['scanId']
        folder.mkdir(exist_ok=True)
        (folder / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
        images = {}
        for name, url in result['assets'].items():
            with urlopen(args.base_url + url, timeout=30) as response:
                png = response.read()
            assert png.startswith(b'\x89PNG')
            (folder / (name + '.png')).write_bytes(png)
            images[name] = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED)
        for name in ('body_original', 'damage_original'):
            np.testing.assert_array_equal(images[name], cv2.imread(str(old_path.parent / (name + '.png')), 0))
        if result['severity']['estimation_basis'] == 'observed_area_only':
            np.testing.assert_array_equal(images['source'], images['display'])
            assert result['transformMatrix'] is None
            assert result['severity']['skeleton_length_ratio'] is None
            assert result['severity']['width_ratio'] is None
        else:
            size = (result['displayImage']['width'], result['displayImage']['height'])
            for source, target in [('damage_original', 'damage_rectified'), ('body_original', 'surface_rectified')]:
                expected = cv2.warpPerspective(images[source], np.asarray(result['transformMatrix']),
                                               size, flags=cv2.INTER_NEAREST)
                np.testing.assert_array_equal(images[target], expected)
        assert images['display'].shape == images['overlay'].shape
        records.append(dict(surface=surface, scan_id=result['scanId'], previous_status=old['status'],
                            status=result['status'], level=result['severity']['estimated_severity'],
                            basis=result['severity']['estimation_basis'],
                            quality=result['severity'].get('geometry_diagnostics'),
                            reasons=result['severity']['reasons'], limitations=result['severity']['limitations'],
                            source_masks_identical=True, persisted_exactly=True))
    after = get_json(args.worker_url + '/health')
    assert after['requests_processed'] - before['requests_processed'] == len(records)
    assert after['detector_calls'] - before['detector_calls'] == len(records)
    report = dict(records=records, worker_before=before, worker_after=after, severity_accuracy_evaluated=False)
    (args.output_dir / 'verification.json').write_text(json.dumps(report, indent=2), 'utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
