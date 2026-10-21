# Phone damage v3: triển khai và kiểm tra

Cập nhật mới nhất 21/10/2026: mặc định **severity v6**: diện tích ≤ 2% là Nhẹ,
trên 2% đến hết 5% là Vừa; Nặng cần diện tích > 5% và bề rộng ≥ 8%.
Dải bề rộng Vừa bắt đầu 5%; skeleton chỉ tham khảo, pixel không phân cấp.
[Quy tắc hiện tại, kiểm thử và cách chạy](SEVERITY_AREA_WIDTH.md).
Các mô tả lấy mức cao nhất/ngưỡng 0.5%/1.5% bên dưới là lịch sử v1–v3,
đã được yêu cầu mới của người dùng thay thế.

Cập nhật 21/10/2026: mặc định **severity v3**, cho mức sơ bộ theo diện tích vùng
nhìn thấy khi hình học thiếu/cắt; nới cạnh phiên bản 2 và cho phép ước tính mục
tiêu tự chọn trong ảnh nhiều máy. [Chính sách mới, kiểm thử và giới hạn](LIMITED_OBSERVATION_ESTIMATES.md).
Thông tin v1/v2 bên dưới ghi lại các bước triển khai trước cập nhật này.

Cập nhật 20/10/2026: đã thêm nới có giới hạn từng cạnh cắt mask, audit góc,
kiểm thử lại hai capture qua backend thật và chặn worker trùng cổng Windows.
Chi tiết, ngưỡng, bằng chứng và lệnh chạy: [Cải tiến khung perspective](CORNER_EXPANSION.md).

Đã đọc README_VI.md, PROMPT_TICH_HOP_VA_DANH_GIA.md, example_integration.py, protocol và verification của gói. Đã nối checkpoint thật với Python worker, API Spring Boot và màn hình phân tích/kết quả Flutter. Không train thêm model.

Theo yêu cầu cập nhật của người dùng, mặc định trả **vị trí và mức độ ước tính theo ảnh**, không hỏi dòng điện thoại hoặc kích thước. Đây là phép đo trên khung ảnh đã nắn với tỷ lệ xấp xỉ từ bốn góc, không phải phép đo vật lý đã hiệu chỉnh. Cờ/giới hạn này được giữ trong JSON và UI; không giả vờ rằng người dùng đã xác nhận đầy đủ quan sát.

## Chạy

Mở ba terminal từ repository. Python mặc định trên máy hiện lỗi khi import NumPy; dùng môi trường hoạt động như `D:\XuLiAnh\.venv`. Không cài đè torch/torchvision. Nếu môi trường khác thiếu dependency, cài `image-processing/requirements-damage.txt` sau khi kiểm tra cặp torch/torchvision.

```powershell
# Terminal 1
cd image-processing
& D:\XuLiAnh\.venv\Scripts\python.exe -m defect_vision.damage_api --port 8000 --device cpu
```

Worker báo ready sau khi kiểm tra hash và nạp cả hai model. `GET http://127.0.0.1:8000/health` trả trạng thái và bộ đếm request/detector.

```powershell
# Terminal 2
docker compose up -d postgres
cd backend
mvn spring-boot:run
```

Nếu dùng dependencies đã tải trong lượt này: `mvn '-Dmaven.repo.local=target/m2' spring-boot:run`. Backend cổng 8080, worker cổng 8000. `PYTHON_IMAGE_SERVICE_URL` đổi địa chỉ worker; `PYTHON_IMAGE_READ_TIMEOUT_MS` mặc định 300000. Flyway V3 thêm JSON phân tích và cho phép `has_defect=null`.

```powershell
# Terminal 3
cd app
flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8080
```

`10.0.2.2` dành cho Android emulator. Điện thoại thật dùng IP LAN của máy backend. Android debug cho phép HTTP nội bộ; release/iOS cần HTTPS hoặc cấu hình mạng phát triển phù hợp.

Sau khi chụp/xem lại, bấm phân tích để tự nhận vị trí trên overlay và Nhẹ/Vừa/Nặng. Không có ô nhập tỷ lệ hoặc checkbox xác nhận hình học. Backend kiểm tra mask/bốn góc trước khi đưa ước tính; ảnh bị cắt, có dấu hiệu che khuất hoặc hình học không đạt giữ `needs_review` và không ép phân cấp. Mỗi mặt được báo riêng, không cộng diện tích giữa ảnh.

