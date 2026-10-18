# Visual Defect Detection

Hệ thống phát hiện lỗi ngoại quan thiết bị điện tử. Repository gồm Flutter app,
Spring Boot backend, phần xử lý ảnh TV3, YOLO TV2 và CNN binary classifier TV1.

## Trạng thái TV1 — CNN Normal / Defective

TV1 đã có pipeline tái lập: CLAHE thật, chuẩn hoá mean/std từ train, augmentation
chỉ train, `StepLR`, calibration threshold validation, checkpoint tương thích ngược,
FastAPI local và test. Hướng dẫn đầy đủ cùng kết quả benchmark ở
[Phase 7](docs/phase-07-cnn-classification.md).

```bash
python -m pip install -r requirements.txt/tv1.txt
python scripts/audit_dataset.py
python -m model.evaluate --checkpoint outputs/model_gaussian/defect_classifier.pt --data-dir data --output-dir outputs/evaluation
python -m scripts.benchmark_inference --checkpoint outputs/model_gaussian/defect_classifier.pt --runs 30
```

Lưu ý: `requirements.txt` là thư mục đã tồn tại; dependency TV1 nằm tại
`requirements.txt/tv1.txt`. Audit SHA-256 hiện phát hiện một ảnh duplicate xuyên
train/test, do đó cần xử lý split trước khi công bố metric cuối.

## Thành phần

- `preprocessing/`, `model/`, `ui/local_api.py`: phần TV1.
- `image-processing/`: pipeline TV3.
- `backend/`: Spring Boot orchestration.
- `app/`: Flutter client.
- `contracts/`: hợp đồng kết quả detection dùng chung.

TV1 chỉ trả kết quả classifier toàn ảnh. Bounding box và nhãn lỗi chi tiết đợi
YOLO của TV2; các hiệu chỉnh perspective/illumination tiếp tục thuộc TV3.
