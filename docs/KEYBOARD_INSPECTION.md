# Kiểm tra lỗi ngoại quan bàn phím

Feature này độc lập với phone-damage: worker chạy `python -m keyboard_vision.keyboard_api --port 8001`; worker phone vẫn chạy `python -m defect_vision.damage_api --port 8000`.

Backend gọi worker keyboard tại `KEYBOARD_SERVICE_URL` (mặc định `127.0.0.1:8001`) qua `POST /api/keyboard-inspections`. Ảnh phải là JPEG/PNG/WebP không quá 25 MB. API trả contract `contracts/keyboard-inspection-result.schema.json` và lưu lịch sử trong `keyboard_inspections`/`keyboard_defects`.

Baseline OpenCV hiện chỉ kết luận `missing_key`, `shifted_key`, `tilted_key` khi có vùng bàn phím và lưới phím đủ tin cậy. Ảnh mờ/tối, không có bàn phím hoặc không đủ lưới trả `insufficient_evidence` / “Cần kiểm tra thủ công”. Không kết luận switch, điện, Bluetooth, USB hoặc firmware. `damaged_keycap` cần model bề mặt; `wrong_keycap` cần reference/template được gán nhãn nên chưa được baseline suy đoán.

Để thay model, cài đặt `KeyboardLocalizer` hoặc `KeyDetector` mới trong `keyboard_vision.pipeline`; giữ nguyên output contract. Đánh giá model bằng key-level precision/recall/F1, image-level precision/recall, false-positive rate và inference latency.

Ví dụ: `curl -F "image=@keyboard.jpg" http://localhost:8080/api/keyboard-inspections`. Response có `status`, `keyboard.quality`, `defects`, URL ảnh annotated và timing; `hasDefect=false` chỉ có nghĩa không phát hiện lỗi ngoại quan trong ảnh.
