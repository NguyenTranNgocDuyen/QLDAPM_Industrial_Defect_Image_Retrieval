"""
Flask Server cho Công cụ Kiểm tra và Gán nhãn Bàn phím (Keyboard Annotation Reviewer & Editor)
"""

import os
import json
from pathlib import Path
from flask import Flask, jsonify, request, send_file, render_template

app = Flask(__name__, template_folder="templates", static_folder="static")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BASE_DATASET = REPO_ROOT / "datasets" / "keyboard" / "training_dataset"
DEFAULT_DATASET = BASE_DATASET / "processed_v7_autolabeled" / "multi_class"

CLASS_NAMES = {
    0: "key_ok",
    1: "key_damaged",
    2: "key_missing"
}


def get_dataset_dir(dataset_name="multi_class"):
    if dataset_name == "multi_class":
        return BASE_DATASET / "processed_v7_autolabeled" / "multi_class"
    elif dataset_name == "keys_v6":
        return BASE_DATASET / "processed"
    elif dataset_name == "stage1_merged":
        return BASE_DATASET / "processed_v7_autolabeled" / "stage1_merged"
    return DEFAULT_DATASET


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/datasets")
def list_datasets():
    return jsonify([
        {"id": "multi_class", "name": "v7 Đã Auto-label (key_ok vs key_damaged)"},
        {"id": "keys_v6", "name": "keys_v6 Chuẩn (Gốc Roboflow)"},
        {"id": "stage1_merged", "name": "v7 Stage 1 Merged (1 class key)"}
    ])


@app.route("/api/images")
def list_images():
    dataset_name = request.args.get("dataset", "multi_class")
    split = request.args.get("split", "train")
    filter_type = request.args.get("filter", "all")  # all, damaged_only, clean_only

    ds_dir = get_dataset_dir(dataset_name)
    img_dir = ds_dir / split / "images"
    lbl_dir = ds_dir / split / "labels"

    if not img_dir.exists():
        return jsonify([])

    extensions = ("*.jpg", "*.jpeg", "*.png")
    img_files = []
    for ext in extensions:
        img_files.extend(img_dir.glob(ext))

    img_files.sort(key=lambda p: p.name)

    results = []
    for p in img_files:
        lbl_p = lbl_dir / (p.stem + ".txt")
        damaged_count = 0
        total_boxes = 0

        if lbl_p.exists():
            lines = [l.strip() for l in lbl_p.read_text(encoding="utf-8").splitlines() if l.strip()]
            total_boxes = len(lines)
            for l in lines:
                parts = l.split()
                if parts and parts[0] == "1":
                    damaged_count += 1

        if filter_type == "damaged_only" and damaged_count == 0:
            continue
        if filter_type == "clean_only" and damaged_count > 0:
            continue

        results.append({
            "name": p.name,
            "stem": p.stem,
            "total_boxes": total_boxes,
            "damaged_count": damaged_count,
            "ok_count": total_boxes - damaged_count
        })

    return jsonify(results)


@app.route("/api/image/<dataset>/<split>/<filename>")
def get_image(dataset, split, filename):
    ds_dir = get_dataset_dir(dataset)
    img_path = ds_dir / split / "images" / filename
    if not img_path.exists():
        return "Image not found", 404
    return send_file(str(img_path))


@app.route("/api/labels/<dataset>/<split>/<filename>", methods=["GET"])
def get_labels(dataset, split, filename):
    ds_dir = get_dataset_dir(dataset)
    stem = Path(filename).stem
    lbl_path = ds_dir / split / "labels" / f"{stem}.txt"

    boxes = []
    if lbl_path.exists():
        lines = [l.strip() for l in lbl_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        for idx, line in enumerate(lines):
            parts = line.split()
            if len(parts) >= 5:
                cls_id = int(parts[0])
                cx, cy, w, h = [float(v) for v in parts[1:5]]
                boxes.append({
                    "id": idx + 1,
                    "cls": cls_id,
                    "cls_name": CLASS_NAMES.get(cls_id, f"class_{cls_id}"),
                    "cx": cx,
                    "cy": cy,
                    "w": w,
                    "h": h
                })

    return jsonify({"filename": filename, "boxes": boxes})


@app.route("/api/labels/<dataset>/<split>/<filename>", methods=["POST"])
def save_labels(dataset, split, filename):
    ds_dir = get_dataset_dir(dataset)
    stem = Path(filename).stem
    lbl_path = ds_dir / split / "labels" / f"{stem}.txt"
    lbl_path.parent.mkdir(parents=True, exist_ok=True)

    data = request.json or {}
    boxes = data.get("boxes", [])

    lines = []
    for b in boxes:
        cls_id = int(b.get("cls", 0))
        cx = float(b.get("cx", 0.0))
        cy = float(b.get("cy", 0.0))
        w = float(b.get("w", 0.0))
        h = float(b.get("h", 0.0))
        lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

    lbl_path.write_text("\n".join(lines), encoding="utf-8")
    return jsonify({"status": "success", "count": len(lines)})


@app.route("/api/delete_image/<dataset>/<split>/<filename>", methods=["POST"])
def delete_image(dataset, split, filename):
    ds_dir = get_dataset_dir(dataset)
    img_path = ds_dir / split / "images" / filename
    stem = Path(filename).stem
    lbl_path = ds_dir / split / "labels" / f"{stem}.txt"

    deleted_dir = BASE_DATASET / "deleted" / dataset / split
    del_img_dir = deleted_dir / "images"
    del_lbl_dir = deleted_dir / "labels"
    del_img_dir.mkdir(parents=True, exist_ok=True)
    del_lbl_dir.mkdir(parents=True, exist_ok=True)

    import shutil
    moved_files = []
    if img_path.exists():
        shutil.move(str(img_path), str(del_img_dir / filename))
        moved_files.append(filename)

    if lbl_path.exists():
        shutil.move(str(lbl_path), str(del_lbl_dir / f"{stem}.txt"))
        moved_files.append(f"{stem}.txt")

    return jsonify({"status": "success", "moved": moved_files})


@app.route("/api/deduplicate/<dataset>", methods=["POST"])
def run_deduplicate(dataset):
    ds_dir = get_dataset_dir(dataset)
    deleted_dir = BASE_DATASET / "deleted" / dataset
    
    import sys
    scripts_dir = REPO_ROOT / "scripts" / "keyboard"
    sys.path.append(str(scripts_dir))
    from deduplicate_dataset import deduplicate
    moved, kept = deduplicate(str(ds_dir), str(deleted_dir))
    return jsonify({"status": "success", "moved": moved, "kept": kept})



if __name__ == "__main__":
    print("Khởi động Keyboard Annotation Reviewer tại http://localhost:5050")
    app.run(host="127.0.0.1", port=5050, debug=False)
