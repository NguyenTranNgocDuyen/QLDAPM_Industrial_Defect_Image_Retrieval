"""Run real checkpoints and HTTP uploads; write reproducible integration evidence.

From image-processing: python scripts/verify_damage_integration.py
No training or severity accuracy evaluation. Existing sample files only.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hashlib
from http.server import ThreadingHTTPServer
import io
import json
import threading
from time import perf_counter
from unittest.mock import patch
from urllib.request import Request, urlopen

import cv2
import numpy as np
from PIL import Image
import torch
import torchvision

from defect_vision.damage_api import make_handler
from defect_vision.damage_service import DamageWorker, ROOT, decode_upright
from phone_damage_v3_kit.phone_damage_v3 import ROIDamageEngine


def main():
    started = perf_counter()
    output = ROOT / 'outputs' / 'damage-verification'
    output.mkdir(exist_ok=True, parents=True)
    with patch('phone_damage_v3_kit.phone_damage_v3.ROIDamageEngine', wraps=ROIDamageEngine) as constructor:
        worker = DamageWorker(device='cpu', output_dir=output)
        engine_id, detector_id = id(worker.engine), id(worker.segmenter._model)
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(worker))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        results = []
        sources = sorted((ROOT / 'data').glob('*.jpeg'))
        blank = io.BytesIO(); Image.new('RGB', (640, 480), 'white').save(blank, format='PNG')
        try:
            for name, data in [(p.name, p.read_bytes()) for p in sources] + [('blank_white', blank.getvalue())]:
                request = Request(base + '/analyze?surface=front', data=data,
                                  headers={'Content-Type': 'application/octet-stream'})
                with urlopen(request, timeout=300) as response:
                    result = json.load(response)
                assert result['success'], result
                if name in ('123k.jpeg', '394k.jpeg'):
                    assert result['severity']['estimated_severity'] is not None
                    assert result['severity']['estimation_basis'] == 'image_geometry'
                    assert 'aspect_approximated_from_image' in result['severity']['limitations']
                elif name == '329k.jpeg':
                    assert result['severity']['estimation_basis'] == 'observed_area_only'
                    assert result['severity']['estimated_severity'] is not None
                    assert result['severity']['skeleton_length_ratio'] is None
                else:
                    assert result['severity']['estimated_severity'] is None
                assert worker.engine.phone is None
                assert id(worker.engine) == engine_id and id(worker.segmenter._model) == detector_id
                record = dict(image=name, scan_id=result['scanId'], damage=result['damage'],
                              severity=result['severity'], processing=result['processing'])
                if name == sources[0].name and result['damage']['candidate_pixels_original'] is not None:
                    folder = output / result['scanId']
                    body = cv2.imread(str(folder / 'body_original.png'), 0)
                    integrated = cv2.imread(str(folder / 'damage_original.png'), 0) != 0
                    # Independent package loader, same upright RGB and detector mask.
                    reference = ROIDamageEngine(worker.weights, device='cpu', load_phone_detector=False)
                    expected, pixels = reference.predict_with_body(decode_upright(data), body)
                    assert np.array_equal(expected, integrated)
                    assert pixels == result['damage']['candidate_pixels_original']
                    record.update(exact_mask_parity=True, mask_array_sha256=hashlib.sha256(expected.tobytes()).hexdigest())
                    del reference
                with urlopen(base + result['assets']['display']) as response:
                    assert response.read().startswith(b'\x89PNG')
                results.append(record)
                print(json.dumps(record, ensure_ascii=True), flush=True)
            assert constructor.call_count == 1
            assert worker.detector_calls == len(results)
            assert results[-1]['damage']['status'] == 'phone_not_found'
            report = dict(torch=torch.__version__, torchvision=torchvision.__version__, device='cpu',
                          engine_initializations_per_worker=constructor.call_count,
                          detector_calls=worker.detector_calls, requests=worker.requests_processed,
                          same_engine_and_detector_instances=True, results=results,
                          elapsed_seconds=perf_counter()-started, severity_accuracy_evaluated=False)
            (output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
        finally:
            server.shutdown(); server.server_close(); thread.join()
    print(f'Verification report: {output / "verification.json"}', flush=True)


if __name__ == '__main__':
    main()
