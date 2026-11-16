"""Read-only validator for the separately curated keyboard inspection dataset."""
from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageOps


SPLITS = {"train", "val", "test"}
LABELS = {"normal", "missing_key", "shifted_key", "tilted_key", "uncertain"}
SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def images(root: Path) -> dict[str, tuple[Path, int, int]]:
    found = {}
    for split in SPLITS:
        folder = root / split / "images"
        if not folder.is_dir():
            print(f"ERROR missing directory: {folder}")
            continue
        for image in sorted(folder.rglob("*")):
            if image.suffix.lower() not in SUFFIXES:
                continue
            relative = image.relative_to(root / split).as_posix()
            try:
                with Image.open(image) as opened:
                    width, height = ImageOps.exif_transpose(opened).size
                    opened.verify()
                found[f"{split}/{relative}"] = (image, width, height)
            except Exception as error:
                print(f"ERROR unreadable image {image}: {error}")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=Path("datasets/keyboard"))
    args = parser.parse_args(); root = args.dataset_dir
    records = images(root); errors = []
    annotation = root / "annotations.csv"
    if not annotation.is_file():
        print(f"ERROR missing annotation file: {annotation}")
        return 1
    with annotation.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    required = {"image", "split", "layout", "label", "x1", "y1", "x2", "y2", "reviewer"}
    if not rows or not required.issubset(rows[0]):
        print("ERROR annotations.csv is empty or missing required columns")
        return 1
    referenced = set(); counts = Counter()
    for line, row in enumerate(rows, start=2):
        image, split, label = row["image"].strip(), row["split"].strip(), row["label"].strip()
        key = f"{split}/{image}" if not image.startswith(f"{split}/") else image
        referenced.add(key); counts[label] += 1
        if split not in SPLITS: errors.append(f"line {line}: invalid split {split}")
        if label not in LABELS: errors.append(f"line {line}: unsupported label {label}")
        if key not in records: errors.append(f"line {line}: image not found: {key}"); continue
        if label == "normal":
            if any(row[column].strip() for column in ("x1", "y1", "x2", "y2")):
                errors.append(f"line {line}: normal image must not have a bounding box")
            continue
        try:
            x1, y1, x2, y2 = (float(row[column]) for column in ("x1", "y1", "x2", "y2"))
            _, width, height = records[key]
            if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
                errors.append(f"line {line}: bounding box outside image")
        except ValueError:
            errors.append(f"line {line}: non-numeric bounding box")
        if not row["reviewer"].strip(): errors.append(f"line {line}: missing reviewer")
    unlabelled = sorted(set(records) - referenced)
    if unlabelled: errors.append(f"{len(unlabelled)} images have no annotation, e.g. {unlabelled[0]}")
    hashes = defaultdict(list)
    for key, (path, _, _) in records.items(): hashes[digest(path)].append(key)
    leakage = [paths for paths in hashes.values() if len({path.split('/')[0] for path in paths}) > 1]
    print(f"Images: {len(records)}; annotations: {len(rows)}; labels: {dict(sorted(counts.items()))}")
    print(f"Exact cross-split duplicate groups: {len(leakage)}")
    for paths in leakage: errors.append("cross-split duplicate: " + ", ".join(paths))
    for error in errors: print("ERROR", error)
    print("VALID" if not errors else f"INVALID ({len(errors)} issue(s))")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
