# Spring Boot Backend - Industrial Defect Inspection

Module backend cung cấp REST API điều phối quy trình kiểm tra lỗi ngoại quan, lưu trữ lịch sử quét (scans), bounding box phát hiện (detections), danh mục lỗi (defect types) và kết quả truy vấn ảnh tương đồng (image retrieval).

Luồng upload hiện gọi worker phone damage v3 thật, lưu JSON hình học và proxy mask/overlay PNG. Xem [hướng dẫn chạy và kiểm thử](../docs/PHONE_DAMAGE_V3.md). `hasDefect` có thể null khi không đủ bằng chứng; không trả dữ liệu mô phỏng.

---

## 1. Kiến trúc Database & Entities

Hệ thống sử dụng **PostgreSQL 17** với các Entity chính:

1. **`ScanRecord` (`scans`)**:
   - Lưu trữ phiên quét ảnh: `id` (UUID), `originalFilename`, `sourceImageUrl`, `sourceWidth`, `sourceHeight`, `displayImageUrl`, `displayWidth`, `displayHeight`, `coordinateSpace` (`source` | `processed`).
   - Cờ lỗi & trạng thái: `hasDefect`, `success`, `status` (`COMPLETED`, `PENDING`, `FAILED`).
   - Chỉ số thời gian thực thi: `preprocessingMs`, `inferenceMs`, `postprocessingMs`, `totalMs`.
   - Quan hệ 1-N với `DefectDetection` và `ImageRetrievalRecord`.

2. **`DefectDetection` (`defect_detections`)**:
   - Tọa độ bounding box phát hiện trên ảnh: `x1`, `y1`, `x2`, `y2`.
   - Phân loại lỗi (`defectClass`) và độ tin cậy (`confidence` từ 0.0 đến 1.0).
   - Khóa ngoại `scan_id` liên kết tới bảng `scans`.

3. **`DefectType` (`defect_types`)**:
   - Danh mục định nghĩa các loại lỗi: `scratch` (Vết xước), `crack` (Vết nứt/vỡ), `dent` (Móp méo), `pinhole` (Lỗ kim), `contamination` (Dị vật), `solder_bridge` (Chập mối hàn), `missing_component` (Thiếu linh kiện).
   - Màu sắc bounding box (`boundingBoxColor`), mức độ nghiêm trọng (`severity`), trạng thái kích hoạt (`isActive`).

4. **`ImageRetrievalRecord` (`image_retrievals`)**:
   - Lưu trữ kết quả so khớp ảnh tương đồng từ thư viện mẫu: `referenceImageUrl`, `matchedDefectType`, `similarityScore`, `rankOrder`.

5. **`DefectGalleryItem` (`defect_gallery`)**:
   - Thư viện mẫu ảnh lỗi chuẩn dùng cho tra cứu/retrieval: `title`, `imageUrl`, `defectClass`, `componentType`, `embeddingVector`.

---

## 2. Hướng dẫn chạy nhanh cho Nhóm làm việc

### Bước 1: Khởi động Database với Docker Compose (PostgreSQL 17)
Từ thư mục gốc của project:
```bash
docker compose up -d
```
> Docker Compose sẽ khởi chạy container `industrial-defect-postgres` với image `postgres:17`, tự động mount volume `defect_postgres_data` để lưu trữ dữ liệu bền vững và nạp các script khởi tạo (`docker/postgres/init-scripts/`).

### Bước 2: Chạy Backend Spring Boot
Vào thư mục `backend/`:
```bash
# Biên dịch và chạy trực tiếp
mvn spring-boot:run

# Hoặc đóng gói JAR
mvn clean package -DskipTests
java -jar target/defect-inspection-backend-0.1.0-SNAPSHOT.jar
```

Database Migration được cấu hình tự động qua **Flyway** (`src/main/resources/db/migration/`), đảm bảo mọi thành viên trong team khi pull code mới về đều tự động cập nhật schema và seed data đồng bộ.

---

## 3. Danh sách REST Endpoints chính

| Phương thức | Endpoint | Mô tả |
|---|---|---|
| `GET` | `/api/health` | Kiểm tra tình trạng backend (Health check) |
| `POST` | `/api/detections` | Upload ảnh multipart (`image`) để nhận diện lỗi (chuẩn JSON Schema) |
| `GET` | `/api/detections/{scanId}` | Lấy chi tiết kết quả phát hiện theo `scanId` |
| `GET` | `/api/scans` | Lịch sử quét ảnh (phân trang `page`, `size`, lọc `hasDefect`) |
| `GET` | `/api/scans/{scanId}` | Xem chi tiết thông số và kết quả của 1 lượt scan |
| `GET` | `/api/defect-types` | Danh mục các loại lỗi đang được hỗ trợ |

Tất cả response JSON đều tuân thủ chặt chẽ theo hợp đồng `contracts/detection-result.schema.json`.
