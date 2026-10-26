"""Binary phone-damage masks, native-resolution crops and a ResNet18 U-Net."""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image
import torch
from torch import nn
from torch.nn import functional as F
from torchvision.models import ResNet18_Weights, resnet18

from .phone_data import ROOT, digest, load_config


class ConvBlock(nn.Sequential):
    def __init__(self, incoming, outgoing):
        super().__init__(
            nn.Conv2d(incoming, outgoing, 3, padding=1, bias=False),
            nn.GroupNorm(8, outgoing), nn.ReLU(inplace=True),
            nn.Conv2d(outgoing, outgoing, 3, padding=1, bias=False),
            nn.GroupNorm(8, outgoing), nn.ReLU(inplace=True))


class UpBlock(nn.Module):
    def __init__(self, incoming, skip, outgoing):
        super().__init__()
        self.conv = ConvBlock(incoming + skip, outgoing)

    def forward(self, x, skip):
        x = F.interpolate(x, size=skip.shape[-2:], mode='bilinear', align_corners=False)
        return self.conv(torch.cat((x, skip), dim=1))


class DamageUNet(nn.Module):
    def __init__(self, pretrained=True):
        super().__init__()
        # Downloaded public weights stay inside the workspace.
        torch.hub.set_dir(str(ROOT / 'artifacts/torch'))
        encoder = resnet18(weights=ResNet18_Weights.DEFAULT if pretrained else None)
        self.stem = nn.Sequential(encoder.conv1, encoder.bn1, encoder.relu)
        self.pool = encoder.maxpool
        self.layers = nn.ModuleList([encoder.layer1, encoder.layer2, encoder.layer3, encoder.layer4])
        self.up = nn.ModuleList([UpBlock(512, 256, 128), UpBlock(128, 128, 64),
                                 UpBlock(64, 64, 32), UpBlock(32, 64, 24), UpBlock(24, 3, 16)])
        self.output = nn.Conv2d(16, 1, 1)
        nn.init.constant_(self.output.bias, -2.0)

    def train(self, mode=True):
        super().train(mode)
        # A batch of one must not destabilize pretrained running statistics.
        for module in self.modules():
            if isinstance(module, nn.BatchNorm2d):
                module.eval()
        return self

    def forward(self, image):
        features = [image, self.stem(image)]
        x = self.pool(features[-1])
        for layer in self.layers:
            x = layer(x)
            features.append(x)
        x = features.pop()
        for up, skip in zip(self.up, reversed(features)):
            x = up(x, skip)
        return self.output(x)


def load_records(data):
    """Use snapshot geometry and hashes, never an annotation proposal folder."""
    cfg = load_config(data)
    root = Path(cfg['path'])
    if cfg['names'] not in (['damage'], ['screen_crack']):
        raise ValueError('Expected a single damage or screen_crack class.')
    records = json.loads((root / 'split_manifest.json').read_text(encoding='utf-8'))['records']
    groups = {}
    for row in records:
        rid, split = row['annotation_id'], row['split']
        if split not in ('train', 'val', 'test') or Path(rid).name != rid:
            raise ValueError('Invalid snapshot record.')
        for field, folder, suffix in [('image', 'images', '.png'), ('mask', 'canonical_masks', '.png')]:
            path = root / split / folder / (rid + suffix)
            if digest(path) != row[f'{field}_sha256']:
                raise ValueError(f'{rid}: source {field} changed.')
            row[field] = str(path)
        for token in [('group', row['group']), ('pixels', row['pixel_sha256'])]:
            if token in groups and groups[token] != split:
                raise ValueError('Device or duplicate image crosses data splits.')
            groups[token] = split
    return records


