"""Measured shape diagnostics for provisional image-based estimates.

No claim to detect every occlusion, identify a handset or recover physical aspect.
Thresholds are versioned, unvalidated guards on visible segmentation geometry.
"""
import cv2
import numpy as np
from .damage_severity import binary_mask


def assess_surface_geometry(body, corners, target_size, config):
    body = binary_mask(body)
    q = np.asarray(corners, np.float32)
    if q.shape != (4, 2) or not np.isfinite(q).all():
        raise ValueError('Invalid corners for geometry assessment.')
    polygon = np.zeros(body.shape, np.uint8)
    cv2.fillConvexPoly(polygon, np.round(q).astype(np.int32), 1)
    overlap = np.count_nonzero(body & (polygon != 0))
    inside = float(overlap / np.count_nonzero(body))
    fill = float(overlap / max(1, np.count_nonzero(polygon)))
    points = cv2.findNonZero(body.astype(np.uint8))
    hull = np.zeros_like(polygon)
    cv2.fillConvexPoly(hull, cv2.convexHull(points), 1)
    convex_fill = float(np.count_nonzero(body) / max(1, np.count_nonzero(hull)))
    edges = np.linalg.norm(np.roll(q, -1, axis=0) - q, axis=1)
    opposing = float(max(max(edges[0], edges[2])/max(1e-6, min(edges[0], edges[2])),
                         max(edges[1], edges[3])/max(1e-6, min(edges[1], edges[3]))))
    measured = dict(body_inside_quad_ratio=inside, quad_fill_ratio=fill,
                    convex_fill_ratio=convex_fill, opposite_edge_ratio=opposing,
                    short_side_px=int(min(target_size)))
    checks = {
        'body_outside_quad': inside >= config['min_body_inside_quad_ratio'],
        'surface_shape_incomplete': fill >= config['min_quad_fill_ratio'],
        'surface_concave_or_occluded': convex_fill >= config['min_convex_fill_ratio'],
        'perspective_too_oblique': opposing <= config['max_opposite_edge_ratio'],
        'surface_too_small': min(target_size) >= config['min_short_side_px'],
    }
    return dict(usable=all(checks.values()), measurements=measured,
                reasons=[reason for reason, passed in checks.items() if not passed])
