# Python Image Processing

Phạm vi module:

- Xử lý ảnh bằng OpenCV.
- Perspective/illumination/color correction có thể bật tắt.
- Tích hợp model YOLO do TV2 bàn giao.
- Postprocess detection và đo thời gian từng bước.
- Cung cấp internal endpoint `POST /v1/infer` cho Spring Boot.

Input là một ảnh hợp lệ. Output phải tuân theo contract chung và không chứa logic lưu lịch sử hoặc logic giao diện.

## Phase 2 - Perspective Correction

Cài dependency trong môi trường ảo:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Chạy demo Perspective Correction để sinh ảnh before/after:

```powershell
python -m defect_vision.demo
```

Chạy với ảnh thật và bốn góc của thiết bị. Các điểm có thể nhập theo thứ tự bất kỳ:

```powershell
python -m defect_vision.perspective_cli `
  --input path\to\device.jpg `
  --points "80,50;520,70;500,400;60,380" `
  --output-dir outputs\my-device
```

Output:

- `01_original.png`: ảnh đầu vào.
- `02_selected_corners.png`: tứ giác và thứ tự bốn góc.
- `03_corrected.png`: ảnh sau hiệu chỉnh.
- `04_before_after.png`: ảnh so sánh phục vụ báo cáo/demo.
- `metrics.json`: kích thước, thời gian, homography và điểm đã sắp xếp.

Chạy test:

```powershell
python -m unittest discover -s tests -v
```

Chi tiết thuật toán và cách đánh giá nằm trong `docs/phase-02-perspective-correction.md`.

## Phase 3 - Illumination Correction

Chạy demo so sánh Gamma, CLAHE, background estimation và combined:

```powershell
python -m defect_vision.illumination_demo
```

So sánh tất cả phương pháp trên ảnh thật:

```powershell
python -m defect_vision.illumination_cli `
  --input path\to\device.jpg `
  --method all `
  --output-dir outputs\illumination-device
```

Chạy riêng một phương pháp để tích hợp vào inference:

```powershell
python -m defect_vision.illumination_cli `
  --input path\to\device.jpg `
  --method background `
  --background-kernel 201 `
  --output-dir outputs\illumination-device
```

Output gồm từng ảnh đã xử lý, `comparison.png` và `metrics.json` chứa thống kê luminance cùng thời gian của mỗi phương pháp.

Chi tiết lựa chọn thuật toán, failure cases và cách đánh giá với YOLO nằm trong `docs/phase-03-illumination-correction.md`.

## Phase 7 - YOLO Baseline

Chạy pipeline mô phỏng không cần tải model:

```powershell
$env:PYTHONPATH="."
python -m defect_vision.yolo_baseline_cli --mock
```

Để chạy trọng số YOLO do TV2 bàn giao, cài dependency tùy chọn bằng
`python -m pip install -r requirements-yolo.txt`, sau đó truyền `--model` và
`--input`. Chi tiết nằm trong `docs/phase-07-yolo-baseline.md`.

## Phase 2 & Model-Guided Perspective Correction (Segmentation)

Mô hình Deep Learning RF-DETR segmentation (`models/weights.pt`) được huấn luyện chuyên dụng để phân đoạn chính xác thân/màn hình điện thoại ngay cả khi có nền phức tạp, tay cầm hoặc vỡ nứt màn hình nặng.

Cài đặt runtime segmentation:

```powershell
python -m pip install -r requirements-segmentation.txt
```

### Cách 1: Chạy Perspective CLI với Segmentation Model

```powershell
python -m defect_vision.perspective_cli `
  --input data/394k.jpeg `
  --model models/weights.pt `
  --output-dir outputs/perspective-phone
```

Output:
- `01_original.png`: Ảnh gốc đầu vào.
- `02_mask.png`: Binary mask điện thoại được dự đoán từ model.
- `03_mask_overlay.png`: Mask phủ màu xanh mạ trực quan trên thân máy.
- `04_selected_corners.png`: 4 góc [TL, TR, BR, BL] kèm đường viền tứ giác khớp chính xác các cạnh vật lý của điện thoại (đã tinh chỉnh triệt tiêu bo cong viền).
- `05_corrected.png`: Ảnh điện thoại sau khi nắn góc nhìn trực diện (rectified).
- `06_before_after.png`: Bảng so sánh trực quan trước và sau khi nắn thẳng.
- `metrics.json`: Tọa độ 4 góc, kích thước chuẩn hóa và ma trận biến đổi Homography.

### Cách 2: Chạy trực tiếp trong Python Code

```python
import cv2
from defect_vision import PhoneSegmenter

segmenter = PhoneSegmenter("models/weights.pt")
image = cv2.imread("data/394k.jpeg")

# Tự động phân đoạn, xác định 4 góc và nắn thẳng góc nhìn
result = segmenter.segment_and_correct(image)

print("Tọa độ 4 góc:", result.corners)
print("Kích thước sau nắn:", result.perspective_result.output_width, "x", result.perspective_result.output_height)
cv2.imwrite("phone_corrected.png", result.perspective_result.image)
```

## Preprocessing Pipeline trọn gói (End-to-End)

Chạy toàn bộ chuỗi tiền xử lý (Perspective với Segmentation, Illumination, Color Space, Before/After evaluation, YOLO) chỉ với một lệnh:

```powershell
python -m defect_vision.pipeline_cli `
  --input data/394k.jpeg `
  --output-dir outputs/pipeline-seg `
  --method clahe `
  --auto-perspective `
  --mock
```

- `--auto-perspective`: Tự động sử dụng `models/weights.pt` để phân đoạn lấy 4 góc và nắn thẳng góc nhìn trước khi chuyển sang các bước tăng cường chất lượng ảnh tiếp theo.
- Hoặc truyền tọa độ thủ công nếu muốn chỉ định: `--points "x1,y1;x2,y2;x3,y3;x4,y4"`.
Toàn bộ ảnh từng khâu (`01_original.png` -> `final_preprocessed.png`), bảng đối chiếu trước/sau (`05_before_after_board.png`), và báo cáo định lượng (`pipeline_report.json`) sẽ được xuất đầy đủ.
