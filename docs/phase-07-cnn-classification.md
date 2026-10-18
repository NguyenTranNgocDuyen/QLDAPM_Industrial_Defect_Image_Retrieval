# Phase 7 — CNN phân loại Normal / Defective (TV1)

## Phạm vi bàn giao

TV1 cung cấp một bộ phân loại ảnh toàn cục hai lớp: `defective` (index 0) và
`normal` (index 1). Đây là bước sàng lọc trước YOLO: kết quả có trường
`classifier_result` để TV2/TV3 ghép vào response chung sau này. TV1 **không**
tạo bounding box hoặc loại lỗi chi tiết.

## Dữ liệu và kiểm soát leakage

Dataset hiện có 1.200 ảnh, theo cấu trúc `data/{train,val,test}/{class}`:

| Split | Defective | Normal | Tổng |
|---|---:|---:|---:|
| train | 630 | 210 | 840 |
| val | 135 | 45 | 180 |
| test | 135 | 45 | 180 |

Chạy `python scripts/audit_dataset.py` tạo
[`dataset_manifest.csv`](dataset_manifest.csv) với `path, split, class, sha256`.
Audit ngày bàn giao phát hiện **1 exact duplicate xuyên split**:
`train/normal/patches_105.jpg` và `test/normal/patches_101.jpg`. Script trả exit
code 1 khi có lỗi này. Dữ liệu gốc không bị sửa; chủ dữ liệu cần loại/đưa lại ảnh
vào split hợp lệ trước khi công bố chỉ số test cuối cùng.

## Pipeline tái lập

```text
PIL RGB → resize LANCZOS → Gaussian/Median (tuỳ chọn)
        → CLAHE trên kênh Y của YCrCb (tuỳ chọn)
        → scale [0,1] → chuẩn hoá mean/std tính trên train
        → DefectCNN → sigmoid = P(normal) → threshold từ checkpoint
```

- `cv2.createCLAHE(clipLimit=2.0, tileGridSize=8×8)` được dùng thật, không còn
  histogram equalization toàn cục.
- Mean/std được tính sau các bước deterministic, **chỉ từ `data/train`**, và lưu
  trong checkpoint. Checkpoint cũ không có statistics vẫn chạy với fallback `/255`.
- Chỉ train có augmentation: horizontal flip, rotation ±10° và color jitter
  brightness/contrast 0,12. Seed mặc định là 42; cuDNN deterministic được bật.
- Optimizer AdamW dùng `StepLR(step_size=8, gamma=0.5)`.
- Trên validation, hệ thống thử các ngưỡng `P(normal)` để tối đa F1 của lớp
  defective; khi bằng nhau chọn ngưỡng thấp hơn (thận trọng cho QC). Checkpoint
  lưu `threshold`, metrics tại 0,5 và metrics ngưỡng chọn. Checkpoint cũ fallback
  threshold 0,5.

## Chạy

```bash
python -m pip install -r requirements.txt/tv1.txt
python scripts/audit_dataset.py
python -m model.train --data-dir data --output-dir outputs/model_gaussian --filter-name gaussian --seed 42 --cpu
python -m model.evaluate --checkpoint outputs/model_gaussian/defect_classifier.pt --data-dir data --output-dir outputs/evaluation
python -m scripts.benchmark_inference --checkpoint outputs/model_gaussian/defect_classifier.pt --runs 30
uvicorn ui.local_api:app --reload --port 8000
```

API:

- `GET /health`
- `POST /predict` (multipart field `image`) trả `label`, `confidence`, timing,
  và `classifier_result={label, confidence, normal_probability, threshold}`.
  `preprocessing_ms` chỉ đo một lần preprocess; `inference_ms` chỉ đo phần tensor
  + forward pass.

## Kết quả thực tế với checkpoint Gaussian sẵn có

Checkpoint `outputs/model_gaussian/defect_classifier.pt` là checkpoint cũ nên
được evaluate với fallback chuẩn hoá `/255` và threshold 0,5. Trên test 180 ảnh:

| Operating point | Threshold | Accuracy | Precision defect | Recall defect | F1 defect | FN |
|---|---:|---:|---:|---:|---:|---:|
| Mặc định | 0,5 | 97,22% | 97,10% | 99,26% | 0,9817 | 1 |
| Được chọn | 0,5 | 97,22% | 97,10% | 99,26% | 0,9817 | 1 |

Chi tiết có trong [`evaluation_gaussian_legacy/test_metrics.json`](evaluation_gaussian_legacy/test_metrics.json).
Benchmark CPU với 10 warm-up + 30 lần đo trên `crazing_10.jpg`: p50 **318,062 ms**,
p95 **412,834 ms**, mean **294,811 ms** ([JSON](benchmark_gaussian_cpu.json)).
Môi trường CPU hiện tại chưa đạt mục tiêu 100 ms/ảnh; cần benchmark lại trên máy
đích và/hoặc chuyển sang backbone nhẹ/ONNX trước khi triển khai realtime.

## Giới hạn và phụ thuộc

- Có data leakage như nêu trên; không dùng kết quả test này làm bằng chứng cuối.
- CNN không định vị lỗi. TV2 cần cung cấp YOLO detections/schema để ghép sau
  `classifier_result`.
- TV3 là chủ phần perspective/illumination; TV1 không gọi hay thay đổi pipeline đó.
- Cần rerun training sau khi chủ dữ liệu xử lý duplicate để checkpoint mới thực sự
  chứa CLAHE/mean-std/augmentation/scheduler/calibration.
