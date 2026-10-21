"""Phone-gated native detail patches with spatially aligned full-phone context."""
from collections import OrderedDict
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
import torch
from torch import nn
from torch.nn import functional as F

from .phone_body_roi import expanded_body
from .phone_data import digest
from .phone_semantic import DamageUNet, axis_starts, image_tensor


ARCHITECTURE = 'resnet18_unet_phone_context_v3'


class ContextDamageUNet(DamageUNet):
    def __init__(self, pretrained=False):
        super().__init__(pretrained=pretrained)
        self.context_fusion = nn.Conv2d(512, 512, 1, bias=False)
        nn.init.zeros_(self.context_fusion.weight)

    def encode_context(self, image):
        x = self.pool(self.stem(image))
        for layer in self.layers:
            x = layer(x)
        return x

    def forward(self, image, context=None, boxes=None, context_features=None):
        features = [image, self.stem(image)]
        x = self.pool(features[-1])
        for layer in self.layers:
            x = layer(x)
            features.append(x)
        x = features.pop()
        if context_features is None:
            if context is None:
                raise ValueError('Full-phone context is required.')
            context_features = self.encode_context(context)
        if boxes is None or boxes.shape != (image.shape[0], 4):
            raise ValueError('Expected normalized context boxes, shape B,4.')
        grid = context_grid(boxes, x.shape[-2], x.shape[-1])
        aligned = F.grid_sample(context_features, grid, align_corners=False,
                                mode='bilinear', padding_mode='border')
        x = x + self.context_fusion(aligned)
        for up, skip in zip(self.up, reversed(features)):
            x = up(x, skip)
        return self.output(x)


def context_grid(boxes, height, width):
    """Input boxes are normalized image EDGE coordinates in the context square."""
    yy, xx = torch.meshgrid((torch.arange(height, device=boxes.device)+.5)/height,
                            (torch.arange(width, device=boxes.device)+.5)/width,
                            indexing='ij')
    x = boxes[:, 0, None, None] + xx*(boxes[:, 2]-boxes[:, 0])[:, None, None]
    y = boxes[:, 1, None, None] + yy*(boxes[:, 3]-boxes[:, 1])[:, None, None]
    return torch.stack((2*x-1, 2*y-1), dim=-1)


def body_bbox(body, padding=.03):
    ys, xs = np.nonzero(body)
    if not len(xs):
        raise ValueError('Empty phone body.')
    h, w = body.shape
    margin = max(2, int(np.ceil(max(np.ptp(xs)+1, np.ptp(ys)+1)*padding)))
    return (max(0, int(xs.min())-margin), max(0, int(ys.min())-margin),
            min(w, int(xs.max())+1+margin), min(h, int(ys.max())+1+margin))


def full_context(rgb, body, size):
    x0, y0, x1, y1 = body_bbox(body)
    width, height = x1-x0, y1-y0
    scale = size/max(width, height)
    cw, ch = max(1, round(width*scale)), max(1, round(height*scale))
    left, top = (size-cw)//2, (size-ch)//2
    canvas = np.full((size, size, 3), 127, dtype=np.uint8)
    canvas[top:top+ch, left:left+cw] = cv2.resize(rgb[y0:y1, x0:x1], (cw, ch), interpolation=cv2.INTER_AREA)
    # Separate x/y scales account for integer rounding of resized dimensions.
    transform = dict(x0=x0, y0=y0, sx=cw/width, sy=ch/height,
                     left=left, top=top, size=size)
    return canvas, transform


def patch_box(x, y, size, transform):
    t = transform
    return np.array([(t['left']+(x-t['x0'])*t['sx'])/t['size'],
                     (t['top']+(y-t['y0'])*t['sy'])/t['size'],
                     (t['left']+(x+size-t['x0'])*t['sx'])/t['size'],
                     (t['top']+(y+size-t['y0'])*t['sy'])/t['size']], dtype=np.float32)


def detail_crop(rgb, target, x, y, size):
    """Native pixels; reflected RGB padding has no supervised target."""
    h, w = target.shape
    ch, cw = min(size, h-y), min(size, w-x)
    patch = rgb[y:y+ch, x:x+cw]
    patch = cv2.copyMakeBorder(patch, 0, size-ch, 0, size-cw, cv2.BORDER_REFLECT_101)
    truth = np.full((size, size), 255, dtype=np.uint8)
    truth[:ch, :cw] = target[y:y+ch, x:x+cw]
    return patch, truth