class PatchSource:
    """Bound the image cache; never resize a thin damage mask."""
    def __init__(self, records):
        self.records = records
        self.positive = [r for r in records if r['kind'] == 'damaged']
        self.normal = [r for r in records if r['kind'] == 'normal']

    @lru_cache(maxsize=2)
    def pair(self, image_path, mask_path):
        with Image.open(image_path) as image:
            rgb = np.asarray(image.convert('RGB')).copy()
        with Image.open(mask_path) as image:
            mask = np.asarray(image.convert('L'))
        if rgb.shape[:2] != mask.shape or not np.isin(mask, [0, 255]).all():
            raise ValueError(f'Image/mask mismatch: {image_path}')
        return rgb, (mask > 0).astype(np.uint8)

    def sample(self, rng, size, positive=None, row=None):
        if row is None:
            positive = rng.random() < .75 if positive is None else positive
            pool = self.positive if positive or rng.random() < .5 else self.normal
            if not pool:
                raise ValueError('Both positive and normal training examples are required.')
            row = pool[int(rng.integers(len(pool)))]
        rgb, mask = self.pair(row['image'], row['mask'])
        h, w = mask.shape
        if positive is None:
            positive = row['kind'] == 'damaged'
        if positive:
            indices = np.flatnonzero(mask)
            if not len(indices):
                raise ValueError(f'Positive image has no mask: {row["annotation_id"]}')
            y, x = divmod(int(indices[int(rng.integers(len(indices)))]), w)
            x = int(np.clip(x - rng.integers(size // 4, 3 * size // 4), 0, max(0, w-size)))
            y = int(np.clip(y - rng.integers(size // 4, 3 * size // 4), 0, max(0, h-size)))
        else:
            best = None
            # Also learn healthy glass, reflections and backgrounds of damaged phones.
            # Keep the exact mask even when no completely clean crop can be found.
            for _ in range(12 if row['kind'] == 'damaged' else 1):
                cx = int(rng.integers(max(1, w-size+1)))
                cy = int(rng.integers(max(1, h-size+1)))
                region = mask[cy:cy+size, cx:cx+size]
                fraction = float(np.count_nonzero(region)) / region.size
                if best is None or fraction < best[0]:
                    best = (fraction, cx, cy)
                if fraction == 0:
                    break
            _, x, y = best
        image, target = crop_pair(rgb, mask, x, y, size)
        return image, target, dict(id=row['annotation_id'], split=row['split'],
                                   x=x, y=y, size=size, image_sha256=row['image_sha256'],
                                   mask_sha256=row['mask_sha256'])


def crop_pair(rgb, mask, x, y, size):
    height, width = mask.shape
    cw, ch = min(size, width-x), min(size, height-y)
    image = np.zeros((size, size, 3), dtype=np.uint8)
    # Padding is ignored in loss and metrics, not labeled as healthy material.
    target = np.full((size, size), 255, dtype=np.uint8)
    image[:ch, :cw] = rgb[y:y+ch, x:x+cw]
    target[:ch, :cw] = mask[y:y+ch, x:x+cw]
    return image, target


def image_tensor(rgb):
    tensor = torch.from_numpy(np.ascontiguousarray(rgb.transpose(2, 0, 1))).float() / 255
    mean = tensor.new_tensor([.485, .456, .406])[:, None, None]
    std = tensor.new_tensor([.229, .224, .225])[:, None, None]
    return (tensor - mean) / std


def damage_loss(logits, target, pos_weight=4.0):
    valid = target != 255
    if not valid.any():
        raise ValueError('The crop contains no valid source pixels.')
    truth = (target == 1).float()
    logits = logits[:, 0].float()
    bce = F.binary_cross_entropy_with_logits(logits, truth,
        pos_weight=logits.new_tensor(pos_weight), reduction='none')[valid].mean()
    probability = logits.sigmoid()
    intersection = (probability * truth * valid).sum(dim=(-1, -2))
    cardinality = ((probability + truth) * valid).sum(dim=(-1, -2))
    dice = 1 - ((2 * intersection + 1) / (cardinality + 1)).mean()
    return bce + dice


def pixel_counts(prediction, target):
    valid = target != 255
    foreground = target == 1
    return dict(tp=int((prediction & foreground & valid).sum()),
                fp=int((prediction & ~foreground & valid).sum()),
                fn=int((~prediction & foreground & valid).sum()))


def scores(counts):
    tp, fp, fn = (counts[k] for k in ('tp', 'fp', 'fn'))
    return dict(damage_dice=2*tp / max(2*tp+fp+fn, 1),
                damage_iou=tp / max(tp+fp+fn, 1),
                precision=tp / max(tp+fp, 1), recall=tp / max(tp+fn, 1))


def axis_starts(length, size, overlap):
    if not 0 <= overlap < size:
        raise ValueError('Overlap must be smaller than patch size.')
    if length <= size:
        return [0]
    starts = list(range(0, length-size+1, size-overlap))
    if starts[-1] != length-size:
        starts.append(length-size)
    return starts


@torch.inference_mode()
def tiled_probability(model, rgb, size, overlap, device):
    model.eval()
    h, w = rgb.shape[:2]
    probability = np.zeros((h, w), dtype=np.float32)
    counts = np.zeros((h, w), dtype=np.float32)
    for y in axis_starts(h, size, overlap):
        for x in axis_starts(w, size, overlap):
            ch, cw = min(size, h-y), min(size, w-x)
            patch = np.zeros((size, size, 3), dtype=np.uint8)
            patch[:ch, :cw] = rgb[y:y+ch, x:x+cw]
            logits = model(image_tensor(patch)[None].to(device))
            if not torch.isfinite(logits).all():
                raise ValueError('Non-finite model output during tiled inference.')
            pred = logits[0, 0].float().sigmoid().cpu().numpy()[:ch, :cw]
            probability[y:y+ch, x:x+cw] += pred
            counts[y:y+ch, x:x+cw] += 1
    return probability / counts


def overlay(rgb, mask):
    image = rgb.astype(np.float32).copy()
    image[mask] = image[mask] * .55 + np.array([0, 255, 50], dtype=np.float32) * .45
    return Image.fromarray(np.uint8(image.clip(0, 255)))