## Model và luồng xử lý

Thư mục mặc định là **phone_damage_v3_kit/phone_damage_v3/weights**, không phải phone_damage_v3_kit/weights:

```text
image-processing/phone_damage_v3_kit/phone_damage_v3/weights/
  model.pt
  phone_detect.pt
  protocol.json
```

Giữ nguyên package và import tương đối. `.pt` bị Git ignore, khi chuyển máy cần copy riêng. Biến cấu hình: `PHONE_DAMAGE_WEIGHTS`, `DAMAGE_DEVICE`, `DAMAGE_OUTPUT_DIR`, `DAMAGE_SEVERITY_CONFIG`; không có đường dẫn máy nguồn hardcode trong runtime.

- Damage SHA256: `a8dce48c3fd0c260e7bb2fa167e1f148eeffe46a9b01c68733bbd168a280ede3`.
- Detector SHA256: `b470b7e3537ec83d64a5024081cf052a92424d86486e3cf1dc70298697cb8ed8`.
- Kiểm tra cả hai hash và khóa kiến trúc detector; chỉ cho phép buffer `_kp_active_mask` bổ sung theo package. Thiếu/sai file làm startup thất bại, không chuyển sang Roboflow.
- Mỗi worker nạp một ROIDamageEngine với `load_phone_detector=False`, một PhoneSegmenter; khóa bảo vệ luồng dùng chung. Nhiều process sẽ dùng nhiều model/bộ nhớ.
- EXIF transpose → RGB uint8 gốc giữ độ phân giải → segmentation một lần. Chọn một instance có confidence cao nhất; nhiều máy thì yêu cầu kiểm tra mục tiêu. RF-DETR nhận RGB đúng; module tiền xử lý vẫn dùng BGR.
- `predict_with_body` nhận RGB gốc chưa warp/tăng sáng và segmentation nhị phân cùng tọa độ. Giữ threshold 0.4, patch 512, overlap 128, context 512, body margin 0, native; detector confidence 0.3. Không resize toàn ảnh xuống 512.
- Sau damage mới lấy bốn góc bằng code hiện có. Mặc định dùng kích thước đích suy từ các cạnh trong ảnh, không tự gán tỷ lệ thật của một dòng máy. API vẫn hỗ trợ tỷ lệ thật nếu một client chuyên dụng cung cấp. Cùng H và kích thước được áp lên RGB, damage mask, surface mask; mask dùng nearest-neighbor, lưu PNG 0/255. Mask gốc giữ nguyên.
- CLAHE/channels của pipeline hiện có chạy sau warp để xuất `preprocessed.png`, không thay đổi đầu vào damage. Overlay trên RGB nắn chưa tăng sáng để đối chiếu.
- Đã xóa đúng cache cũ `D:\tmp\cache\phone-segmentation-uiymg\1` sau khi xác nhận checkpoint mới. CLI tiền xử lý/phối cảnh cũng mặc định chọn checkpoint mới; luồng damage backend không dùng key/cache Roboflow.

## Hình học chưa kiểm chứng

Module độc lập `damage_severity.py`; cấu hình mặc định `severity.v2.json`, version `geometry-v2-image-estimate-unvalidated`, cờ `heuristic_unvalidated=true`. `severity.v1.json` giữ cho khả năng đọc/đối chiếu bản cũ. Ngưỡng A/L/W không đổi, không phải chuẩn grading và chưa được hiệu chỉnh bằng nhãn mức độ.

| Chỉ số | Định nghĩa | Vừa từ | Nặng từ |
|---|---|---:|---:|
| A | pixel D / pixel mặt quan sát, D = damage AND surface | 0.005 | 0.03 |
| L | skeleton dài nhất trong các vùng liên thông / đường chéo toàn mặt | 0.20 | 0.50 |
| W | max P90(2 × EDT tại skeleton) từng vùng / cạnh ngắn toàn mặt | 0.005 | 0.015 |

