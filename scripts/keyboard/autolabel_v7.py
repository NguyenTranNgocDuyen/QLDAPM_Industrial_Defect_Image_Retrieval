"""
Script tự động gán nhãn bổ sung cho dataset v7 (Auto-labeling v7)
- Dùng model Stage 1 (train từ keys_v6) để quét tìm toàn bộ phím bình thường (key_ok)
- Kết hợp với nhãn sẵn có của v7 (dameged-keys) để gán nhãn phím hỏng (key_damaged)
- Xuất ra 2 bộ nhãn:
  1. Multi-class (0: key_ok, 1: key_damaged)
  2. Stage 1 merged (0: key - cho tất cả các phím, để mở rộng tập train Stage 1)
"""

import sys
import shutil
from pathlib import Path
import numpy as np
from ultralytics import YOLO


def compute_iou(box1, box2):
    """box format: [cx, cy, w, h] (normalized 0-1)"""
    x1_min, x1_max = box1[0] - box1[2] / 2, box1[0] + box1[2] / 2
    y1_min, y1_max = box1[1] - box1[3] / 2, box1[1] + box1[3] / 2
    
    x2_min, x2_max = box2[0] - box2[2] / 2, box2[0] + box2[2] / 2
    y2_min, y2_max = box2[1] - box2[3] / 2, box2[1] + box2[3] / 2
    
    inter_xmin = max(x1_min, x2_min)
    inter_ymin = max(y1_min, y2_min)
    inter_xmax = min(x1_max, x2_max)
    inter_ymax = min(y1_max, y2_max)
    
    inter_w = max(0.0, inter_xmax - inter_xmin)
    inter_h = max(0.0, inter_ymax - inter_ymin)
    inter_area = inter_w * inter_h
    
    area1 = box1[2] * box1[3]
    area2 = box2[2] * box2[3]
    union_area = area1 + area2 - inter_area
    
    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def autolabel_v7_dataset(model_path: str, v7_dir: str, output_dir: str, conf: float = 0.35, iou_thresh: float = 0.3):
    print(f"Đang tải model từ: {model_path}")
    model = YOLO(model_path)
    
    src_base = Path(v7_dir)
    dst_base = Path(output_dir)
    
    # 2 output folders: multi_class và stage1_merged
    multi_dst = dst_base / "multi_class"
    stage1_dst = dst_base / "stage1_merged"
    
    splits = ["train", "valid", "test"]
    stats = {"total_images": 0, "total_keys_ok": 0, "total_keys_damaged": 0}
    
    for split in splits:
        src_img_dir = src_base / split / "images"
        src_lbl_dir = src_base / split / "labels"
        
        dst_split_name = "val" if split == "valid" else split
        
        out_multi_img = multi_dst / dst_split_name / "images"
        out_multi_lbl = multi_dst / dst_split_name / "labels"
        out_stage1_img = stage1_dst / dst_split_name / "images"
        out_stage1_lbl = stage1_dst / dst_split_name / "labels"
        
        for d in [out_multi_img, out_multi_lbl, out_stage1_img, out_stage1_lbl]:
            d.mkdir(parents=True, exist_ok=True)
            
        imgs = list(src_img_dir.glob("*.jpg")) + list(src_img_dir.glob("*.png"))
        print(f"Bắt đầu xử lý {len(imgs)} ảnh trong tập '{split}'...")
        
        for img_p in imgs:
            stats["total_images"] += 1
            lbl_p = src_lbl_dir / (img_p.stem + ".txt")
            
            # 1. Đọc nhãn dameged-keys hiện có của v7
            existing_damaged_boxes = []
            if lbl_p.exists():
                lines = [l.strip() for l in lbl_p.read_text(encoding="utf-8").splitlines() if l.strip()]
                for l in lines:
                    parts = l.split()
                    if len(parts) >= 5:
                        existing_damaged_boxes.append([float(x) for x in parts[1:5]])
                        
            # 2. Dự đoán toàn bộ phím bằng model Stage 1
            preds = model.predict(source=str(img_p), conf=conf, imgsz=800, verbose=False)
            detected_boxes = []
            if preds and len(preds[0].boxes) > 0:
                xywhn = preds[0].boxes.xywhn.cpu().numpy()
                for b in xywhn:
                    detected_boxes.append([float(b[0]), float(b[1]), float(b[2]), float(b[3])])
                    
            # 3. Phân loại và gộp nhãn
            multi_lines = []
            stage1_lines = []
            
            # Giữ lại các nhãn damaged đã biết
            matched_detected_indices = set()
            for d_box in existing_damaged_boxes:
                # Tìm xem có detected_box nào trùng với d_box này không
                for idx, det_box in enumerate(detected_boxes):
                    if compute_iou(d_box, det_box) > iou_thresh:
                        matched_detected_indices.add(idx)
                        
                # Gán nhãn 1 (key_damaged) cho multi_class
                multi_lines.append(f"1 {d_box[0]:.6f} {d_box[1]:.6f} {d_box[2]:.6f} {d_box[3]:.6f}")
                # Gán nhãn 0 (key) cho stage1
                stage1_lines.append(f"0 {d_box[0]:.6f} {d_box[1]:.6f} {d_box[2]:.6f} {d_box[3]:.6f}")
                stats["total_keys_damaged"] += 1
                
            # Các phím còn lại là phím lành lặn (key_ok)
            for idx, det_box in enumerate(detected_boxes):
                if idx in matched_detected_indices:
                    continue
                multi_lines.append(f"0 {det_box[0]:.6f} {det_box[1]:.6f} {det_box[2]:.6f} {det_box[3]:.6f}")
                stage1_lines.append(f"0 {det_box[0]:.6f} {det_box[1]:.6f} {det_box[2]:.6f} {det_box[3]:.6f}")
                stats["total_keys_ok"] += 1
                
            # Copy ảnh sang cả 2 nơi
            shutil.copy2(img_p, out_multi_img / img_p.name)
            shutil.copy2(img_p, out_stage1_img / img_p.name)
            
            # Ghi file nhãn
            (out_multi_lbl / (img_p.stem + ".txt")).write_text("\n".join(multi_lines), encoding="utf-8")
            (out_stage1_lbl / (img_p.stem + ".txt")).write_text("\n".join(stage1_lines), encoding="utf-8")

    print("\n============== HOÀN TẤT TỰ ĐỘNG GÁN NHÃN V7 ==============")
    print(f"Tổng số ảnh đã xử lý: {stats['total_images']}")
    print(f"Tổng số phím lành lặn (key_ok) tự động phát hiện: {stats['total_keys_ok']}")
    print(f"Tổng số phím hư hại (key_damaged) tích hợp: {stats['total_keys_damaged']}")
    print(f"Dữ liệu được lưu tại: {output_dir}")
    print("==========================================================")


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent.parent
    ds_base = repo_root / "datasets/keyboard/training_dataset"
    ckpt = sys.argv[1] if len(sys.argv) > 1 else str(repo_root / "image-processing/models/keyboard_yolo11n_keys_v1.pt")
    v7_path = sys.argv[2] if len(sys.argv) > 2 else str(ds_base / "raw_extracted/defect_v7")
    out_path = sys.argv[3] if len(sys.argv) > 3 else str(ds_base / "processed_v7_autolabeled")
    
    autolabel_v7_dataset(
        model_path=ckpt,
        v7_dir=v7_path,
        output_dir=out_path
    )
