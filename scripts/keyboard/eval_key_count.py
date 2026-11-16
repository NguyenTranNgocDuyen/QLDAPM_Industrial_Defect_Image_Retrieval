"""
Script đánh giá Stage 1: Đếm số phím detect được / tổng số phím thật trên mỗi ảnh
"""

from pathlib import Path
import numpy as np
from ultralytics import YOLO


def evaluate_key_coverage(model_path: str, val_images_dir: str, val_labels_dir: str, conf_thresh: float = 0.3, iou_thresh: float = 0.4):
    model = YOLO(model_path)
    img_dir = Path(val_images_dir)
    lbl_dir = Path(val_labels_dir)

    img_files = list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png"))
    if not img_files:
        print("Không tìm thấy ảnh nào.")
        return

    results_stats = []

    for img_p in img_files:
        lbl_p = lbl_dir / (img_p.stem + ".txt")
        gt_count = 0
        if lbl_p.exists():
            lines = [l.strip() for l in lbl_p.read_text().splitlines() if l.strip()]
            gt_count = len(lines)

        preds = model.predict(source=str(img_p), conf=conf_thresh, iou=iou_thresh, verbose=False)
        pred_count = len(preds[0].boxes) if preds else 0

        coverage = (pred_count / gt_count * 100.0) if gt_count > 0 else 0.0
        results_stats.append({
            "img": img_p.name,
            "gt": gt_count,
            "pred": pred_count,
            "coverage": coverage
        })

    coverages = [r["coverage"] for r in results_stats if r["gt"] > 0]
    avg_coverage = np.mean(coverages)
    min_coverage = np.min(coverages)

    print(f"\n================ KẾT QUẢ ĐÁNH GIÁ ĐỘ PHỦ PHÍM ================")
    print(f"Tổng số ảnh đánh giá: {len(results_stats)}")
    print(f"Độ phủ phím trung bình (pred/gt): {avg_coverage:.2f}% (Mục tiêu: >=98%)")
    print(f"Độ phủ phím thấp nhất trên 1 ảnh: {min_coverage:.2f}%")
    print("=============================================================")


if __name__ == "__main__":
    import sys
    repo_root = Path(__file__).resolve().parent.parent.parent
    ckpt = sys.argv[1] if len(sys.argv) > 1 else str(repo_root / "image-processing/models/keyboard_yolo11n_keys_v1.pt")
    ds_base = repo_root / "datasets/keyboard/training_dataset/processed"
    evaluate_key_coverage(
        model_path=ckpt,
        val_images_dir=str(ds_base / "val/images"),
        val_labels_dir=str(ds_base / "val/labels"),
    )
