"""Audit YOLO polygon labels and build an isolated, reproducible training copy."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parent
EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tif', '.tiff'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_config(data):
    data = Path(data).resolve()
    cfg = yaml.safe_load(data.read_text(encoding='utf-8-sig'))
    root = Path(cfg.get('path') or data.parent)
    if not root.is_absolute():
        root = data.parent / root
    cfg['path'] = str(root.resolve())
    names = cfg.get('names', [])
    if isinstance(names, dict):
        names = [names[i] for i in range(len(names))]
    if not names or cfg.get('nc', len(names)) != len(names):
        raise ValueError('names must be nonempty and agree with nc.')
    cfg['names'] = names
    return cfg


def parse_labels(text, classes):
    """Return valid polygons and line-specific errors; never invent mask geometry."""
    polygons, errors = [], []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            values = [float(v) for v in line.split()]
            if not all(math.isfinite(v) for v in values):
                raise ValueError('NaN/Inf')
            cls, coords = values[0], values[1:]
            if not cls.is_integer() or not 0 <= cls < classes:
                raise ValueError('class index outside names')
            if len(coords) == 4:
                raise ValueError('5-token detection/box row mixed into segmentation; redraw a polygon')
            if len(coords) < 6 or len(coords) % 2:
                raise ValueError(f'need >=3 xy points; got {len(coords)} coordinates')
            if not all(0 <= v <= 1 for v in coords):
                raise ValueError('coordinates must be normalized to [0,1]')
            points = list(zip(coords[::2], coords[1::2]))
            if len(set(points)) < 3:
                raise ValueError('fewer than three distinct vertices')
            area = abs(sum(x * points[(i+1) % len(points)][1] -
                           points[(i+1) % len(points)][0] * y
                           for i, (x, y) in enumerate(points))) / 2
            if area <= 1e-12:
                raise ValueError('zero-area polygon')
            polygons.append({'class_id': int(cls), 'points': points, 'line': number})
        except (ValueError, IndexError) as exc:
            errors.append({'line': number, 'reason': str(exc), 'raw': line})
    return polygons, errors


def serialize(polygons):
    return ''.join(str(p['class_id']) + ' ' + ' '.join(
        f'{v:.9f}' for xy in p['points'] for v in xy) + '\n' for p in polygons)


def copy_training_image(source, dest):
    """Trim JPEG trailer metadata in the copy, avoiding Ultralytics' lossy repair.

    Some valid camera files have vendor data after EOI. Check decoded pixels before
    trimming; never repair genuinely truncated data or modify the original.
    """
    shutil.copy2(source, dest)
    if Path(dest).suffix.lower() not in ('.jpg', '.jpeg'):
        return None
    raw = Path(dest).read_bytes()
    if raw.endswith(b'\xff\xd9'):
        return None
    end = raw.rfind(b'\xff\xd9')
    if end < 0:
        raise ValueError(f'JPEG is missing its end marker; review the source: {source}')
    import io
    trimmed = raw[:end+2]
    with Image.open(io.BytesIO(raw)) as before, Image.open(io.BytesIO(trimmed)) as after:
        if before.size != after.size or before.convert('RGB').tobytes() != after.convert('RGB').tobytes():
            raise ValueError(f'JPEG trailer cleanup would change pixels: {source}')
    Path(dest).write_bytes(trimmed)
    return dict(reason='removed JPEG trailer after EOI; decoded pixels unchanged',
                removed_bytes=len(raw)-len(trimmed), prepared_image_sha256=digest(dest))


def scan(data=ROOT / 'data.yaml'):
    cfg = load_config(data)
    root = Path(cfg['path'])
    manifest_path = root / 'reviewed' / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    split_manifest = root / 'split_manifest.json'
    split_records = json.loads(split_manifest.read_text(encoding='utf-8')).get('records', []) if split_manifest.exists() else []
    source_metadata = {r['id']: r for r in split_records}
    device_groups = defaultdict(list)
    records, hashes, originals = [], defaultdict(list), defaultdict(list)
    orphans = []
    for split in ('train', 'val', 'test'):
        if not cfg.get(split):
            continue
        folder = Path(cfg[split])
        if not folder.is_absolute():
            folder = root / folder
        if folder.name != 'images' or not folder.is_dir():
            raise ValueError(f'{split}: expected an existing .../images directory: {folder}')
        images = sorted(p for p in folder.iterdir() if p.suffix.lower() in EXTENSIONS)
        stems = [p.stem for p in images]
        if len(set(stems)) != len(stems):
            raise ValueError(f'{split}: duplicate image stems')
        label_dir = folder.parent / 'labels'
        orphans += [str(p) for p in label_dir.glob('*.txt') if p.stem not in set(stems)]
        for im in images:
            key = f'{split}/{im.name}'
            original_label = label_dir / (im.stem + '.txt')
            overlay = root / 'reviewed' / split / 'labels' / original_label.name
            label = overlay if overlay.exists() else original_label
            text = label.read_text(encoding='utf-8-sig') if label.exists() else ''
            polygons, errors = parse_labels(text, len(cfg['names']))
            image_hash = digest(im)
            label_hash = digest(label) if label.exists() else None
            checked = manifest.get(key, {})
            reviewed = (checked.get('image_sha256') == image_hash and
                        checked.get('label_sha256') == label_hash)
            status = ('invalid' if errors else 'labeled' if polygons else
                      'background' if reviewed and checked.get('status') == 'background' else
                      'empty_unreviewed' if label.exists() else 'missing')
            if overlay.exists() and checked.get('image_sha256') != image_hash:
                status = 'stale_overlay'
                errors.append({'line': 0, 'reason': 'Review overlay belongs to a different/unverified image; relabel.'})
            record = dict(key=key, split=split, image=str(im.resolve()),
                          label=str(label.resolve()), original_label=str(original_label.resolve()),
                          status=status, reviewed=reviewed, polygons=polygons, errors=errors,
                          image_sha256=image_hash, label_sha256=label_hash)
            source = source_metadata.get(im.name, {})
            record['device_group'] = source.get('group')
            record['semantic_label'] = 'normal' if status == 'background' else None
            if source.get('group'):
                device_groups[source['group']].append(key)
            try:
                with Image.open(im) as image:
                    record['size'] = list(image.size)
                    image.verify()
            except Exception as exc:
                record['status'] = 'corrupt_image'
                record['errors'].append({'line': 0, 'reason': str(exc)})
            records.append(record)
            hashes[image_hash].append(key)
            originals[im.stem.split('.rf.')[0]].append(key)
    leakage = [keys for keys in hashes.values() if len({k.split('/')[0] for k in keys}) > 1]
    groups = [keys for keys in originals.values() if len({k.split('/')[0] for k in keys}) > 1]
    summary = {}
    for split in ('train', 'val', 'test'):
        rows = [r for r in records if r['split'] == split]
        summary[split] = dict(images=len(rows), statuses=dict(Counter(r['status'] for r in rows)),
                              valid_polygons=sum(len(r['polygons']) for r in rows),
                              invalid_rows=sum(len(r['errors']) for r in rows))
    return dict(data=str(Path(data).resolve()), config=cfg, summary=summary, records=records,
                exact_cross_split_duplicates=leakage, source_name_cross_split_groups=groups,
                device_cross_split_groups=[keys for keys in device_groups.values()
                                           if len({k.split('/')[0] for k in keys}) > 1],
                orphan_labels=orphans)


def write_audit(report, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'dataset_audit.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    with (out / 'review_queue.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['key', 'status', 'reviewed', 'valid_polygons', 'errors', 'image', 'label'])
        for r in sorted(report['records'], key=lambda r: (r['status'] == 'labeled', r['key'])):
            writer.writerow([r['key'], r['status'], r['reviewed'], len(r['polygons']),
                             json.dumps(r['errors'], ensure_ascii=False), r['image'], r['label']])


def prepare(report, out, allow_partial=False):
    """Unknown empty labels never become negative examples. Test remains separate."""
    if (report['exact_cross_split_duplicates'] or report['source_name_cross_split_groups']
            or report.get('device_cross_split_groups')):
        raise ValueError('Possible train/val/test leakage. Inspect dataset_audit.json before splitting.')
    invalid = [r for r in report['records'] if r['errors']]
    if invalid and not allow_partial:
        raise ValueError('Invalid labels/images found. Relabel first, or explicitly use --allow-partial for a smoke test.')
    if report['orphan_labels']:
        raise ValueError('Orphan label files found; inspect the audit.')
    selected, excluded = [], []
    for r in report['records']:
        if r['status'] in ('corrupt_image', 'stale_overlay'):
            excluded.append(r['key'])
        elif r['polygons'] or r['status'] == 'background':
            selected.append(r)
        else:
            excluded.append(r['key'])
    for split in ('train', 'val'):
        if not any(r['split'] == split and r['polygons'] for r in selected):
            raise ValueError(f'{split} must contain at least one labeled positive image.')
    dest = Path(out).resolve() / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    dest.mkdir(parents=True, exist_ok=False)
    image_repairs = []
    for r in selected:
        image_dest = dest / r['split'] / 'images' / Path(r['image']).name
        label_dest = dest / r['split'] / 'labels' / Path(r['label']).name
        image_dest.parent.mkdir(parents=True, exist_ok=True)
        label_dest.parent.mkdir(parents=True, exist_ok=True)
        repair = copy_training_image(r['image'], image_dest)
        if repair:
            image_repairs.append(dict(key=r['key'], **repair))
        label_dest.write_text(serialize(r['polygons']), encoding='utf-8')
    cfg = dict(path=dest.as_posix(), train='train/images', val='val/images',
               nc=len(report['config']['names']), names=report['config']['names'])
    for field in ('channels', 'max_instances'):
        if field in report['config']:
            cfg[field] = report['config'][field]
    if any(r['split'] == 'test' for r in selected):
        cfg['test'] = 'test/images'
    (dest / 'data.yaml').write_text(yaml.safe_dump(cfg, sort_keys=False), encoding='utf-8')
    # Keep positive review provenance, background confirmation and device groups.
    review = {r['key']: dict(status='background' if r['status'] == 'background' else 'approved', image_sha256=digest(dest / r['split'] / 'images' / Path(r['image']).name),
                            label_sha256=digest(dest / r['split'] / 'labels' / Path(r['label']).name))
              for r in selected if r['reviewed'] or r['status'] == 'background'}
    (dest / 'reviewed').mkdir()
    (dest / 'reviewed' / 'manifest.json').write_text(json.dumps(review, indent=2), encoding='utf-8')
    (dest / 'split_manifest.json').write_text(json.dumps(dict(records=[dict(
        id=Path(r['image']).name, group=r.get('device_group')) for r in selected]), indent=2), encoding='utf-8')
    (dest / 'source_audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (dest / 'provenance.json').write_text(json.dumps(dict(
        source=report['data'], allow_partial=allow_partial, excluded_images=excluded,
        image_repairs=image_repairs,
        dropped_rows=[dict(key=r['key'], errors=r['errors']) for r in invalid],
        included=[{k: r[k] for k in ('key', 'image_sha256', 'label_sha256', 'status')}
                  for r in selected]), indent=2), encoding='utf-8')
    print('Prepared:', dest, 'included:', dict(Counter(r['split'] for r in selected)),
          'excluded:', len(excluded), flush=True)
    return dest / 'data.yaml'
