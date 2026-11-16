# Kiểm tra lỗi ngoại quan bàn phím (Keyboard Defect Detection)

> Xem tài liệu quyết định kiến trúc và triển khai chính thức tại [docs/KEYBOARD_RUNTIME.md](KEYBOARD_RUNTIME.md).

Feature này độc lập với phone-damage: worker chạy `python -m keyboard_vision.keyboard_api --port 8001`; worker phone vẫn chạy `python -m defect_vision.damage_api --port 8000`.

Backend gọi worker keyboard tại `KEYBOARD_SERVICE_URL` (mặc định `127.0.0.1:8001`) qua `POST /api/keyboard-inspections`. Ảnh phải là JPEG/PNG/WebP không quá 25 MB. API trả contract `contracts/keyboard-inspection-result.schema.json` và lưu lịch sử trong `keyboard_inspections`/`keyboard_defects`.

---

## 1. Quyết định Triển khai Kiến trúc (Architecture Decisions)

- **Cô lập dịch vụ:** Chạy worker Python riêng biệt tại cổng 8001, cách ly hoàn toàn tài nguyên và logic với worker điện thoại (cổng 8000).
- **Kiến trúc Hybrid 5 tầng:** Kết hợp Deep Learning (YOLO11n) nhận diện phím & hư hại bề mặt + OpenCV/Hungarian Matching phân tích cấu trúc lưới hình học + Crop OCR (EasyOCR) & Rule Engine kiểm tra vị trí ký tự.
- **Tiến trình mô hình:**
  - *Baseline hiện tại:* OpenCV Contour Baseline (`ContourKeyboardLocalizer`, `ContourKeyDetector`) phân tích lưới hình học suy ra `missing_key`, `shifted_key`, `tilted_key`.
  - *Mô hình Deep Learning Stage 1:* YOLO11n Key Detector đã hoàn thành huấn luyện (đạt **Recall 98.4%**, **mAP50 98.9%**, checkpoint tại `image-processing/models/keyboard_yolo11n_keys_v1.pt`).
  - *Mô hình Stage 2:* YOLO 3-class (`key_ok`, `key_damaged`, `key_missing`) kết hợp công cụ gán nhãn bán tự động `Keyboard Annotation Studio` (Port 5050).

---

## 2. Mục tiêu phát hiện lỗi & Phân loại Class (Defect Taxonomy)

Hệ thống đặt mục tiêu phát hiện toàn diện 4 nhóm vấn đề ngoại quan trên bàn phím:
1. **Lỗi hư hỏng phím (`damaged_keycap` / `defective_key`)**: Phím bị nứt, vỡ, trầy xước, mẻ góc, mờ/mòn ký tự.
2. **Mất phím / thiếu phím (`missing_key`)**: Vị trí keycap bị trống, lộ chân switch hoặc khung phím.
3. **Lệch & sai vị trí phím**:
   - *Lệch hình học (`shifted_key`, `tilted_key`)*: Keycap bị cắm lệch tâm lưới hoặc bị xoay nghiêng so với hàng phím.
   - *Sai vị trí ký tự (`wrong_keycap` / `misplaced_key`)*: Keycap bị lắp sai vị trí so với layout quy chuẩn (ví dụ phím Q đổi chỗ phím W).
4. **Nhận diện và xác thực Layout (`layout_validation`)**: Tự động nhận diện và kiểm tra tính toàn vẹn của layout (ANSI-104, ANSI-87 TKL, ISO-105, 60%, Laptop,...).

---

## 3. Chiến lược Phối hợp (Hybrid Architecture)

Thay vì bắt một mô hình Object Detection đơn lẻ phải học tất cả các khái niệm trừu tượng (như "khoảng trống mất phím" hay "sai vị trí layout"), hệ thống phân chia trách nhiệm:

| Thành phần | Cơ chế thực hiện | Trách nhiệm chính |
| :--- | :--- | :--- |
| **Object Detection Model (YOLO / Vision Model)** | Deep Learning trên bounding box | Detect sự hiện diện của **các phím (`key`)** và **các phím bị hư hại bề mặt (`damaged_key` / `defective_key`)**. |
| **Grid & Topology Engine** | Thuật toán hình học & Phân tích lưới (OpenCV) | Phân hàng/cột, đo khoảng cách bước lưới để suy ra **mất phím (`missing_key`)**, đo độ lệch tâm và góc xoay để suy ra **lệch phím (`shifted_key`, `tilted_key`)**. |
| **Layout & Template Matcher** | Luật cấu trúc & Template Matching (kèm OCR) | Đếm số lượng hàng/phím để nhận diện layout, đối chiếu vị trí ký tự để phát hiện **sai vị trí phím (`wrong_keycap`)**. |

---

## 4. Ranh giới Khẳng định & Bằng chứng (Evidence-Gated Decision)

- Baseline OpenCV hiện chỉ kết luận `missing_key`, `shifted_key`, `tilted_key` khi có vùng bàn phím và lưới phím đủ tin cậy (tối thiểu 8 phím và 2 hàng).
- Ảnh mờ/tối, không có bàn phím hoặc không đủ lưới trả `insufficient_evidence` / “Cần kiểm tra thủ công” kèm lý do giải thích chi tiết trong `summary.reasons`.
- **Tuyệt đối không kết luận** về switch cơ học, mạch điện, pin, Bluetooth, USB hoặc firmware.

---

## 5. Hướng dẫn Thay đổi Mô hình & Kiểm thử

Để thay model, cài đặt `KeyboardLocalizer` hoặc `KeyDetector` mới trong `keyboard_vision.pipeline`; giữ nguyên output contract. Đánh giá model bằng key-level precision/recall/F1, image-level precision/recall, false-positive rate và inference latency.

### Gọi API kiểm tra:
```bash
curl -F "image=@keyboard.jpg" http://localhost:8080/api/keyboard-inspections
```

Response chứa `status`, `keyboard.quality`, `defects`, URL ảnh `annotated` và `timing`; `hasDefect=false` chỉ có nghĩa không phát hiện lỗi ngoại quan trong ảnh.
