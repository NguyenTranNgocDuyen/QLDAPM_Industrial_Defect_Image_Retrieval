# Flutter App

Phạm vi module:

- Chọn ảnh từ thư viện hoặc chụp từ camera.
- Gửi multipart image tới Spring Boot.
- Hiển thị trạng thái loading/error/result.
- Hiển thị ảnh kết quả và bounding box đúng theo `displayImage`.
- Hiển thị chi tiết lỗi và lịch sử quét.

Flutter chỉ giao tiếp với Spring Boot. App không chứa model và không gọi trực tiếp Python Image Service.

Module sẽ được khởi tạo ở phase App integration.