Mỗi chỉ số cho Nhẹ/Vừa/Nặng, lấy mức cao nhất và lưu chỉ số kích hoạt. L có thể vượt 1 với mạng phân nhánh; UI đổi tỷ lệ sang %. Lưu thêm tổng chiều dài skeleton. Số vùng liên thông không phải số vết vật lý. Skeleton Zhang–Suen trên bản sao có pad zero; graph đếm cạnh ngang/dọc=1, chéo=√2 một lần, bỏ cạnh chéo khi có cầu nối ngang/dọc để tránh cộng shortcut ở bậc thang. EDT có pad zero xử lý full/sát biên; một điểm skeleton dài 0. Không dilation/closing/lọc vùng nhỏ. Sai số raster đáng kể hơn với mask vài pixel.

Ngưỡng `candidate_pixels_original >= 200` chỉ là cờ báo ảnh gốc, tách khỏi severity. Dưới 200 vẫn giữ nguyên ứng viên, số đo và mức hình học tạm tính nếu có; thêm `below_alarm_threshold`, `needs_review` để UI không coi là kết luận chính thức.

Mặc định dùng `estimation_basis=image_geometry`, `needs_review=true` và `limitations=[aspect_approximated_from_image, visibility_not_verified]`; status vẫn là `estimated` và UI hiển thị mức kèm “Ước tính theo ảnh”. Không dùng việc thiếu tên dòng máy làm lý do chặn ước tính. Chỉ xét một mặt gần phẳng; unknown surface mang giả định này, các cạnh/cụm camera được khai báo rõ vẫn không phân cấp.

`surface_geometry.py` tính các kiểm tra từ mask thực: tỷ lệ body nằm trong tứ giác ≥0.98, lấp đầy tứ giác ≥0.75, lấp đầy convex hull ≥0.90, tỷ lệ hai cạnh đối diện ≤1.8, cạnh ngắn khung đích ≥32 pixel. Các ngưỡng chất lượng này cũng ở cấu hình v2 và chưa kiểm chứng. Chúng phát hiện một số dấu hiệu mask thiếu/lõm/góc xiên; không phải xác suất hoặc bằng chứng mọi che khuất đều đã được loại bỏ. Mask chạm biên nguồn, nhiều máy hoặc kiểm tra không đạt → không xuất mức, giữ lý do cần kiểm tra. Thiếu hình học thì L/W chuẩn hóa null; A/skeleton pixel chỉ mô tả phần mặt quan sát.

Vị trí được mô tả bằng các ô 3×3 trên ảnh sau nắn trong `severity.locations`, kèm số pixel ứng viên và tỷ phần ứng viên mỗi ô. Giữ toàn bộ ô có ứng viên; không coi số ô/vùng là số vết vật lý, không suy ra bộ phận camera/màn hình hoặc loại lỗi. Overlay vẫn giữ nguyên mask nguồn đã warp.

Mask rỗng và hình học đầy đủ → `no_detected_damage`, severity null, chỉ trong mặt quan sát. Không có phone/surface → `insufficient_evidence`. Lỗi mask/model/tính toán → `processing_error`, số đo null, `found/hasDefect=null`; không kết luận máy lành.

## API

Flutter chỉ gọi Spring Boot. Upload mặc định chưa xác nhận hình học:

```powershell
curl.exe -X POST http://localhost:8080/api/detections -F "image=@image-processing/data/123k.jpeg" -F "surface=front"
```

Upload mặc định trên đã có thể trả mức ước tính theo ảnh và vị trí, không cần trường bổ sung. `surfaceAspectRatio`/`fullSurfaceConfirmed` vẫn là tuỳ chọn API cho client có thông tin hình học thực, không xuất hiện trong form Flutter. Không tự gán tỷ lệ ví dụ cho ảnh thật. `deviceInfo` vẫn tuỳ chọn. `GET /api/detections/{scanId}` đọc JSON đã lưu; `GET /api/damage-assets/{artifactId}/{name}.png` proxy PNG. ID artifact worker có thể khác scanId database; dùng nguyên URL trong JSON.

Ví dụ JSON rút gọn (đã lược bớt trường):

```json
{
  "success": true,
  "hasDefect": true,
  "status": "estimated",
  "damage": {
    "status": "candidates",
    "candidate_pixels_original": 69974,
    "found": true,
    "threshold": 0.4,
    "alarm_pixels": 200,
    "inference_variant": "native",
    "detector_loaded_in_damage_engine": false,
    "observed_surface": "front"
  },
  "severity": {
    "status": "estimated",
    "estimated_severity": "severe",
    "needs_review": true,
    "heuristic_unvalidated": true,
    "config_version": "geometry-v2-image-estimate-unvalidated",
    "estimation_basis": "image_geometry",
    "limitations": ["aspect_approximated_from_image", "visibility_not_verified"],
    "scope": "observed_surface_only"
  }
}
```

