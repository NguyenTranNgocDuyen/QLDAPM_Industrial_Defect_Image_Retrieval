"""Unvalidated geometry of candidate masks on ONE observed planar surface.

No learned grading, physical defect types, depth, millimetres or device health.
Skeleton: padded Zhang-Suen thinning; graph counts right/down and diagonals once,
omitting a diagonal when either orthogonal bridge exists (staircase shortcut).
Width: padded Euclidean distance transform, 90th percentile per component.
The input masks are never dilated, closed, filtered or modified.
"""
from __future__ import annotations

import json
from pathlib import Path
import math

import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt

METRICS = ("area_ratio", "skeleton_length_ratio", "width_ratio")
LEVELS = (None, "minor", "moderate", "severe")


def load_config(path=None):
    # Support CLI/tests launched either from ``image-processing`` or from the
    # repository root.  Existing absolute/custom paths retain priority.
    requested = Path(path) if path else Path(__file__).with_name("severity.v6.json")
    if path and not requested.is_absolute() and not requested.is_file():
        package_relative = Path(__file__).parent / requested.name
        if package_relative.is_file():
            requested = package_relative
    config = json.loads(requested.read_text("utf-8"))
    if not isinstance(config.get("version"), str) or not config["version"]:
        raise ValueError("Severity configuration needs a version.")
    if config.get("heuristic_unvalidated") is not True:
        raise ValueError("Geometry grading must remain marked unvalidated.")
    for name in METRICS:
        moderate, severe = (config[name][key] for key in ("moderate", "severe"))
        if not all(isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x)
                   for x in (moderate, severe)) or not 0 <= moderate < severe:
            raise ValueError(f"Invalid severity thresholds: {name}")
    quality = config.get('image_geometry')
    if quality is not None:
        if not isinstance(quality.get('enabled'), bool):
            raise ValueError('Image geometry enabled must be boolean.')
        for key in ('min_body_inside_quad_ratio', 'min_quad_fill_ratio', 'min_convex_fill_ratio'):
            value = quality[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= 1:
                raise ValueError(f'Invalid geometry threshold: {key}')
        for key, minimum in (('max_opposite_edge_ratio', 1), ('min_short_side_px', 2)):
            value = quality[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
                raise ValueError(f'Invalid geometry threshold: {key}')
        if not isinstance(quality.get('allow_selected_target_estimate', False), bool):
            raise ValueError('Selected target estimate enabled must be boolean.')
    fallback = config.get('observed_area_fallback')
    if fallback is not None:
        if (not isinstance(fallback.get('enabled'), bool)
                or isinstance(fallback.get('min_surface_pixels'), bool)
                or not isinstance(fallback.get('min_surface_pixels'), int)
                or fallback['min_surface_pixels'] < 1):
            raise ValueError('Invalid observed-area fallback configuration.')
    classification = config.get('classification')
    if classification is not None:
        if (classification.get('rule') not in ('area_and_width', 'area_led_width_confirmation')
                or not isinstance(classification.get('partial_severe_requires_width'), bool)):
            raise ValueError('Invalid severity classification rule.')
        if (classification['rule'] == 'area_led_width_confirmation'
                and (classification.get('area_moderate_comparison') != '>'
                     or classification.get('area_severe_comparison') != '>')):
            raise ValueError('Area-led grading requires inclusive minor/moderate area limits.')
    return config


def _metric_level(value, key, config):
    # Area-led policy: exactly 2% remains minor, exactly 5% remains moderate.
    exclusive = (key == 'area_ratio' and config.get('classification', {}).get('rule')
                 == 'area_led_width_confirmation')
    severe = value > config[key]['severe'] if exclusive else value >= config[key]['severe']
    if severe:
        return 3
    moderate = value > config[key]['moderate'] if exclusive else value >= config[key]['moderate']
    return 2 if moderate else 1


def classify_metrics(measurements, config):
    """Classify ratios only: raw pixel counts and the detection alarm are absent.

Keep per-metric bands for audit, separate from the combined final decision.
Legacy configurations retain their original maximum-of-three policy.
"""
    levels = {}
    for key in METRICS:
        value = measurements[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f'Invalid severity measurement: {key}')
        levels[key] = _metric_level(value, key, config)
    policy = config.get('classification')
    if policy is None:
        highest = max(levels.values())
        reasons = [f'{key}:{LEVELS[value]}' for key, value in levels.items() if value == highest]
    else:
        combined_severe = levels['area_ratio'] == 3 and levels['width_ratio'] == 3
        scoring_metrics = ('area_ratio', 'width_ratio')
        if combined_severe:
            highest = 3
            reasons = ['area_width_confirmed_severe']
        elif policy['rule'] == 'area_led_width_confirmation':
            highest = min(2, levels['area_ratio'])
            reasons = (['area_within_minor_limit'] if highest == 1 else ['area_ratio:moderate'])
            if levels['area_ratio'] == 3:
                reasons.append('area_requires_width_confirmation')
        else:
            highest = min(2, max(levels[key] for key in scoring_metrics))
            reasons = [f'{key}:{LEVELS[value]}' for key, value in levels.items()
                       if key in scoring_metrics and value == highest]
            if levels['width_ratio'] == 3:
                reasons.append('width_requires_area_confirmation')
            if levels['area_ratio'] == 3:
                reasons.append('area_requires_width_confirmation')
    return dict(estimated_severity=LEVELS[highest],
                metric_levels={key: LEVELS[value] for key, value in levels.items()}, reasons=reasons)


def candidate_locations(damage, *, coordinate_space='rectified_surface'):
    """All occupied cells of a 3x3 image grid, never physical defect labels."""
    total = int(damage.sum())
    if not total:
        return []
    rows, columns = ('top', 'middle', 'bottom'), ('left', 'center', 'right')
    h, w = damage.shape
    locations = []
    for y in range(3):
        for x in range(3):
            pixels = int(damage[y*h//3:(y+1)*h//3, x*w//3:(x+1)*w//3].sum())
            if pixels:
                count_key = 'candidate_pixels_source' if coordinate_space == 'source' else 'candidate_pixels_rectified'
                locations.append(dict(region=f'{rows[y]}_{columns[x]}',
                                      **{count_key: pixels}, candidate_share=pixels/total))
    return sorted(locations, key=lambda item: item['candidate_share'], reverse=True)


def binary_mask(mask, shape=None):
    mask = np.asarray(mask)
    if mask.ndim != 2 or not mask.size or (shape is not None and mask.shape != shape):
        raise ValueError("Mask must be a nonempty HxW array in the same coordinates.")
    if mask.dtype != np.bool_ and (not np.issubdtype(mask.dtype, np.integer)
                                  or not np.isin(mask, (0, 1, 255)).all()):
        raise ValueError("Expected binary bool/integer mask, not probabilities.")
    return mask != 0


def skeletonize(mask):
    """Zhang-Suen thinning with an explicit zero border, including full masks."""
    image = np.pad(mask.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            p = [image[:-2, 1:-1], image[:-2, 2:], image[1:-1, 2:],
                 image[2:, 2:], image[2:, 1:-1], image[2:, :-2],
                 image[1:-1, :-2], image[:-2, :-2]]
            count = sum(p)
            transitions = sum(((p[i] == 0) & (p[(i + 1) % 8] == 1)).astype(np.uint8)
                              for i in range(8))
            if step == 0:
                triplets = (p[0] * p[2] * p[4] == 0) & (p[2] * p[4] * p[6] == 0)
            else:
                triplets = (p[0] * p[2] * p[6] == 0) & (p[0] * p[4] * p[6] == 0)
            remove = ((image[1:-1, 1:-1] != 0) & (count >= 2) & (count <= 6)
                      & (transitions == 1) & triplets)
            if remove.any():
                image[1:-1, 1:-1][remove] = 0
                changed = True
        if not changed:
            return image[1:-1, 1:-1].astype(bool)


def skeleton_length(skeleton):
    s = skeleton
    orthogonal = np.count_nonzero(s[:, :-1] & s[:, 1:]) + np.count_nonzero(s[:-1] & s[1:])
    diagonal_a = s[:-1, :-1] & s[1:, 1:] & ~s[:-1, 1:] & ~s[1:, :-1]
    diagonal_b = s[:-1, 1:] & s[1:, :-1] & ~s[:-1, :-1] & ~s[1:, 1:]
    return float(orthogonal + math.sqrt(2) * (np.count_nonzero(diagonal_a) + np.count_nonzero(diagonal_b)))


def unavailable(reason, status="insufficient_evidence", config=None):
    config = config or load_config()
    return dict(status=status, estimated_severity=None, needs_review=True,
                reasons=[reason], area_ratio=None, skeleton_length_ratio=None, width_ratio=None,
                skeleton_length_max_px=None, skeleton_length_total_px=None, width_p90_max_px=None,
                component_count=None, heuristic_unvalidated=True, config_version=config["version"],
                measurement_coordinate_space=None, scope="observed_surface_only",
                estimation_basis=None, limitations=[], locations=None,
                classification_rule=config.get('classification', {}).get('rule', 'max_metric'))


def evaluate_geometry(damage, visible_surface, *, full_surface_size=None,
                      geometry_confirmed=False, observation_complete=False, config=None,
                      allow_image_estimate=False):
    """Image estimates require the caller's usable-geometry checks first.

    They retain unverified aspect/visibility as limitations and needs_review;
    this does not assert that physical calibration or full visibility is known.
    """
    config = config or load_config()
    damage = binary_mask(damage)
    if visible_surface is None:
        return unavailable("missing_visible_surface", config=config)
    surface = binary_mask(visible_surface, damage.shape)
    if not surface.any():
        return unavailable("empty_visible_surface", config=config)
    result = unavailable("geometry_not_confirmed", "needs_review", config)
    result["measurement_coordinate_space"] = "rectified_surface"
    d = damage & surface
    result['locations'] = candidate_locations(d)
    result["area_ratio"] = float(np.count_nonzero(d) / np.count_nonzero(surface))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(d.astype(np.uint8), 8)
    lengths, widths = [], []
    for i in range(1, n):
        x, y, w, h, _ = stats[i]
        component = labels[y:y+h, x:x+w] == i
        skel = skeletonize(component)
        lengths.append(skeleton_length(skel))
        distances = distance_transform_edt(np.pad(component, 1))[1:-1, 1:-1]
        widths.append(float(np.percentile(2 * distances[skel], 90)) if skel.any() else 0.0)
    result.update(component_count=n-1, skeleton_length_max_px=max(lengths, default=0.0),
                  skeleton_length_total_px=sum(lengths), width_p90_max_px=max(widths, default=0.0))
    if full_surface_size is not None:
        w, h = full_surface_size
        if (not all(math.isfinite(x) and x > 1 for x in (w, h))
                or (w, h) != (damage.shape[1], damage.shape[0])):
            raise ValueError("Full surface size must match the rectified coordinate frame.")
        result["skeleton_length_ratio"] = result["skeleton_length_max_px"] / math.hypot(w, h)
        result["width_ratio"] = result["width_p90_max_px"] / min(w, h)
    reasons = []
    if not geometry_confirmed or full_surface_size is None:
        reasons.append("geometry_or_target_aspect_unconfirmed")
    if not observation_complete:
        reasons.append("surface_occluded_cropped_or_unconfirmed")
    provisional = bool(allow_image_estimate and full_surface_size is not None)
    if reasons and not provisional:
        result["reasons"] = reasons
        return result
    result['estimation_basis'] = 'image_geometry' if reasons else 'known_surface_geometry'
    result['limitations'] = ([reason for condition, reason in (
        (not geometry_confirmed, 'aspect_approximated_from_image'),
        (not observation_complete, 'visibility_not_verified')) if condition] if provisional else [])
    if not d.any():
        result.update(status="no_detected_damage", needs_review=bool(reasons), reasons=["no_candidates_on_observed_surface"])
        return result
    decision = classify_metrics({key: result[key] for key in METRICS}, config)
    result.update(status="estimated", needs_review=bool(reasons), **decision)
    return result


def evaluate_observed_area(damage, visible_surface, *, reasons, config=None):
    """Provisional area-only result in SOURCE coordinates, never a whole-face grade.

No normalization by a guessed partial bounding box; L/W stay unknown. This is
an area-only estimate of the visible region. Keep the missing metrics explicit.
"""
    config = config or load_config()
    damage = binary_mask(damage)
    surface = binary_mask(visible_surface, damage.shape)
    settings = config.get('observed_area_fallback', {})
    result = unavailable('observed_geometry_incomplete', 'needs_review', config)
    result['reasons'] = list(dict.fromkeys(reasons))
    if not settings.get('enabled') or int(surface.sum()) < settings['min_surface_pixels']:
        result['reasons'].append('visible_surface_too_small_for_estimate')
        return result
    d = damage & surface
    area = float(d.sum() / surface.sum())
    result.update(area_ratio=area, measurement_coordinate_space='source',
                  estimation_basis='observed_area_only', severity_is_partial=True,
                  unassessed_metrics=['skeleton_length_ratio', 'width_ratio'],
                  limitations=['observed_area_only', 'unseen_surface_not_assessed',
                               'perspective_not_corrected', 'length_and_width_unavailable'],
                  locations=candidate_locations(d, coordinate_space='source'))
    result['locations_coordinate_space'] = 'source'
    if not d.any():
        result.update(status='no_detected_damage')
        result['reasons'].append('no_candidates_on_observed_surface')
        return result
    level = LEVELS[_metric_level(area, 'area_ratio', config)]
    raw_level = level
    if level == 'severe' and config.get('classification', {}).get('partial_severe_requires_width'):
        level = 'moderate'
        result['reasons'].append('severe_unconfirmed_without_width')
    result.update(status='estimated', estimated_severity=level,
                  metric_levels={'area_ratio': raw_level})
    if raw_level == level:
        result['reasons'].append('area_within_minor_limit' if level == 'minor' and
                                config.get('classification', {}).get('rule') == 'area_led_width_confirmation'
                                else f'area_ratio:{level}')
    result['reasons'].append('partial_area_estimate_only')
    return result
