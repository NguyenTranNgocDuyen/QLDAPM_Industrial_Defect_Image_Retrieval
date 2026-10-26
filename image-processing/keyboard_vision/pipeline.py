from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
import cv2
import numpy as np
from .config import CONFIG

@dataclass
class KeyCandidate:
    x: int; y: int; w: int; h: int; angle: float; confidence: float; row: int | None = None; column: int | None = None
    @property
    def center(self): return (self.x + self.w / 2, self.y + self.h / 2)

class KeyboardLocalizer(Protocol):
    def localize(self, image: np.ndarray) -> tuple[np.ndarray | None, float]: ...

class KeyDetector(Protocol):
    def detect(self, image: np.ndarray) -> list[KeyCandidate]: ...

class ContourKeyboardLocalizer:
    """Conservative baseline; can be replaced by a segmentation/YOLO implementation."""
    def localize(self, image):
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 60, 160)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for contour in contours:
            x, y, cw, ch = cv2.boundingRect(contour)
            ratio = (cw * ch) / float(w * h)
            if ratio > .18 and cw / max(ch, 1) > 1.3: candidates.append((ratio, (x, y, cw, ch)))
        if not candidates: return None, 0.0, (0, 0)
        ratio, (x, y, cw, ch) = max(candidates)
        return image[y:y+ch, x:x+cw].copy(), min(.9, .35 + ratio), (x, y)

class ContourKeyDetector:
    def detect(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        binary = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 4)
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        h, w = gray.shape
        found = []
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c); area = cw * ch
            if area < CONFIG['keys']['min_area'] or area > h*w*CONFIG['keys']['max_area_fraction']: continue
            ar = cw / max(ch, 1)
            if not .45 <= ar <= 4.5 or cw < 12 or ch < 12: continue
            rect = cv2.minAreaRect(c); angle = rect[-1]
            if rect[1][0] < rect[1][1]: angle += 90
            found.append(KeyCandidate(x, y, cw, ch, angle, .6))
        # nested contours are common; retain non-overlapping larger candidates
        found.sort(key=lambda k: k.w*k.h, reverse=True); kept=[]
        for key in found:
            if not any(_iou(key, old) > .65 for old in kept): kept.append(key)
        return kept

def _iou(a, b):
    x1=max(a.x,b.x); y1=max(a.y,b.y); x2=min(a.x+a.w,b.x+b.w); y2=min(a.y+a.h,b.y+b.h)
    inter=max(0,x2-x1)*max(0,y2-y1); return inter / max(1, a.w*a.h+b.w*b.h-inter)

def cluster_rows(keys):
    if not keys: return []
    median_h = float(np.median([k.h for k in keys])); tolerance=max(8, median_h*CONFIG['keys']['row_tolerance_factor'])
    rows=[]
    for key in sorted(keys, key=lambda k:k.center[1]):
        target=next((row for row in rows if abs(np.median([v.center[1] for v in row])-key.center[1])<=tolerance), None)
        if target is None: rows.append([key])
        else: target.append(key)
    for ri,row in enumerate(rows):
        row.sort(key=lambda k:k.center[0])
        for ci,key in enumerate(row): key.row=ri; key.column=ci
    return rows

def geometry_defects(rows):
    defects=[]
    for row in rows:
        if len(row)<3: continue
        centers=np.array([k.center[0] for k in row]); gaps=np.diff(centers); median_gap=float(np.median(gaps))
        angles=np.array([k.angle for k in row]); median_angle=float(np.median(angles))
        for index,key in enumerate(row):
            if abs(key.angle-median_angle)>CONFIG['keys']['tilt_degrees']:
                defects.append(_defect('tilted_key', key, 'Góc keycap lệch đáng kể so với hàng phím.'))
            expected=row[0].center[0]+index*median_gap
            if abs(key.center[0]-expected)>median_gap*CONFIG['keys']['shift_factor']:
                defects.append(_defect('shifted_key', key, 'Tâm keycap lệch khỏi lưới hàng phím.'))
        for index,gap in enumerate(gaps):
            if gap > median_gap*CONFIG['keys']['missing_gap_factor']:
                left=row[index]; x=int(left.center[0]+median_gap*.25); y=left.y
                pseudo=KeyCandidate(x,y,int(median_gap*.5),left.h,0,.65,left.row,index+1)
                defects.append(_defect('missing_key', pseudo, 'Khoảng trống bất thường trong hàng phím.'))
    return defects

def _defect(kind,key,reason):
    return {'id': f'{kind}-{key.row}-{key.column}', 'type':kind, 'severity':'moderate' if kind=='missing_key' else 'minor',
      'confidence':round(key.confidence,2), 'keyLabel':None, 'row':key.row, 'column':key.column,
      'bbox':{'x1':key.x,'y1':key.y,'x2':key.x+key.w,'y2':key.y+key.h,'coordinateSpace':'source'}, 'reason':reason}

def quality(image):
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY); blur=float(cv2.Laplacian(gray,cv2.CV_64F).var()); brightness=float(gray.mean())
    clip=float(((gray<5)|(gray>250)).mean()); reasons=[]
    if blur < CONFIG['quality']['min_blur']: reasons.append('Ảnh bị mờ, không đủ bằng chứng để kết luận.')
    if not CONFIG['quality']['min_brightness'] <= brightness <= CONFIG['quality']['max_brightness'] or clip>CONFIG['quality']['max_clipping_ratio']: reasons.append('Ảnh quá tối/sáng hoặc bị cháy sáng.')
    return {'status':'acceptable' if not reasons else 'needs_review','blurScore':round(blur,2),'brightnessScore':round(brightness,2),'perspectiveScore':0.0,'reasons':reasons}
