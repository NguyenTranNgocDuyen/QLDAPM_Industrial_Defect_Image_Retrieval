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
