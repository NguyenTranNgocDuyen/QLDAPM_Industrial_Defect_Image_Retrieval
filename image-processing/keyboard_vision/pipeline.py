from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np

from .config import CONFIG


@dataclass
class KeyCandidate:
    x: int; y: int; w: int; h: int; angle: float; confidence: float
    row: int | None = None; column: int | None = None

    @property
    def center(self): return (self.x + self.w / 2, self.y + self.h / 2)


class KeyboardLocalizer(Protocol):
    def localize(self, image: np.ndarray) -> tuple[np.ndarray | None, float, tuple[int, int]]: ...


class KeyDetector(Protocol):
    def detect(self, image: np.ndarray) -> list[KeyCandidate]: ...


class ContourKeyboardLocalizer:
    """Conservative localizer; replaceable without changing the keyboard contract."""
    def localize(self, image):
        h, w = image.shape[:2]
        edges = cv2.Canny(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), 60, 160)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for contour in contours:
            x, y, cw, ch = cv2.boundingRect(contour)
            ratio = (cw * ch) / float(w * h)
            if ratio > .18 and cw / max(ch, 1) > 1.3: candidates.append((ratio, (x, y, cw, ch)))
        if not candidates: return None, 0.0, (0, 0)
        ratio, (x, y, cw, ch) = max(candidates)
        return image[y:y + ch, x:x + cw].copy(), min(.9, .35 + ratio), (x, y)


class ContourKeyDetector:
    def detect(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        binary = cv2.adaptiveThreshold(cv2.GaussianBlur(gray, (5, 5), 0), 255,
                                       cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 4)
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        h, w = gray.shape; found = []
        for contour in contours:
            x, y, cw, ch = cv2.boundingRect(contour); area = cw * ch
            if area < CONFIG['keys']['min_area'] or area > h * w * CONFIG['keys']['max_area_fraction']: continue
            if not .45 <= cw / max(ch, 1) <= 4.5 or cw < 12 or ch < 12: continue
            rect = cv2.minAreaRect(contour); angle = rect[-1] + (90 if rect[1][0] < rect[1][1] else 0)
            found.append(KeyCandidate(x, y, cw, ch, angle, .6))
        found.sort(key=lambda key: key.w * key.h, reverse=True); kept = []
        for key in found:
            if not any(_iou(key, old) > .65 for old in kept): kept.append(key)
        return kept


def _iou(a, b):
    x1, y1, x2, y2 = max(a.x, b.x), max(a.y, b.y), min(a.x + a.w, b.x + b.w), min(a.y + a.h, b.y + b.h)
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    return inter / max(1, a.w * a.h + b.w * b.h - inter)


def cluster_rows(keys):
    if not keys: return []
    tolerance = max(8, float(np.median([key.h for key in keys])) * CONFIG['keys']['row_tolerance_factor']); rows = []
    for key in sorted(keys, key=lambda value: value.center[1]):
        row = next((row for row in rows if abs(np.median([item.center[1] for item in row]) - key.center[1]) <= tolerance), None)
        (row if row is not None else rows.append([]) or rows[-1]).append(key)
    for row_index, row in enumerate(rows):
        row.sort(key=lambda value: value.center[0])
        for column_index, key in enumerate(row): key.row, key.column = row_index, column_index
    return rows


def geometry_defects(rows, origin=(0, 0)):
    defects = []
    for row in rows:
        if len(row) < 3: continue
        centers = np.array([key.center[0] for key in row]); gaps = np.diff(centers); median_gap = float(np.median(gaps))
        median_angle = float(np.median([key.angle for key in row]))
        for index, key in enumerate(row):
            if abs(key.angle - median_angle) > CONFIG['keys']['tilt_degrees']:
                defects.append(_defect('tilted_key', key, 'Góc keycap lệch đáng kể so với hàng phím.', origin))
            expected = row[0].center[0] + index * median_gap
            if abs(key.center[0] - expected) > median_gap * CONFIG['keys']['shift_factor']:
                defects.append(_defect('shifted_key', key, 'Tâm keycap lệch khỏi lưới hàng phím.', origin))
        for index, gap in enumerate(gaps):
            if gap > median_gap * CONFIG['keys']['missing_gap_factor']:
                left = row[index]
                pseudo = KeyCandidate(int(left.center[0] + median_gap * .25), left.y, int(median_gap * .5), left.h, 0, .65, left.row, index + 1)
                defects.append(_defect('missing_key', pseudo, 'Khoảng trống bất thường trong hàng phím.', origin))
    return defects


def draw_grid_debug(image, rows):
    """Render the accepted contour grid in ROI coordinates for human review."""
    debug = image.copy()
    for row in rows:
        for key in row:
            cv2.rectangle(debug, (key.x, key.y), (key.x + key.w, key.y + key.h), (0, 255, 0), 1)
            cv2.putText(debug, f"{key.row}:{key.column}", (key.x, max(12, key.y - 3)), cv2.FONT_HERSHEY_SIMPLEX, .35, (0, 180, 255), 1)
    return debug


def _defect(kind, key, reason, origin):
    return {'id': f'{kind}-{key.row}-{key.column}', 'type': kind, 'severity': 'moderate' if kind == 'missing_key' else 'minor',
            'confidence': round(key.confidence, 2), 'keyLabel': None, 'row': key.row, 'column': key.column,
            'bbox': {'x1': key.x + origin[0], 'y1': key.y + origin[1], 'x2': key.x + key.w + origin[0],
                     'y2': key.y + key.h + origin[1], 'coordinateSpace': 'source'}, 'reason': reason}


def quality(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY); blur = float(cv2.Laplacian(gray, cv2.CV_64F).var()); brightness = float(gray.mean())
    clip = float(((gray < 5) | (gray > 250)).mean()); reasons = []
    if blur < CONFIG['quality']['min_blur']: reasons.append('Ảnh bị mờ, không đủ bằng chứng để kết luận.')
    if not CONFIG['quality']['min_brightness'] <= brightness <= CONFIG['quality']['max_brightness'] or clip > CONFIG['quality']['max_clipping_ratio']:
        reasons.append('Ảnh quá tối/sáng hoặc bị cháy sáng.')
    return {'status': 'acceptable' if not reasons else 'needs_review', 'blurScore': round(blur, 2),
            'brightnessScore': round(brightness, 2), 'perspectiveScore': 0.0, 'reasons': reasons}
