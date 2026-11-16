"""
Script huấn luyện YOLO11 Stage 1: Detector phím (1 class: 'key')
Tối ưu cho GPU GTX 1650 (4GB VRAM): batch=8, imgsz=960, amp=True
"""

from pathlib import Path
from ultralytics import YOLO


def train():
    repo_root = Path(__file__).resolve().parent.parent.parent
    data_yaml = repo_root / "datasets" / "keyboard" / "training_dataset" / "data.yaml"
    project_dir = repo_root / "image-processing" / "keyboard_vision" / "runs" / "stage1_key_detector"

    # Dùng yolo11n để train nhanh, ít tốn VRAM
    model = YOLO("yolo11n.pt")

    model.train(
        data=str(data_yaml),
        epochs=25,
        imgsz=800,          # Cân bằng độ chi tiết và tốc độ trên GTX 1650
        batch=8,            # Phù hợp GTX 1650 4GB VRAM
        device=0,           # Sử dụng GPU NVIDIA
        project=str(project_dir),
        name="yolo11n_keys_v1",
        fliplr=0.0,         # Tắt lật ngang theo nguyên tắc dữ liệu
        flipud=0.0,         # Tắt lật dọc
        degrees=5.0,        # Xoay nhẹ góc chụp
        hsv_v=0.3,          # Tăng giảm độ sáng
        workers=2,
        save=True,
        save_period=10,
        exist_ok=True,
    )


if __name__ == "__main__":
    train()