JSON đầy đủ còn có source/display sizes, `assets`, `transformMatrix`, timings thật, A, chiều dài/bề rộng pixel, số vùng và reasons. Hợp đồng: `contracts/detection-result.schema.json`. Không trả numpy array, confidence hư hại giả, loại lỗi, mm hay grade A/B/C.

## Kiểm tra

- 95 kiểm thử Python đạt: dài mảnh tăng theo L dù A nhỏ; ngắn dày tăng theo W; mảng tăng theo A; rỗng/surface rỗng/một pixel/full/sát biên/nhiều vùng/vòng; graph; resize đồng dạng; EXIF/RGB; warp cùng H/kích thước; sai kích thước mask; dưới 200; lỗi model; request đồng thời; tái sử dụng model; HTTP/PNG; chế độ tự ước tính không có kích thước; ghi rõ giả định; vị trí không mất pixel; không tự phân cấp khi bị cắt/lõm/nhiều máy/cạnh cong.
- 17 kiểm thử Flutter đạt, gồm camera/xem lại/chụp lại hiện có, UI severity/lỗi/vị trí và không còn form nhập dòng máy/kích thước. Phân tích tĩnh mã mới sạch.
- Backend build thành công. Hai kiểm thử API dùng worker giao thức giả lập và một kiểm thử Java → HTTP worker với checkpoint thật đều đạt. Kiểm tra upload ảnh gốc, trả PNG và đúng một lần detector. Database repository được mock.
- `scripts/verify_damage_integration.py` chạy ba ảnh thực trong data và ảnh trắng qua HTTP: cùng instance, một lần khởi tạo engine/worker, bốn lần detector cho bốn request. Đối chiếu một ảnh với engine độc lập trên cùng RGB/body mask: mask bằng nhau chính xác. Báo cáo và ảnh tại `image-processing/outputs/damage-verification/`; JSON ghi phiên bản torch/torchvision thực tế.
- Với torch 2.13.0+cu126 / torchvision 0.28.0+cu126 chạy CPU: 123k/329k/394k có 69974 / 134522 / 74847 pixel ứng viên; khoảng 2.9–4.4 giây/ảnh, chưa tính nạp model. Đây là ví dụ tích hợp, không phải nhãn đúng/sai hay accuracy. Các ảnh giữ needs_review do chưa xác nhận hình học, 329k còn chạm biên. Ảnh trắng → phone_not_found, số đo null.
- Đã chạy lại bốn yêu cầu bằng môi trường dự án `D:\XuLiAnh\.venv` (torch 2.14.1+cpu / torchvision 0.29.1+cpu): smoke/parity cũng đạt, khoảng 2.8–3.6 giây/ảnh mẫu. Báo cáo verification hiện tại ghi lần chạy này; không suy rộng tính tương đương sang ảnh/môi trường khác.
- Cập nhật sau khi Docker chạy ngày 20/10/2026: PostgreSQL 17.11 healthy; Flyway V3 đã áp dụng thành công trên database hiện có. Kiểm thử Spring Boot context với `ddl-auto=validate` đạt. Toàn bộ lượt `mvn test` có 3 bài đạt và 1 bài model thật có điều kiện được skip do không đặt biến môi trường; model thật được chạy riêng qua luồng HTTP bên dưới.
- Đã chạy end-to-end **không mock**: client HTTP → Spring Boot cổng 8080 → worker cổng 8000/checkpoint thật → PostgreSQL → GET kết quả/lịch sử/PNG. Ba ảnh thực và ảnh trắng đều lưu/đọc lại JSON chính xác; 26 tài nguyên PNG tải được và có kích thước đúng tọa độ. Bốn request chạy đúng bốn lần detector. Ảnh trắng lưu `has_defect=NULL`, không thành máy lành. Kiểm tra SQL trực tiếp xác nhận `analysis_json`, `has_defect` nullable và bốn bản ghi có `device_info=integration-test-postgres-20261020`; bản ghi cũ được giữ.
- Script tái lập: `python scripts/verify_backend_postgres.py` khi cả ba service đang chạy. Script tạo bốn bản ghi test có đánh dấu và lưu báo cáo tại `outputs/backend-postgres-verification/verification.json`. Đồng thời kiểm tra mặt giả lập 1024×1024: một điểm → Nhẹ, đường mảnh 350 pixel → Vừa, đường mảnh 900 pixel → Nặng. Đây là kiểm tra thuật toán trên hình học biết trước, không phải mức độ của các ảnh điện thoại thật.
- Sau cập nhật v2 theo yêu cầu chỉ cần ảnh: 123k và 394k tự trả **Nặng — ước tính theo ảnh**, có vị trí 3×3 và overlay; 329k không phân cấp vì chạm biên và body nằm ngoài tứ giác; ảnh trắng vẫn insufficient_evidence. JSON mới được lưu/đọc lại chính xác qua PostgreSQL và 26 PNG khớp kích thước. Mask source/parity không thay đổi. Lượt backend cuối có đủ **4/4 bài đạt, không skip**, gồm context PostgreSQL và worker checkpoint thật.

