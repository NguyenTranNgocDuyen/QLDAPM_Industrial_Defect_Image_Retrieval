"""Run v3 with an existing original-coordinate phone mask; no phone detector."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image, ImageOps

from phone_damage_v3 import ROIDamageEngine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--body', type=Path, required=True,
                        help='Upright original-coordinate binary phone segmentation PNG.')
    parser.add_argument('--out', type=Path, required=True, help='A new output directory.')
    parser.add_argument('--device', default='cpu')
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Use a new output directory to preserve existing results.')
    with Image.open(args.image) as image:
        rgb = np.array(ImageOps.exif_transpose(image).convert('RGB'))
    with Image.open(args.body) as image:
        body = np.array(image.convert('L'))
    engine = ROIDamageEngine(Path(__file__).resolve().parent / 'phone_damage_v3/weights',
                             device=args.device, load_phone_detector=False)
    started = time.perf_counter()
    mask, pixels = engine.predict_with_body(rgb, body)
    seconds = time.perf_counter() - started
    args.out.mkdir(parents=True)
    Image.fromarray(mask.astype(np.uint8) * 255).save(args.out / 'mask.png')
    overlay = rgb.astype(np.float32)
    overlay[mask] = overlay[mask] * .55 + np.array([255, 60, 30]) * .45
    Image.fromarray(np.uint8(overlay.clip(0, 255))).save(args.out / 'overlay.png')
    result = dict(shape=list(mask.shape), candidate_pixels=pixels,
                  found=pixels >= engine.alarm_pixels, alarm_pixels=engine.alarm_pixels,
                  threshold=engine.threshold, inference_variant=engine.variant,
                  detector_loaded=engine.phone is not None, inference_seconds=seconds,
                  severity=None, severity_status='not_implemented')
    (args.out / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
