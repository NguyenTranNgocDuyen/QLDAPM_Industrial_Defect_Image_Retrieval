# Python Image Processing

Phân cấp mặc định hiện tại: [severity v6, diện tích 2%/5% và bề rộng 5%/8%](../docs/SEVERITY_AREA_WIDTH.md).

Luồng phone damage v3 thật (worker, backend, Flutter, severity hình học chưa kiểm chứng): xem [hướng dẫn triển khai và kiểm thử](../docs/PHONE_DAMAGE_V3.md). Luồng này dùng checkpoint local trong `phone_damage_v3_kit/phone_damage_v3/weights`, dùng chung segmentation và chạy damage trên RGB gốc trước mọi warp/tăng sáng. Các ví dụ YOLO/Roboflow bên dưới là công cụ baseline cũ, không phải loader của v3.

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

### Hỗ trợ tải tự động Model khi Clone Repository

Do GitHub giới hạn kích thước file tải lên (< 100MB), file trọng số `weights.pt` (~127MB) không được commit trực tiếp vào git. Khi một thành viên mới clone source code về máy, hệ thống hỗ trợ **tự động tải model** qua Roboflow Inference:

#### Bước 1: Cấu hình API Key
Tạo file `.env` từ `.env.example`:
```powershell
cp .env.example .env
```
Điền Roboflow API Key của bạn vào `.env`:
```env
ROBOFLOW_API_KEY=your_roboflow_api_key_here
ROBOFLOW_PHONE_MODEL_ID=phone-segmentation-uiymg/1
```

#### Bước 2: Tải trước model bằng script (Khuyên dùng)
Chạy script tự động tải và cache model vào máy:
```powershell
python scripts/download_model.py
```
*(Hoặc truyền trực tiếp API key qua tham số: `python scripts/download_model.py --api-key <YOUR_KEY>`)*

Kiểm tra trạng thái sẵn sàng của model:
```powershell
python scripts/download_model.py --check
```

Nếu bạn có link tải trực tiếp file `weights.pt` (từ Google Drive, GitHub Release, v.v.):
```powershell
python scripts/download_model.py --url "https://your-server.com/weights.pt"
```

#### Tự động chạy ngầm (Zero-Configuration On-the-fly)
Nếu bạn đã cấu hình `ROBOFLOW_API_KEY` trong `.env`, bạn không cần chạy lệnh tải thủ công. Khi chạy bất kỳ lệnh nào có `--auto-perspective`, hệ thống sẽ tự động tải model từ Roboflow về cache máy tính trong lần chạy đầu tiên.

---

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

### Kiểm tra khung cắt từ mask đã lưu

Phần lấy góc giữ cách khớp cạnh trong dải 8 pixel làm bước đầu tiên. Nếu tứ giác
giữ được dưới 98% vùng điện thoại trong mask, thuật toán thử khớp lại với dải tìm
kiếm bằng 10% cạnh ngắn (tối thiểu 8 pixel). Các cạnh vốn làm mất không quá 1%
diện tích mask vẫn được giữ nguyên. Kết quả mới chỉ được nhận khi độ bao phủ tăng
ít nhất 0,5 điểm phần trăm, phần nền ngoài mask chiếm không quá 3% khung mới,
diện tích khung tăng không quá 20% và mỗi góc dịch không quá 20% cạnh ngắn.

So sánh cách cũ và cách mới trên cùng ảnh/mask, không cần tải hoặc chạy model:

```powershell
python scripts/compare_perspective.py --case 329k data/329k.jpeg outputs/test_seg/mask_329k.png
```

Có thể truyền nhiều `--case NAME IMAGE MASK`. Kết quả nằm trong
`outputs/perspective-audit/`: ảnh đối chiếu khung cắt, ảnh đã nắn theo từng cách
và `comparison.json`. Chỉ số coverage đo phần mask được giữ lại trong khung,
không phải độ chính xác model hay độ bao phủ thân máy theo nhãn chuẩn.
Nếu mask bỏ sót viền hoặc điện thoại vượt khỏi ảnh gốc, bước này không khôi phục
được phần thông tin bị thiếu.

Khi gọi Python, dùng `extract_corners_from_mask(..., adaptive_refinement=False)`
để tái lập cách khớp cạnh cũ. `refine_edges=False` vẫn tắt cả hai lượt khớp cạnh.

### Chạy pipeline

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
