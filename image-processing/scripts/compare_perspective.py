"""Compare legacy and guarded corner fitting on saved segmentation masks.

No model download or inference is needed. Example (from image-processing):
    python scripts/compare_perspective.py --case 329k data/329k.jpeg outputs/test_seg/mask_329k.png
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np

from defect_vision.perspective import correct_perspective
from defect_vision.phone_segmenter import extract_corners_from_mask


def compare_case(name: str, image_path: str, mask_path: str, output: Path) -> dict:
    image = cv2.imread(image_path)
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    if image is None or mask is None or image.shape[:2] != mask.shape:
        raise ValueError(f'{name}: image and mask must be readable and have matching sizes')
    if not np.any(mask):
        raise ValueError(f'{name}: mask is empty')
    report = {'image': image_path, 'mask': mask_path, 'methods': {}}
    panels = []
    source_mask = mask.copy()
    for label, adaptive, expand in [('legacy', False, False), ('refitted', True, False),
                                    ('expanded', True, True)]:
        diagnostics = {}
        corners = extract_corners_from_mask(mask, image_shape=mask.shape, adaptive_refinement=adaptive,
                                           expand_to_mask=expand, corner_diagnostics=diagnostics)
        if corners is None:
            raise ValueError(f'{name}: no corners found')
        polygon = cv2.fillConvexPoly(np.zeros_like(mask), np.round(corners).astype(np.int32), 1)
        overlap = np.count_nonzero((mask > 0) & (polygon > 0))
        polygon_area = np.count_nonzero(polygon)
        coverage = overlap / np.count_nonzero(mask)
        background = (polygon_area - overlap) / max(polygon_area, 1)
        report['methods'][label] = {
            'corners': corners.astype(float).round(3).tolist(),
            'mask_coverage_pct': round(100 * coverage, 3),
            'outside_mask_pct': round(100 * background, 3),
            'expansion': diagnostics,
        }
        overlay = image.copy()
        overlay[(mask > 0) & (polygon == 0)] = (0, 0, 255)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, (0, 255, 0), 1)
        cv2.polylines(overlay, [np.round(corners).astype(np.int32)], True, (0, 255, 255), 2)
        height = 650
        overlay = cv2.resize(overlay, (round(image.shape[1] * height / image.shape[0]), height))
        header = np.full((65, overlay.shape[1], 3), 245, np.uint8)
        cv2.putText(header, f'{name} | {label}', (10, 24), cv2.FONT_HERSHEY_SIMPLEX, .65, (30,30,30), 2)
        cv2.putText(header, f'Mask retained: {coverage:.2%}', (10, 50), cv2.FONT_HERSHEY_SIMPLEX, .55, (30,30,30), 1)
        panels.append(np.vstack((header, overlay)))
        corrected = correct_perspective(image, corners).image
        if not cv2.imwrite(str(output / f'{name}-{label}-corrected.png'), corrected):
            raise OSError('Could not save corrected image')
    if not np.array_equal(mask, source_mask):
        raise AssertionError('Corner processing changed the source segmentation mask')
    if not cv2.imwrite(str(output / f'{name}-comparison.png'), np.hstack(panels)):
        raise OSError('Could not save comparison')
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', nargs=3, action='append', required=True, metavar=('NAME', 'IMAGE', 'MASK'))
    parser.add_argument('--output-dir', type=Path, default=Path('outputs/perspective-audit'))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        'note': 'Coverage measures the saved mask retained by the crop, not model accuracy or true phone coverage.',
        'cases': [compare_case(*case, args.output_dir) for case in args.case],
    }
    (args.output_dir / 'comparison.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
