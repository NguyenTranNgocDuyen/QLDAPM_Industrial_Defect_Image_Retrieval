"""Throwaway prototype for outer-body corner detection."""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

from defect_vision.demo import create_perspective_view
from defect_vision.perspective import (
    correct_perspective,
    draw_corners,
    order_corners,
)

PointArray = NDArray[np.float32]


def _to_bgr(image):
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 1:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image


def contour_to_quad(contour) -> PointArray | None:
    hull = cv2.convexHull(contour)
    peri = max(float(cv2.arcLength(hull, True)), 1.0)
    for factor in np.linspace(0.01, 0.08, 15):
        approx = cv2.approxPolyDP(hull, float(factor) * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            return approx.reshape(-1, 2).astype(np.float32)
    pts = hull.reshape(-1, 2).astype(np.float32)
    if len(pts) >= 4:
        s = pts.sum(axis=1)
        d = pts[:, 0] - pts[:, 1]
        quad = np.array(
            [pts[np.argmin(s)], pts[np.argmax(d)], pts[np.argmax(s)], pts[np.argmin(d)]],
            dtype=np.float32,
        )
        if np.unique(np.round(quad, 1), axis=0).shape[0] == 4:
            try:
                return order_corners(quad)
            except Exception:
                pass
    box = cv2.boxPoints(cv2.minAreaRect(hull)).astype(np.float32)
    try:
        return order_corners(box)
    except Exception:
        return None


def line_from_points(p, q):
    a = float(p[1] - q[1])
    b = float(q[0] - p[0])
    c = float(p[0] * q[1] - q[0] * p[1])
    return np.array([a, b, c], dtype=np.float64)


def intersect_lines(l1, l2):
    a1, b1, c1 = l1
    a2, b2, c2 = l2
    det = a1 * b2 - a2 * b1
    if abs(det) < 1e-6:
        raise ValueError("parallel")
    x = (b1 * c2 - b2 * c1) / det
    y = (c1 * a2 - c2 * a1) / det
    return np.array([x, y], dtype=np.float32)


def detect_screen(image) -> PointArray | None:
    bgr = _to_bgr(image)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    scored: list[tuple[float, PointArray]] = []

    masks = []
    for thr in (45, 60, 75, 90, 110):
        dark = cv2.threshold(blurred, thr, 255, cv2.THRESH_BINARY_INV)[1]
        masks.append(dark)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    masks.append(cv2.inRange(hsv, (0, 0, 0), (180, 80, 90)))
    adaptive = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 41, 8
    )
    masks.append(adaptive)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    for mask in masks:
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8), iterations=1)
        contours, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area = cv2.contourArea(contour)
            ratio = area / float(h * w)
            if ratio < 0.08 or ratio > 0.62:
                continue
            quad = contour_to_quad(contour)
            if quad is None:
                continue
            try:
                ordered = order_corners(quad)
            except Exception:
                continue
            xs, ys = ordered[:, 0], ordered[:, 1]
            border_hits = int(
                np.sum(xs < 3)
                + np.sum(ys < 3)
                + np.sum(xs > w - 4)
                + np.sum(ys > h - 4)
            )
            if border_hits >= 2:
                continue
            ww = max(
                np.linalg.norm(ordered[1] - ordered[0]),
                np.linalg.norm(ordered[2] - ordered[3]),
            )
            hh = max(
                np.linalg.norm(ordered[3] - ordered[0]),
                np.linalg.norm(ordered[2] - ordered[1]),
            )
            aspect = max(ww, hh) / max(min(ww, hh), 1.0)
            if aspect < 1.15 or aspect > 3.4:
                continue
            rect = cv2.minAreaRect(ordered)
            rarea = max(rect[1][0] * rect[1][1], 1.0)
            rectangularity = abs(cv2.contourArea(ordered)) / rarea
            if rectangularity < 0.78:
                continue
            poly_mask = np.zeros((h, w), np.uint8)
            cv2.fillConvexPoly(poly_mask, np.round(ordered).astype(np.int32), 255)
            mean_in = cv2.mean(gray, mask=poly_mask)[0]
            if mean_in > 110:
                continue
            score = (
                2.0 * rectangularity
                + 1.0 * (1.15 <= aspect <= 2.6)
                + 1.2 * (0.12 <= ratio <= 0.5)
                + 1.5 * (1.0 - mean_in / 255.0)
                - 0.6 * border_hits
            )
            scored.append((score, ordered))

    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return complete_screen(bgr, scored[0][1])


