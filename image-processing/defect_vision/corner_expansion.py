"""Bounded outward edge offsets for a crop, never a modification of source masks.

Coverage is relative to the detector mask, not the true physical phone. Keeping
parallel edges does not repair incorrect edge directions or physical calibration.
"""
from functools import lru_cache
import json
from pathlib import Path

import cv2
import numpy as np

from .perspective import order_corners


@lru_cache(maxsize=1)
def load_expansion_config():
    config = json.loads(Path(__file__).with_name('corner_expansion.v2.json').read_text('utf-8'))
    ratios = ('min_coverage', 'target_coverage', 'max_edge_offset_ratio',
              'max_corner_displacement_ratio', 'max_background_ratio')
    if (not config.get('version') or config.get('heuristic_unvalidated') is not True
            or any(not isinstance(config[k], (float, int)) or isinstance(config[k], bool)
                   or not np.isfinite(config[k]) or not 0 < config[k] < 1 for k in ratios)
            or not config['min_coverage'] <= config['target_coverage']
            or not np.isfinite(config['max_area_growth']) or not 1 < config['max_area_growth'] <= 2):
        raise ValueError('Invalid corner expansion configuration.')
    return config


def quad_mask_metrics(body, quad):
    polygon = np.zeros(body.shape, np.uint8)
    cv2.fillConvexPoly(polygon, np.round(quad).astype(np.int32), 1)
    overlap = np.count_nonzero(body & (polygon != 0))
    coverage = overlap / max(1, np.count_nonzero(body))
    background = 1 - overlap / max(1, np.count_nonzero(polygon))
    return dict(mask_coverage=float(coverage), background_ratio=float(background))


def expand_quad_to_mask(mask, corners, *, config=None):
    """Return original quad on rejection, plus JSON-safe audit measurements.

Use per-edge quantiles of signed distances. Allocate a quarter of the allowed
outside-mask pixels to each edge (union bound); adequate edges stay fixed. A
binary search chooses the smallest shared fraction of these offsets that meets
the target under the same raster measurement used by the quality guard.
"""
    config = config or load_expansion_config()
    body = np.asarray(mask) != 0
    if body.ndim != 2 or not body.any():
        raise ValueError('Expansion requires a nonempty 2D segmentation mask.')
    quad = order_corners(corners)
    height, width = body.shape
    if (quad[:, 0].min() < 0 or quad[:, 1].min() < 0
            or quad[:, 0].max() > width - 1 or quad[:, 1].max() > height - 1):
        raise ValueError('Expansion corners must be inside the source image.')
    before = quad_mask_metrics(body, quad)
    report = dict(config_version=config['version'], heuristic_unvalidated=True,
                  applied=False, reason='already_covered', before=before, after=before,
                  edge_offsets_px=[0.0] * 4)
    if before['mask_coverage'] >= config['min_coverage']:
        return quad, report

    edges = np.roll(quad, -1, axis=0) - quad
    lengths = np.linalg.norm(edges, axis=1)
    # Same scale convention as perspective._output_size (max opposite edges),
    # rather than the foreshortened single edge of an oblique quadrilateral.
    short_side = float(min(max(lengths[0], lengths[2]), max(lengths[1], lengths[3])))
    # Inward unit normals for clockwise corners in image coordinates.
    normals = np.column_stack((-edges[:, 1], edges[:, 0])) / lengths[:, None]
    constants = np.sum(normals * quad, axis=1)
    ys, xs = np.nonzero(body)
    points = np.column_stack((xs, ys))
    tail = (1 - config['target_coverage']) / 4
    offsets = np.array([max(0.0, -float(np.quantile(points @ n - c, tail)))
                        for n, c in zip(normals, constants)])
    report['proposed_edge_offsets_px'] = offsets.tolist()
    if np.any(offsets > config['max_edge_offset_ratio'] * short_side):
        report['reason'] = 'edge_offset_limit'
        return quad, report

    def candidate_at(fraction):
        shifted = constants - fraction * offsets
        result = []
        for i in range(4):
            pair = [(i - 1) % 4, i]
            result.append(np.linalg.solve(normals[pair], shifted[pair]))
        return np.asarray(result, np.float32)

    candidate = candidate_at(1.0)
    measured = quad_mask_metrics(body, candidate)
    if measured['mask_coverage'] < config['min_coverage']:
        report['reason'] = 'coverage_not_recovered'
        return quad, report
    # Quantile/raster rounding can undershoot target slightly: require the
    # configured minimum, never silently relax the downstream severity guard.
    target = min(config['target_coverage'], measured['mask_coverage'])
    low, high = 0.0, 1.0
    for _ in range(20):
        middle = (low + high) / 2
        if quad_mask_metrics(body, candidate_at(middle))['mask_coverage'] >= target:
            high = middle
        else:
            low = middle
    candidate = candidate_at(high)
    measured = quad_mask_metrics(body, candidate)
    growth = abs(cv2.contourArea(candidate)) / max(1.0, abs(cv2.contourArea(quad)))
    movement = float(np.linalg.norm(candidate - quad, axis=1).max()) / short_side
    report.update(candidate_metrics=measured, area_growth=float(growth),
                  max_corner_displacement_ratio=movement)
    # Do not clip individual corner coordinates: that would rotate fitted edges
    # and falsely suggest recovery of a surface beyond the captured image.
    if (candidate[:, 0].min() < 0 or candidate[:, 1].min() < 0
            or candidate[:, 0].max() > width - 1 or candidate[:, 1].max() > height - 1):
        reason = 'candidate_outside_image'
    elif movement > config['max_corner_displacement_ratio']:
        reason = 'corner_displacement_limit'
    elif growth > config['max_area_growth']:
        reason = 'area_growth_limit'
    elif measured['background_ratio'] > config['max_background_ratio']:
        reason = 'background_limit'
    elif measured['mask_coverage'] < config['min_coverage']:
        reason = 'coverage_not_recovered'
    else:
        report.update(applied=True, reason='expanded_clipped_edges', after=measured,
                      edge_offsets_px=(high * offsets).tolist())
        return candidate, report
    report['reason'] = reason
    return quad, report
