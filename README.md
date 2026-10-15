# Industrial Defect Image Retrieval

Hệ thống phát hiện lỗi ngoại quan trên thiết bị điện tử bằng xử lý ảnh và AI.

## Kiến trúc

```mermaid
flowchart LR
    A[Flutter App] -->|multipart image| B[Spring Boot API]
    B -->|internal HTTP request| C[Python Image Service]
    C --> D[OpenCV Enhancement]
    D --> E[YOLO Detection]
    E --> C
    C -->|detections + timings| B
    B --> F[(Scan History)]
    B -->|JSON result| A
```

- `image-processing/`: xử lý ảnh, enhancement, YOLO inference và đo thời gian.
- `backend/`: API Spring Boot, validation, điều phối inference và lưu lịch sử.
- `app/`: Flutter UI, upload/camera, hiển thị bounding box và lịch sử quét.
- `contracts/`: hợp đồng dữ liệu dùng chung giữa ba thành phần.
- `docs/`: thiết kế hệ thống và tài liệu thực nghiệm.

## Trạng thái

Phase 1 đã xác định pipeline tổng thể, ranh giới trách nhiệm và hợp đồng kết quả phát hiện. Xem [tài liệu Phase 1](docs/phase-01-overall-pipeline.md).

Phase 2 đã cài đặt Perspective Correction trên Python/OpenCV, kèm CLI, ảnh before/after, timing và unit test. Xem [tài liệu Phase 2](docs/phase-02-perspective-correction.md).

Phase 3 đã cài đặt Illumination Correction với Gamma, CLAHE, background estimation và chế độ kết hợp. Xem [tài liệu Phase 3](docs/phase-03-illumination-correction.md).

Phase 4 đã cài đặt Color Space Transformation (BGR, RGB, Gray, HSV, LAB), trích xuất kênh, tính toán tương phản (Weber, Michelson, CNR) và sinh ảnh so sánh. Xem [tài liệu Phase 4](docs/phase-04-color-space.md).

Phase 5 đã cài đặt Data Augmentation cho thiết bị điện tử, đồng bộ tọa độ Bounding Box YOLO (Flip, Rotation, Brightness, Noise, Blur) và export nhãn YOLO. Xem [tài liệu Phase 5](docs/phase-05-image-augmentation.md).

Phase 6 đã cài đặt Before & After Comparison Suite với bộ chỉ số định lượng (CNR, Tenengrad, Laplacian Var, Entropy, Noise Amplification) và bảng so sánh trực quan. Xem [tài liệu Phase 6](docs/phase-06-before-after-comparison.md).

Phase 7 đã thiết lập YOLO baseline pipeline: adapter Ultralytics cho trọng số TV2, mock detector chạy được không cần model, postprocess bounding box, ảnh annotated và timing theo contract. Xem [tài liệu Phase 7](docs/phase-07-yolo-baseline.md).

Việc còn lại sau Phase 7 là nhận dataset/trọng số TV2 để benchmark accuracy, calibration và tích hợp inference thật vào backend/API.