def load_manifest(path, verify=True):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    groups, pixels = {}, {}
    for r in data['records']:
        if r['split'] not in ('train', 'val'):
            raise ValueError('Training manifest must contain only train and validation.')
        for mapping, key in [(groups, 'group'), (pixels, 'pixel_sha256')]:
            if r[key] in mapping and mapping[r[key]] != r['split']:
                raise ValueError('A device or duplicate crosses splits.')
            mapping[r[key]] = r['split']
        if verify:
            for field in ['image', 'mask', 'body']:
                if digest(r[field]) != r[field+'_sha256']:
                    raise ValueError(f'{r["annotation_id"]}: {field} changed.')
            for name, expected in r.get('cache_sha256', {}).items():
                if digest(Path(r['rgb_cache']).parent/name) != expected:
                    raise ValueError(f'{r["annotation_id"]}: training cache changed: {name}')
    return data


class ROIPatchSource:
    def __init__(self, records, context_size=512, margin=.005):
        if any(r['split'] != 'train' for r in records):
            raise ValueError('Patch sampling is restricted to training records.')
        self.records, self.context_size, self.margin = records, context_size, margin
        self.positive = [r for r in records if r['kind'] == 'damaged']
        self.normal = [r for r in records if r['kind'] == 'normal']
        if not self.positive or not self.normal:
            raise ValueError('Both damaged and normal training records are needed.')
        self.cache = OrderedDict()

    def pair(self, row):
        rid = row['annotation_id']
        if rid not in self.cache:
            if 'rgb_cache' in row:
                rgb = np.load(row['rgb_cache'], mmap_mode='r')
                target = np.load(row['target_cache'], mmap_mode='r')
                positives = np.load(row['positions_cache'], mmap_mode='r')
                with Image.open(row['context_cache']) as im:
                    context = np.array(im.convert('RGB'))
                transform = row['context_transform']
                if transform['size'] != self.context_size:
                    raise ValueError('Context cache size mismatch.')
                bounds = tuple(row.get('sample_bounds', ()))
                if not bounds:
                    with Image.open(row['body']) as im:
                        bounds = body_bbox(expanded_body(np.array(im.convert('L')) > 0, self.margin))
            else:
                with Image.open(row['image']) as im:
                    rgb = np.array(im.convert('RGB'))
                with Image.open(row['mask']) as im:
                    raw = np.array(im.convert('L'))
                with Image.open(row['body']) as im:
                    body = np.array(im.convert('L')) > 0
                if raw.shape != rgb.shape[:2] or body.shape != raw.shape or not np.isin(raw, [0, 255]).all():
                    raise ValueError('Image, binary damage mask and phone body must align.')
                target = (raw > 0).astype(np.uint8)
                if row.get('_forced_normal'):
                    target[:] = 0
                roi = expanded_body(body, self.margin)
                target[~roi] = 255  # ignored, never relabeled as healthy material
                context, transform = full_context(rgb, body, self.context_size)
                positives = np.flatnonzero(target == 1)
                bounds = body_bbox(roi)
            if row['kind'] == 'damaged' and not len(positives):
                raise ValueError(f'{rid}: no supervised damage remains; review ROI.')
            self.cache[rid] = rgb, target, context, transform, positives, bounds
            while len(self.cache) > 4:
                self.cache.popitem(last=False)
        self.cache.move_to_end(rid)
        return self.cache[rid]

    def sample(self, rng, size=512, mode='positive', row=None):
        if mode not in ('positive', 'healthy_damage', 'normal'):
            raise ValueError('Unknown patch mode.')
        if row is None:
            pool = self.normal if mode == 'normal' else self.positive
            row = pool[int(rng.integers(len(pool)))]
        rgb, target, context, transform, positions, bounds = self.pair(row)
        h, w = target.shape
        if mode == 'positive':
            if not len(positions):
                raise ValueError('Positive patch requested from an empty mask.')
            cy, cx = divmod(int(rng.choice(positions)), w)
            x = int(np.clip(cx-rng.integers(size//4, 3*size//4), 0, max(0, w-size)))
            y = int(np.clip(cy-rng.integers(size//4, 3*size//4), 0, max(0, h-size)))
        else:
            best = None
            x0, y0, x1, y1 = bounds
            for _ in range(32):
                cx, cy = rng.integers(x0, x1), rng.integers(y0, y1)
                px, py = int(np.clip(cx-size//2, 0, max(0, w-size))), int(np.clip(cy-size//2, 0, max(0, h-size)))
                truth = target[py:py+size, px:px+size]
                valid = int((truth != 255).sum())
                if not valid:
                    continue
                frac = float((truth == 1).sum())/valid
                # Among equally clean proposals prefer textured/reflective material,
                # not empty padding or far-away background. Never erase real labels.
                contrast = float(rgb[py:py+size, px:px+size].std())
                key = (frac, -min(valid/(size*size), .5), -contrast)
                if best is None or key < best[0]:
                    best = key, px, py
            if best is None:
                raise ValueError('No supervised phone pixels in negative proposals.')
            _, x, y = best
        patch, truth = detail_crop(rgb, target, x, y, size)
        return dict(rgb=patch, target=truth, context=context,
                    box=patch_box(x, y, size, transform),
                    meta=dict(id=row['annotation_id'], split=row['split'], mode=mode,
                              x=x, y=y, size=size, positive_pixels=int((truth == 1).sum()),
                              valid_pixels=int((truth != 255).sum())))


def tensors(samples, device, rng=None):
    images, contexts, boxes, targets = [], [], [], []
    for sample in samples:
        rgb, context, target, box = [sample[k].copy() for k in ('rgb', 'context', 'target', 'box')]
        if rng is not None:
            if rng.random() < .5:
                rgb, context, target = np.fliplr(rgb), np.fliplr(context), np.fliplr(target)
                box[[0, 2]] = 1-box[[2, 0]]
            if rng.random() < .25:
                rgb, context, target = np.flipud(rgb), np.flipud(context), np.flipud(target)
                box[[1, 3]] = 1-box[[3, 1]]
            gain = rng.uniform(.9, 1.1)
            rgb, context = [np.uint8(np.clip(a.astype(np.float32)*gain, 0, 255)) for a in (rgb, context)]
        images.append(image_tensor(rgb))
        contexts.append(image_tensor(context))
        boxes.append(torch.from_numpy(np.ascontiguousarray(box)))
        targets.append(torch.from_numpy(np.ascontiguousarray(target)).long())
    return [torch.stack(v).to(device) for v in (images, contexts, boxes, targets)]


def roi_loss(logits, target, pos_weight=1.5):
    valid, truth = target != 255, (target == 1).float()
    if not valid.any():
        raise ValueError('No valid source pixels in batch.')
    logits = logits[:, 0].float()
    bce = F.binary_cross_entropy_with_logits(logits, truth,
        pos_weight=logits.new_tensor(pos_weight), reduction='none')
    # Each image has equal weight, including small normal images with padding.
    bce = ((bce*valid).sum((-1, -2))/valid.sum((-1, -2)).clamp_min(1)).mean()
    positives = truth.sum((-1, -2)) > 0
    if positives.any():
        probability = logits.sigmoid()
        intersection = (probability*truth*valid).sum((-1, -2))
        cardinality = ((probability+truth)*valid).sum((-1, -2))
        dice = (1-(2*intersection+1)/(cardinality+1))[positives].mean()
    else:
        dice = logits.sum()*0
    return bce+dice


@torch.inference_mode()
def roi_probability(model, rgb, body, size, overlap, context_size, device, margin=0):
    model.eval()
    roi = expanded_body(body, margin)
    context, transform = full_context(rgb, body, context_size)
    context_features = model.encode_context(image_tensor(context)[None].to(device))
    x0, y0, x1, y1 = body_bbox(roi)
    h, w = roi.shape
    probability, weights = np.zeros((h, w), np.float32), np.zeros((h, w), np.float32)
    # Raised-cosine blending suppresses tile boundary artifacts without removing
    # any ROI pixel. Endpoints remain nonzero, including image borders.
    taper = np.maximum(np.hanning(size), .1).astype(np.float32)
    window = np.outer(taper, taper)
    dummy = np.zeros((h, w), dtype=np.uint8)
    for yy in axis_starts(y1-y0, size, overlap):
        for xx in axis_starts(x1-x0, size, overlap):
            x, y = x0+xx, y0+yy
            ch, cw = min(size, h-y), min(size, w-x)
            if not roi[y:y+ch, x:x+cw].any():
                continue
            patch, _ = detail_crop(rgb, dummy, x, y, size)
            logits = model(image_tensor(patch)[None].to(device),
                           boxes=torch.from_numpy(patch_box(x, y, size, transform))[None].to(device),
                           context_features=context_features)
            if not torch.isfinite(logits).all():
                raise ValueError('Non-finite inference output.')
            pred = logits[0, 0].sigmoid().cpu().numpy()[:ch, :cw]
            win = window[:ch, :cw]
            probability[y:y+ch, x:x+cw] += pred*win
            weights[y:y+ch, x:x+cw] += win
    if (roi & (weights == 0)).any():
        raise ValueError('ROI tiling left gaps.')
    return np.where(roi, probability/np.maximum(weights, 1e-8), 0)
