"""Audit external keyboard datasets and build reproducible, derived training exports.

Raw data remains in datasets/keyboard/external. The generated manifests and labels
refer back to it; only the cleaned BSX binary-defect export copies its 429 unique
images so that its replacement split cannot leak the original Roboflow split.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path("datasets/keyboard")
EXTERNAL = ROOT / "external"
DERIVED = ROOT / "derived"
SPLITS = ("train", "val", "test")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_voc(xml_path: Path) -> tuple[int, int, list[dict[str, int | str]]]:
    root = ET.parse(xml_path).getroot()
    width = int(root.findtext("size/width")); height = int(root.findtext("size/height"))
    objects = []
    for object_node in root.findall("object"):
        box = object_node.find("bndbox")
        if box is None:
            continue
        objects.append({"label": object_node.findtext("name", ""),
                        "x1": int(float(box.findtext("xmin", "0"))), "y1": int(float(box.findtext("ymin", "0"))),
                        "x2": int(float(box.findtext("xmax", "0"))), "y2": int(float(box.findtext("ymax", "0")))})
    return width, height, objects


def voc_records(root: Path, with_hash: bool = True) -> list[dict]:
    rows = []
    for image in sorted(root.rglob("*.jpg")):
        xml = image.with_suffix(".xml")
        if not xml.is_file():
            rows.append({"image": image, "xml": None, "sha256": sha256(image) if with_hash else str(image.relative_to(root)), "error": "missing_xml"})
            continue
        width, height, objects = parse_voc(xml)
        rows.append({"image": image, "xml": xml, "sha256": sha256(image) if with_hash else str(image.relative_to(root)), "width": width, "height": height,
                     "objects": objects, "split": image.relative_to(root).parts[0]})
    return rows


def audit(name: str, rows: list[dict]) -> dict:
    hashes = defaultdict(list)
    classes = Counter(); invalid = 0; empty = 0
    for row in rows:
        hashes[row["sha256"]].append(row)
        objects = row.get("objects", [])
        empty += not bool(objects)
        for box in objects:
            classes[box["label"]] += 1
            if not (0 <= box["x1"] < box["x2"] <= row["width"] and 0 <= box["y1"] < box["y2"] <= row["height"]):
                invalid += 1
    duplicate_groups = [group for group in hashes.values() if len(group) > 1]
    cross_split = [group for group in duplicate_groups if len({item.get("split") for item in group}) > 1]
    return {"name": name, "images": len(rows), "classes": dict(sorted(classes.items())), "empty_annotations": empty,
            "invalid_boxes_before_clamp": invalid, "duplicate_groups": len(duplicate_groups),
            "duplicate_extra_images": sum(len(group) - 1 for group in duplicate_groups), "cross_split_duplicate_groups": len(cross_split)}


def split_for(unique_rows: list[dict]) -> dict[str, str]:
    ordered = sorted(unique_rows, key=lambda row: row["sha256"])
    total = len(ordered); train_end = round(total * .70); val_end = train_end + round(total * .15)
    return {row["sha256"]: "train" if index < train_end else "val" if index < val_end else "test"
            for index, row in enumerate(ordered)}


def clamped(box: dict, width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1 = max(0, min(width - 1, box["x1"])), max(0, min(height - 1, box["y1"]))
    x2, y2 = max(x1 + 1, min(width, box["x2"])), max(y1 + 1, min(height, box["y2"]))
    return x1, y1, x2, y2


def write_yolo(label_path: Path, boxes: list[dict], width: int, height: int, class_ids: dict[str, int]) -> int:
    lines = []
    for box in boxes:
        x1, y1, x2, y2 = clamped(box, width, height)
        lines.append(f"{class_ids[box['label']]} {(x1 + x2) / 2 / width:.8f} {(y1 + y2) / 2 / height:.8f} {(x2 - x1) / width:.8f} {(y2 - y1) / height:.8f}")
    label_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)


def build_bsx(rows: list[dict], destination: Path) -> dict:
    by_hash = {}
    for row in rows: by_hash.setdefault(row["sha256"], row)
    unique = list(by_hash.values()); assignments = split_for(unique); clamped_count = 0; manifests = []
    for row in unique:
        split = assignments[row["sha256"]]; image_target = destination / split / "images" / f"{row['sha256']}.jpg"
        image_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(row["image"], image_target) if not image_target.exists() else None
        normalized = []
        for box in row["objects"]:
            fixed = {"label": "keyboard_defect", "x1": clamped(box, row["width"], row["height"])[0],
                     "y1": clamped(box, row["width"], row["height"])[1], "x2": clamped(box, row["width"], row["height"])[2],
                     "y2": clamped(box, row["width"], row["height"])[3]}
            clamped_count += tuple(fixed[key] for key in ("x1", "y1", "x2", "y2")) != (box["x1"], box["y1"], box["x2"], box["y2"])
            normalized.append(fixed)
        write_yolo(destination / split / "labels" / f"{row['sha256']}.txt", normalized, row["width"], row["height"], {"keyboard_defect": 0})
        manifests.append({"image": str(image_target.as_posix()), "split": split, "sha256": row["sha256"], "source": str(row["image"].as_posix()),
                          "width": row["width"], "height": row["height"], "object_count": len(normalized), "source_label": "dameged-keys", "label": "keyboard_defect"})
    with (destination / "manifest.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(manifests[0])); writer.writeheader(); writer.writerows(manifests)
    (destination / "data.yaml").write_text("path: .\ntrain: train/images\nval: val/images\ntest: test/images\nnames:\n  0: keyboard_defect\n", encoding="utf-8")
    return {"unique_images": len(unique), "splits": dict(Counter(row["split"] for row in manifests)), "clamped_boxes": clamped_count,
            "label_mapping": {"dameged-keys": "keyboard_defect"}}


def build_keycap_yolo(rows: list[dict], destination: Path) -> dict:
    classes = sorted({box["label"] for row in rows for box in row.get("objects", [])})
    class_ids = {label: index for index, label in enumerate(classes)}; count = 0; manifest = []
    for row in rows:
        relative = row["image"].relative_to(row["image"].parents[1])
        write_yolo(destination / relative.with_suffix(".txt"), row["objects"], row["width"], row["height"], class_ids)
        count += 1
        manifest.append({"image": str(row["image"].as_posix()), "label": str((destination / relative.with_suffix(".txt")).as_posix()),
                         "split": relative.parts[0], "width": row["width"], "height": row["height"], "object_count": len(row["objects"])})
    (destination / "classes.json").write_text(json.dumps(class_ids, indent=2, ensure_ascii=False), encoding="utf-8")
    with (destination / "manifest.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(manifest[0])); writer.writeheader(); writer.writerows(manifest)
    (destination / "README.md").write_text("YOLO label files refer to immutable images in ../../external/keyboard-key-detection/dataset_final. "
                                            "This source has train/test only; do not use it as keyboard-defect evaluation data.\n", encoding="utf-8")
    return {"images": count, "classes": len(classes), "image_source": "external/keyboard-key-detection/dataset_final"}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, default=DERIVED)
    parser.add_argument("--skip-keycap", action="store_true", help="Prepare only the smaller BSX defect export.")
    args = parser.parse_args()
    bsx = voc_records(EXTERNAL / "roboflow-bsx-defect")
    rsi = voc_records(EXTERNAL / "roboflow-rsi-defect")
    defect_source = bsx if bsx else rsi
    if not defect_source:
        print(f"Warning: No defect records found in {EXTERNAL / 'roboflow-bsx-defect'} or {EXTERNAL / 'roboflow-rsi-defect'}")
    rsi_hashes = {row["sha256"] for row in rsi}; bsx_hashes = {row["sha256"] for row in bsx}
    args.output.mkdir(parents=True, exist_ok=True)
    print("Preparing unique defect export...", flush=True)
    report = {"bsx": audit("bsx", bsx) if bsx else {}, "rsi": audit("rsi", rsi) if rsi else {},
              "rsi_is_subset_of_bsx": rsi_hashes.issubset(bsx_hashes) if (bsx and rsi) else True,
              "shared_bsx_rsi_hashes": len(rsi_hashes & bsx_hashes),
              "derived_bsx": build_bsx(defect_source, args.output / "bsx-keyboard-defect") if defect_source else {}}
    if not args.skip_keycap:
        print("Parsing Kaggle key-level XML and exporting YOLO labels...", flush=True)
        kaggle = voc_records(EXTERNAL / "keyboard-key-detection" / "dataset_final", with_hash=False)
        report["key_detection"] = audit("key_detection", kaggle)
        report["derived_keycap_yolo"] = build_keycap_yolo(kaggle, args.output / "keycap-yolo-labels")
    (args.output / "audit-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__": main()