```powershell
# Trong image-processing, với môi trường Python đã kích hoạt
python -m pytest -p no:cacheprovider tests --basetemp=outputs/pytest-local -q
python scripts/verify_damage_integration.py
# Trong backend
mvn -B -ntp '-Dmaven.repo.local=target/m2' '-Dtest=DamageApiIntegrationTests' test
$env:DAMAGE_REAL_PYTHON = 'D:/XuLiAnh/.venv/Scripts/python.exe'
mvn -B -ntp '-Dmaven.repo.local=target/m2' '-Dtest=RealDamageWorkerSmokeTests' test
# Trong app
flutter test
```

## Giới hạn

- Chưa có nhãn mức độ của con người nên không báo accuracy phân cấp. Các ngưỡng vẫn chưa kiểm chứng; model có thể nhận nhầm phản chiếu/nền hoặc bỏ sót vùng. Không suy ra loại lỗi, độ sâu, chức năng hoặc tình trạng toàn máy.
- Segmentation phone body không tự phân biệt từng mặt 3D. Chỉ dùng nó làm mask mặt quan sát khi xác nhận ảnh là một mặt gần phẳng; không coi một homography là phép nắn toàn bộ thiết bị 3D.
- PostgreSQL/Flyway V3 và lưu/đọc kết quả qua backend thật đã được kiểm tra sau khi Docker hoạt động. Chế độ v2 tự ước tính theo hình ảnh, không coi tỷ lệ xấp xỉ là hiệu chỉnh vật lý hay mặc định người dùng đã xác nhận đầy đủ bề mặt.
- Chưa kiểm thử end-to-end trên điện thoại vật lý/GPU. Giữ cùng môi trường khi so sánh mask; không đảm bảo bitwise equality giữa các bản torch/thiết bị.
- Worker HTTP là service nội bộ sau Spring Boot, tuần tự xử lý ảnh trong mỗi process. Giữ thư mục output trên ổ bền vững để xem lại lịch sử; chưa có dọn artifact tự động hoặc queue phân tán.
- Lịch sử/danh mục demo cũ của Flutter là luồng riêng chưa nối API trong phạm vi này. Màn hình kết quả phân tích mới đã bỏ mock grade/loại lỗi/mm.

## File thay đổi

- Python mới: `damage_api.py`, `damage_service.py`, `damage_severity.py`, `surface_geometry.py`, `severity.v1.json`, `severity.v2.json`, `requirements-damage.txt`, `scripts/verify_damage_integration.py`, `scripts/verify_backend_postgres.py`. Sửa `phone_segmenter.py`, `perspective.py`, `perspective_cli.py`, `pipeline_cli.py` để dùng local checkpoint/RGB đúng/kích thước đích chung.
- Backend: `PythonDamageClient.java`, `DamageAssetController.java`, `DetectionController.java`, `ScanService.java`, `DetectionResponseDto.java`, `ScanSummaryDto.java`, `ScanRecord.java`, `application.yml`, migration `V3__damage_analysis.sql`, schema JSON.
- Flutter: `damage_api.dart`, `analysis_screen.dart`, `result_screen.dart`, dependency HTTP, quyền Internet/debug HTTP. Giữ luồng camera/xem lại có sẵn.
- Tests: `test_damage_severity.py`, `test_damage_integration.py`, `DamageApiIntegrationTests.java`, `RealDamageWorkerSmokeTests.java`, `damage_result_test.dart`.
