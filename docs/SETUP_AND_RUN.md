# Cài đặt và chạy demo

## Điều kiện cần

- Git.
- Python 3.13 (môi trường model đã kiểm tra là 3.13.5).
- Java 21 và Maven tương thích với Spring Boot.
- Flutter SDK cùng Android SDK/thiết bị Android nếu demo mobile.
- Docker Desktop để chạy PostgreSQL.

Không dùng Java 24 hoặc Python 3.14 làm môi trường demo chính trước khi đã kiểm
tra lại toàn bộ model và test. Chúng có thể hoạt động một phần nhưng chưa phải cấu
hình được project xác nhận.

## 1. Chuẩn bị model

Damage worker yêu cầu ba file cục bộ tại:

```text
image-processing/phone_damage_v3_kit/phone_damage_v3/weights/
  model.pt
  phone_detect.pt
  protocol.json
```

Hai checkpoint `.pt` không được commit. Thành viên bàn giao model phải cung cấp
chúng qua kho nội bộ/Drive/Release kèm SHA-256. Trước khi chạy, đối chiếu hash
với `model_sha256` và `phone_model_sha256` trong `protocol.json`.

## 2. Python worker

```powershell
cd image-processing
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-damage.txt
python -m pip install -r requirements-dev.txt
New-Item -ItemType Directory -Force outputs | Out-Null
python -m pytest tests -p no:cacheprovider --basetemp outputs/pytest-local -q
python -m defect_vision.damage_api --host 127.0.0.1 --port 8000
```

### TV1 offline preprocessing and A/B artifacts

From repository root (these commands do not alter v3 model input):

```powershell
$env:PYTHONPATH = '.;image-processing'
python -m pip install -r image-processing/requirements-dev.txt
python -m preprocessing.experiment image-processing/data/123k.jpeg --output-dir outputs/preprocessing-experiment
python -m defect_vision.preprocess_benchmark image-processing/data/123k.jpeg --output-dir outputs/preprocess-benchmark
python image-processing/scripts/smoke_tv1_decode.py
python image-processing/scripts/validate_manifest.py path/to/manifest.csv
```

The experiment emits resize/filter/enhancement/histogram/comparison artifacts; the benchmark emits JSON/CSV with config hash and latency. They are offline only: phone v3 receives raw EXIF-upright RGB at source resolution. Health checks remain `http://127.0.0.1:8000/health` (worker) and `http://127.0.0.1:8080/api/health` (backend). YOLO/mock is baseline-only, and this project has no separate CNN normal/defective classifier.

Không cài lại Torch/Torchvision một cách mù quáng. Hãy chọn cặp CPU/CUDA tương
thích với máy trước, rồi cài các dependency còn lại. Worker phải trả `status=ready`
tại `http://127.0.0.1:8000/health` trước khi chạy backend.

## 3. Database

Tại root repository:

```powershell
Copy-Item .env.example .env
docker compose up -d
docker compose ps
```

PostgreSQL mặc định dùng cổng `5433`. Không commit `.env` hay password thật.

## 4. Spring Boot

Mở terminal mới:

```powershell
cd backend
$env:PYTHON_IMAGE_SERVICE_URL = 'http://127.0.0.1:8000'
mvn test
mvn spring-boot:run
```

Kiểm tra `http://127.0.0.1:8080/api/health`. Backend phải trả `status=UP` trước
khi Flutter upload ảnh. Nếu thiếu Maven, cài Maven hoặc bổ sung Maven Wrapper
trong một thay đổi riêng; không sao chép `target/m2` từ máy khác để thay thế.

## 5. Flutter

Mở terminal mới:

```powershell
cd app
flutter pub get
flutter analyze
flutter test
```

### Android emulator

```powershell
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8080
```

### Android thật qua USB

```powershell
adb reverse tcp:8080 tcp:8080
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8080
```

### Android thật qua Wi-Fi

Dùng IP LAN của máy chạy backend, ví dụ `http://192.168.x.x:8080`; điện thoại và
máy tính phải cùng mạng, đồng thời firewall phải cho phép cổng 8080.

## Checklist demo tối thiểu

1. Docker PostgreSQL hoạt động.
2. Python `/health` trả `ready`.
3. Backend `/api/health` trả `UP`.
4. App chọn/chụp ảnh và gửi được cả mặt trước hoặc mặt sau.
5. Kết quả hiển thị source/overlay, `needs_review` và lý do nếu có.
6. Ảnh source/overlay tải lại được từ history.
7. Thử ít nhất một ảnh không có điện thoại và một ảnh có vùng ứng viên.

## Khi có lỗi

| Triệu chứng | Kiểm tra đầu tiên |
|---|---|
| App không gọi được backend | API base URL, `adb reverse`, Wi-Fi/firewall, `/api/health` |
| Backend lỗi gọi worker | worker đang chạy, `PYTHON_IMAGE_SERVICE_URL`, hash checkpoint |
| Worker không khởi động | Python/Torch version, ba file weights, hash protocol |
| Không thấy ảnh overlay | endpoint `/api/damage-assets/...`, backend log, scan history |
| Kết quả không đủ bằng chứng | ảnh bị che/cắt, nhiều điện thoại, điện thoại quá nhỏ hoặc model không tìm thấy máy |
