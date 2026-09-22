# Python Image Service

Phạm vi module:

- Xử lý ảnh bằng OpenCV.
- Perspective/illumination/color correction có thể bật tắt.
- Tích hợp model YOLO do TV2 bàn giao.
- Postprocess detection và đo thời gian từng bước.
- Cung cấp internal endpoint `POST /v1/infer` cho Spring Boot.

Input là một ảnh hợp lệ. Output phải tuân theo contract chung và không chứa logic lưu lịch sử hoặc logic giao diện.

Module sẽ được khởi tạo trong các phase xử lý ảnh tiếp theo.
