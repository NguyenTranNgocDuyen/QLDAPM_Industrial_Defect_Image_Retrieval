"""
Script tự động lọc và rút gọn ảnh trùng lặp trong dataset v7
Chuyển các bản sao augmented (ví dụ .rf.xxxx) vào thư mục dataset/deleted
để giữ lại 1 ảnh gốc duy nhất cho mỗi bàn phím.
"""

import shutil
from pathlib import Path
from collections import defaultdict


def deduplicate(dataset_path: str = None, deleted_path: str = None):
    repo_root = Path(__file__).resolve().parent.parent.parent
    ds_base = repo_root / "datasets/keyboard/training_dataset"
    if dataset_path is None:
        dataset_path = ds_base / "processed_v7_autolabeled" / "multi_class"
    else:
        dataset_path = Path(dataset_path)

    if deleted_path is None:
        deleted_path = ds_base / "deleted" / "multi_class"
    else:
        deleted_path = Path(deleted_path)

    splits = ["train", "val", "test"]
    total_moved = 0
    total_kept = 0

    print(f"=== Bắt đầu rút gọn ảnh trùng lặp ===")
    print(f"Thư mục nguồn: {dataset_path}")
    print(f"Thư mục lưu ảnh đã xóa/rút gọn: {deleted_path}")

    for split in splits:
        img_dir = dataset_path / split / "images"
        lbl_dir = dataset_path / split / "labels"
        if not img_dir.exists():
            continue

        del_img_dir = deleted_path / split / "images"
        del_lbl_dir = deleted_path / split / "labels"
        del_img_dir.mkdir(parents=True, exist_ok=True)
        del_lbl_dir.mkdir(parents=True, exist_ok=True)

        imgs = sorted(list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png")))
        groups = defaultdict(list)
        for p in imgs:
            base_id = p.name.split(".rf.")[0]
            groups[base_id].append(p)

        split_moved = 0
        split_kept = 0

        for base_id, img_list in groups.items():
            # Chọn ảnh giữ lại: ảnh có file nhãn nhiều box nhất hoặc ảnh đầu tiên
            best_img = img_list[0]
            max_boxes = -1
            for p in img_list:
                lbl_p = lbl_dir / (p.stem + ".txt")
                if lbl_p.exists():
                    cnt = len([l for l in lbl_p.read_text(encoding="utf-8").splitlines() if l.strip()])
                    if cnt > max_boxes:
                        max_boxes = cnt
                        best_img = p

            split_kept += 1

            # Di chuyển các ảnh trùng còn lại vào deleted
            for p in img_list:
                if p == best_img:
                    continue

                lbl_p = lbl_dir / (p.stem + ".txt")

                # Move image
                shutil.move(str(p), str(del_img_dir / p.name))
                # Move label if exists
                if lbl_p.exists():
                    shutil.move(str(lbl_p), str(del_lbl_dir / lbl_p.name))

                split_moved += 1

        print(f"  [{split}]: Giữ lại {split_kept} ảnh gốc độc nhất | Đã chuyển {split_moved} ảnh trùng vào 'deleted'")
        total_moved += split_moved
        total_kept += split_kept

    print("======================================================")
    print(f"TỔNG KẾT: Đã dọn dẹp {total_moved} ảnh trùng lặp.")
    print(f"Dataset hiện tại còn lại {total_kept} ảnh độc nhất, sạch sẽ.")
    print("======================================================")
    return total_moved, total_kept


if __name__ == "__main__":
    deduplicate()
