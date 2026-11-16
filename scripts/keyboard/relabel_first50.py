"""
Script gán nhãn lại kỹ lưỡng cho 50 ảnh đầu tiên của tập v7
Sử dụng Multi-scale + Test-Time Rotation Augmentation (TTA) + IoU Non-Maximum Suppression (NMS)
để phủ kín 70-90 phím trên mỗi bàn phím.
"""

import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO


def compute_iou(box1, box2):
    """box: [x1, y1, x2, y2]"""
    inter_x1 = max(box1[0], box2[0])
    inter_y1 = max(box1[1], box2[1])
    inter_x2 = min(box1[2], box2[2])
    inter_y2 = min(box1[3], box2[3])

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


def detect_all_keys_robust(model, im):
    h, w = im.shape[:2]

    # 1. Chiều xuôi
    r1 = model.predict(im, conf=0.07, imgsz=960, iou=0.4, verbose=False)[0]
    b1 = r1.boxes.xyxy.cpu().numpy()

    # 2. Xoay 180 độ (giải quyết ảnh bàn phím lộn ngược / góc ngược)
    im_rot = cv2.rotate(im, cv2.ROTATE_180)
    r2 = model.predict(im_rot, conf=0.07, imgsz=960, iou=0.4, verbose=False)[0]
    b2 = r2.boxes.xyxy.cpu().numpy()
    b2_rot = [[w - b[2], h - b[3], w - b[0], h - b[1]] for b in b2]

    all_b = list(b1) + list(b2_rot)

    # NMS để lọc trùng lặp
    indices = cv2.dnn.NMSBoxes(
        bboxes=[[int(b[0]), int(b[1]), int(b[2] - b[0]), int(b[3] - b[1])] for b in all_b],
        scores=[1.0] * len(all_b),
        score_threshold=0.5,
        nms_threshold=0.35,
    )

    final_boxes = [all_b[i] for i in indices]
    return final_boxes


def relabel_first_50():
    repo_root = Path(__file__).resolve().parent.parent.parent
    model_path = repo_root / "image-processing/models/keyboard_yolo11n_keys_v1.pt"
    print(f"Đang tải model: {model_path}")
    model = YOLO(str(model_path))

    # Thư mục gốc chứa nhãn gốc của v7 (dameged-keys)
    v7_lbl_dir = repo_root / "datasets/keyboard/training_dataset/raw_extracted/defect_v7/train/labels"

    # Thư mục multi_class cần cập nhật
    target_img_dir = repo_root / "datasets/keyboard/training_dataset/processed_v7_autolabeled/multi_class/train/images"
    target_lbl_dir = repo_root / "datasets/keyboard/training_dataset/processed_v7_autolabeled/multi_class/train/labels"

    # Thư mục stage1_merged cần cập nhật
    stage1_lbl_dir = repo_root / "datasets/keyboard/training_dataset/processed_v7_autolabeled/stage1_merged/train/labels"

    images = sorted(list(target_img_dir.glob("*.jpg")))[:50]
    print(f"Bắt đầu gán nhãn lại kỹ lưỡng {len(images)} ảnh đầu tiên...")

    stats_total_keys = 0
    stats_damaged = 0

    for idx, img_p in enumerate(images):
        im = cv2.imread(str(img_p))
        h, w = im.shape[:2]

        # 1. Đọc nhãn gốc dameged-keys của v7
        raw_lbl_p = v7_lbl_dir / (img_p.stem + ".txt")
        raw_damaged_boxes = []
        if raw_lbl_p.exists():
            for line in raw_lbl_p.read_text().splitlines():
                parts = line.strip().split()
                if len(parts) >= 5:
                    cx, cy, bw, bh = [float(v) for v in parts[1:5]]
                    # Convert to xyxy pixels
                    x1 = (cx - bw / 2) * w
                    y1 = (cy - bh / 2) * h
                    x2 = (cx + bw / 2) * w
                    y2 = (cy + bh / 2) * h
                    raw_damaged_boxes.append([x1, y1, x2, y2])

        # 2. Dùng detector siêu nhạy (TTA) tìm mọi phím
        detected_xyxy = detect_all_keys_robust(model, im)

        # 3. Phân loại key_ok vs key_damaged
        multi_lines = []
        stage1_lines = []

        matched_det_indices = set()

        # Đặt các phím damaged gốc
        for d_box in raw_damaged_boxes:
            for d_idx, det_box in enumerate(detected_xyxy):
                if compute_iou(d_box, det_box) > 0.3:
                    matched_det_indices.add(d_idx)

            # xyxy -> normalized cx cy w h
            cx = (d_box[0] + d_box[2]) / 2 / w
            cy = (d_box[1] + d_box[3]) / 2 / h
            bw = (d_box[2] - d_box[0]) / w
            bh = (d_box[3] - d_box[1]) / h

            multi_lines.append(f"1 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
            stage1_lines.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
            stats_damaged += 1
            stats_total_keys += 1

        # Các phím còn lại là key_ok
        for d_idx, det_box in enumerate(detected_xyxy):
            if d_idx in matched_det_indices:
                continue

            cx = (det_box[0] + det_box[2]) / 2 / w
            cy = (det_box[1] + det_box[3]) / 2 / h
            bw = (det_box[2] - det_box[0]) / w
            bh = (det_box[3] - det_box[1]) / h

            # Lọc các box rác méo mó bất thường
            if bw < 0.01 or bh < 0.02 or bw > 0.4:
                continue

            multi_lines.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
            stage1_lines.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
            stats_total_keys += 1

        # Ghi đè nhãn
        (target_lbl_dir / (img_p.stem + ".txt")).write_text("\n".join(multi_lines), encoding="utf-8")
        (stage1_lbl_dir / (img_p.stem + ".txt")).write_text("\n".join(stage1_lines), encoding="utf-8")

        if (idx + 1) % 10 == 0 or idx == len(images) - 1:
            print(f"  Đã hoàn thành {idx + 1}/50 ảnh. Ảnh '{img_p.name[:35]}...' có {len(multi_lines)} phím.")

    print("\n============== HOÀN TẤT GÁN NHÃN LẠI 50 ẢNH ==============")
    print(f"Tổng số phím đã gán: {stats_total_keys} phím")
    print(f"Trung bình mỗi ảnh: {stats_total_keys / len(images):.1f} phím/ảnh (trước đây chỉ 9-15 phím)")
    print(f"Trong đó có: {stats_damaged} phím damaged")
    print("==========================================================")


if __name__ == "__main__":
    relabel_first_50()
