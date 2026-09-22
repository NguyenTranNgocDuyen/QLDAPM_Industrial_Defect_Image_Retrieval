# Spring Boot Backend

Phạm vi module:

- Cung cấp public endpoint `POST /api/detections` cho Flutter.
- Validate file upload và ánh xạ lỗi sang response ổn định.
- Gọi Python Image Service qua HTTP nội bộ.
- Lưu scan, detection result, metadata và lịch sử.
- Cung cấp ảnh kết quả và API lịch sử quét.

Backend không triển khai lại OpenCV hoặc YOLO. Nó điều phối pipeline và giữ public API không phụ thuộc công nghệ model.

Module sẽ được khởi tạo ở phase Backend/API.
