"""Create a SHA-256 dataset manifest and reject cross-split leakage."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLITS = ("train", "val", "test")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(data_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for split in SPLITS:
        split_dir = data_dir / split
        if not split_dir.is_dir():
            raise FileNotFoundError(f"Missing split directory: {split_dir}")
        for path in sorted(candidate for candidate in split_dir.rglob("*") if candidate.suffix.lower() in IMAGE_SUFFIXES):
            relative = path.relative_to(data_dir)
            class_name = relative.parts[1] if len(relative.parts) >= 3 else ""
            rows.append({"path": relative.as_posix(), "split": split, "class": class_name, "sha256": sha256_file(path)})
    return rows


def duplicate_groups(rows: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    by_hash: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_hash[row["sha256"]].append(row)
    return [group for group in by_hash.values() if len(group) > 1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("docs/dataset_manifest.csv"))
    args = parser.parse_args()

    rows = build_manifest(args.data_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "split", "class", "sha256"])
        writer.writeheader()
        writer.writerows(rows)

    duplicates = duplicate_groups(rows)
    cross_split = [group for group in duplicates if len({row["split"] for row in group}) > 1]
    print(f"Manifest: {args.output} ({len(rows)} images)")
    print(f"Exact duplicate groups: {len(duplicates)}; cross-split groups: {len(cross_split)}")
    for group in cross_split:
        print("CROSS-SPLIT DUPLICATE:", ", ".join(row["path"] for row in group))
    return 1 if cross_split else 0


if __name__ == "__main__":
    raise SystemExit(main())