def complete_screen(bgr, seed: PointArray) -> PointArray | None:
    """Push each seed edge outward until the dark glass meets the bright bezel."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    ordered = order_corners(seed)
    center = ordered.mean(axis=0)
    poly_mask = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(poly_mask, np.round(ordered).astype(np.int32), 255)
    screen_mean = float(cv2.mean(gray, mask=poly_mask)[0])
    bezel_gray = min(175.0, max(125.0, screen_mean + 50.0))

    edge_pairs = ((0, 1), (1, 2), (2, 3), (3, 0))
    short = min(float(np.linalg.norm(ordered[j] - ordered[i])) for i, j in edge_pairs)
    max_walk = max(24.0, 0.55 * short)

    outer_lines = []
    for i, j in edge_pairs:
        p, q = ordered[i], ordered[j]
        tangent = q - p
        nlen = float(np.linalg.norm(tangent))
        normal = np.array([tangent[1], -tangent[0]], np.float32) / nlen
        mid = (p + q) / 2
        if np.dot(normal, mid - center) < 0:
            normal = -normal

        hits = []
        for t in np.linspace(0.12, 0.88, 20):
            origin = p + tangent * t
            hit_dist = 0.0
            for dist in np.linspace(0.0, max_walk, int(max_walk) + 1):
                pt = origin + normal * dist
                x, y = int(round(pt[0])), int(round(pt[1]))
                if x < 0 or y < 0 or x >= w or y >= h:
                    break
                if gray[y, x] >= bezel_gray:
                    hit_dist = dist
                    break
                hit_dist = dist
            hits.append(hit_dist)
        p30, p70 = float(np.percentile(hits, 30)), float(np.percentile(hits, 70))
        # Truncated glass: many rays travel far before the bezel.
        offset = p70 if p70 > p30 + 18 else p30
        outer_pt = mid + normal * offset
        outer_lines.append(line_from_points(outer_pt, outer_pt + tangent))

    top, right, bottom, left = outer_lines
    grown = np.stack(
        [
            intersect_lines(left, top),
            intersect_lines(top, right),
            intersect_lines(right, bottom),
            intersect_lines(bottom, left),
        ]
    ).astype(np.float32)
    grown[:, 0] = np.clip(grown[:, 0], 0, w - 1)
    grown[:, 1] = np.clip(grown[:, 1], 0, h - 1)
    try:
        grown = order_corners(grown)
    except Exception:
        return ordered
    if abs(cv2.contourArea(grown)) < abs(cv2.contourArea(ordered)) * 0.9:
        return ordered
    return grown


def expand_to_body(image, screen: PointArray):
    bgr = _to_bgr(image)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    h, w = gray.shape[:2]
    ordered = order_corners(screen)
    center = ordered.mean(axis=0)

    edge_pairs = ((0, 1), (1, 2), (2, 3), (3, 0))
    edge_lens = [float(np.linalg.norm(ordered[j] - ordered[i])) for i, j in edge_pairs]
    short = float(min(edge_lens))
    min_bezel = max(6.0, 0.03 * short)

    screen_mask = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(screen_mask, np.round(ordered).astype(np.int32), 255)

    bezel_samples = []
    for i, j in edge_pairs:
        p, q = ordered[i], ordered[j]
        tangent = q - p
        nlen = np.linalg.norm(tangent)
        if nlen < 1:
            continue
        normal = np.array([tangent[1], -tangent[0]], np.float32) / nlen
        mid = (p + q) / 2
        if np.dot(normal, mid - center) < 0:
            normal = -normal
        for t in np.linspace(0.2, 0.8, 9):
            origin = p + tangent * t
            for dist in (8.0, 14.0, 20.0):
                pt = origin + normal * dist
                x, y = int(round(pt[0])), int(round(pt[1]))
                if 0 <= x < w and 0 <= y < h and screen_mask[y, x] == 0:
                    bezel_samples.append(lab[y, x])

    if len(bezel_samples) < 8:
        bezel_mean = np.array([200, 128, 128], np.float32)
        bezel_tol = 42.0
    else:
        bezel_mean = np.median(np.stack(bezel_samples), axis=0)

    def is_device(x: int, y: int) -> bool:
        if screen_mask[y, x] or gray[y, x] < 75:
            return True
        delta = lab[y, x] - bezel_mean
        d_l = abs(float(delta[0]))
        d_ab = float(np.hypot(delta[1], delta[2]))
        return d_l < 24.0 and d_ab < 28.0

    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.GaussianBlur(cv2.magnitude(gx, gy), (5, 5), 0)

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    canny = cv2.Canny(blurred, 40, 140)
    inner = cv2.erode(screen_mask, np.ones((21, 21), np.uint8), iterations=1)
    canny[inner > 0] = 0
    hough = cv2.HoughLinesP(
        canny, 1, np.pi / 180, threshold=40, minLineLength=int(0.18 * short), maxLineGap=18
    )

    debug = bgr.copy()
    outer_lines = []
    for i, j in edge_pairs:
        p, q = ordered[i], ordered[j]
        tangent = q - p
        nlen = float(np.linalg.norm(tangent))
        normal = np.array([tangent[1], -tangent[0]], np.float32) / nlen
        mid = (p + q) / 2
        if np.dot(normal, mid - center) < 0:
            normal = -normal
        edge_angle = float(np.arctan2(tangent[1], tangent[0]))
        # Long sides of a phone have thin bezels; short sides include camera / home button.
        max_bezel = max(28.0, (0.42 if nlen < 1.2 * short else 0.16) * short)

        boundary = []
        for t in np.linspace(0.08, 0.92, 28):
            origin = p + tangent * t
            last_device = None
            run = 0
            for dist in np.linspace(min_bezel, max_bezel, int(max_bezel - min_bezel) + 1):
                pt = origin + normal * dist
                x, y = int(round(pt[0])), int(round(pt[1]))
                if x < 0 or y < 0 or x >= w or y >= h:
                    break
                if is_device(x, y):
                    last_device = pt
                    run += 1
                elif run >= 4:
                    break
            if last_device is not None:
                boundary.append(last_device)
                cv2.circle(debug, tuple(np.round(last_device).astype(int)), 2, (0, 255, 255), -1)

        # Hough support: lines parallel to this edge, outward
        hough_offsets = []
        if hough is not None:
            for seg_pts in hough.reshape(-1, 4):
                x1, y1, x2, y2 = (int(v) for v in seg_pts)
                seg = np.array([x2 - x1, y2 - y1], np.float32)
                if np.linalg.norm(seg) < 20:
                    continue
                ang = float(np.arctan2(seg[1], seg[0]))
                diff = abs((ang - edge_angle + np.pi / 2) % np.pi - np.pi / 2)
                if diff > np.deg2rad(18):
                    continue
                seg_mid = np.array([(x1 + x2) / 2, (y1 + y2) / 2], np.float32)
                offset = float(np.dot(seg_mid - mid, normal))
                if min_bezel * 0.5 <= offset <= max_bezel:
                    hough_offsets.append(offset)

        chosen_offset = None
        if boundary:
            offsets = [float(np.dot(pt - mid, normal)) for pt in boundary]
            med = float(np.median(offsets))
            inliers = [o for o in offsets if abs(o - med) < 0.18 * short]
            if inliers:
                chosen_offset = float(np.median(inliers))

        if hough_offsets:
            # prefer farthest consistent hough line (outer body) near color boundary
            h_med = float(np.median(hough_offsets))
            h_far = float(np.percentile(hough_offsets, 75))
            if chosen_offset is None:
                chosen_offset = h_far
            else:
                # if hough agrees it's farther (outer gold edge), take it
                if h_far > chosen_offset * 0.85:
                    chosen_offset = max(chosen_offset, h_far * 0.65 + chosen_offset * 0.35)
                    # actually take the larger of color/hough if close
                    if abs(h_far - chosen_offset) < 0.22 * short:
                        chosen_offset = max(chosen_offset, h_far)

        if chosen_offset is None:
            chosen_offset = 0.12 * short

        outer_pt = mid + normal * chosen_offset
        outer_lines.append(line_from_points(outer_pt, outer_pt + tangent))
        cv2.circle(debug, tuple(np.round(outer_pt).astype(int)), 7, (0, 0, 255), -1)

    top, right, bottom, left = outer_lines
    body = np.stack(
        [
            intersect_lines(left, top),
            intersect_lines(top, right),
            intersect_lines(right, bottom),
            intersect_lines(bottom, left),
        ]
    ).astype(np.float32)
    body[:, 0] = np.clip(body[:, 0], 0, w - 1)
    body[:, 1] = np.clip(body[:, 1], 0, h - 1)
    return order_corners(body), debug


def main():
    cases = {
        "394k": cv2.imread("data/394k.jpeg"),
        "329k": cv2.imread("data/329k.jpeg"),
        "demo": create_perspective_view()[0],
    }
    for name, img in cases.items():
        print("====", name, img.shape)
        screen = detect_screen(img)
        print("screen", None if screen is None else np.round(screen, 1).tolist())
        if screen is None:
            continue
        cv2.imwrite(f"outputs/body-{name}-screen.png", draw_corners(img, screen))
        body, debug = expand_to_body(img, screen)
        print("body", np.round(body, 1).tolist())
        cv2.imwrite(f"outputs/body-{name}-debug.png", debug)
        cv2.imwrite(f"outputs/body-{name}-quad.png", draw_corners(img, body))
        cv2.imwrite(f"outputs/body-{name}-warp.png", correct_perspective(img, body).image)


if __name__ == "__main__":
    main()
