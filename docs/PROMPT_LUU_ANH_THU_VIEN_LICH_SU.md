# Prompt giao AI: lưu ảnh, nhập từ thư viện và lịch sử quét thật

Bạn đang làm việc trong repository `D:\XuLiAnh\Industrial-Defect-Image-Retrieval`.
Hãy rà soát code hiện tại rồi triển khai hoàn chỉnh các chức năng dưới đây,
nối Flutter → Spring Boot → PostgreSQL/worker Python và kiểm thử thực tế.
Không chỉ đưa kế hoạch. Không train hoặc thay model. Giữ các thay đổi đang có;
không reset repository, xóa dữ liệu hay ghi đè những phần không liên quan.

## 1. Đọc trước khi sửa

Đọc AGENTS.md nếu có, các README liên quan và:

- `docs/PHONE_DAMAGE_V3.md`, `docs/CORNER_EXPANSION.md`.
- `image-processing/phone_damage_v3_kit/README_VI.md` và `PROMPT_TICH_HOP_VA_DANH_GIA.md`.
- Flutter: `app/lib/main.dart`; các file trong
  `app/lib/features/inspection/presentation/`: `capture_screen.dart`,
  `photo_review_screen.dart`, `analysis_screen.dart`, `result_screen.dart`,
  `history_screen.dart`; `data/damage_api.dart`, `models/capture_condition.dart`,
  `models/defect_item.dart`; `app/pubspec.yaml`, Android manifests và iOS Info.plist.
- Backend: `DetectionController`, `ScanController`, `DamageAssetController`,
  `ScanService`, `PythonDamageClient`, `ScanSummaryDto`, `DetectionResponseDto`,
  `ScanRecord`, `ScanRecordRepository`, `application.yml` và các migration Flyway.
- Python: `damage_api.py`, `damage_service.py`, `phone_segmenter.py`,
  `corner_expansion.py`, `surface_geometry.py`, `damage_severity.py` trong
  `image-processing/defect_vision/`; schema `contracts/detection-result.schema.json`.
- Test Flutter/Java/Python hiện có; `docker-compose.yml` và `.gitignore`.

Tự xác minh những thông tin hiện trạng dưới đây vì code có thể đã thay đổi.

## 2. Hiện trạng đã rà soát

- App vào `CaptureScreen`, chụp mặt trước/mặt sau, xem lại rồi chuyển sang
  `AnalysisScreen`. Nút phân tích gửi riêng từng ảnh và mở `ResultScreen`.
- Đường dẫn ảnh và thumbnail đang được giữ trong state màn hình; không coi đây
  là kho lưu ảnh lâu dài. Chưa có nút chọn ảnh thư viện hay xuất ảnh kết quả.
- `HistoryScreen` có dữ liệu mẫu REC-2026, tên/IMEI thiết bị giả, grade A/B/C,
  loại lỗi và mm. Màn hình này chưa nối API; `main.dart` đang mở thẳng camera.
  Phải kiểm tra và bổ sung đường điều hướng thật vào lịch sử.
- `DamageApi` hiện có analyze, kiểm tra kết nối, resolve URL tài nguyên và close;
  chưa có phương thức tải danh sách/chi tiết lịch sử hoặc tải byte ảnh để lưu.
- Backend đã tự lưu một `ScanRecord` và `analysis_json` cho mỗi ảnh phân tích,
  đồng thời lưu URL tài nguyên. Không cần POST lần nữa để "lưu kết quả".
- Các PNG nằm trong thư mục output worker; DB lưu metadata/JSON/URL, không lưu
  byte ảnh. PostgreSQL volume trong Docker không tự bảo vệ thư mục ảnh Python.
- Mặc định output là `image-processing/outputs/damage-api`, có thể đổi bằng
  `DAMAGE_OUTPUT_DIR`. Thư mục outputs đang bị Git ignore, không phải nơi tạm
  được phép tự xóa nếu nó đang chứa ảnh lịch sử.
- `assets.source` là PNG ảnh nguồn đã chuẩn hóa hướng EXIF, chưa warp; không
  phải bản sao byte JPEG nguyên gốc và không bảo đảm giữ toàn bộ EXIF gốc.
- `assets.display` là ảnh sau chỉnh hình học nếu có; `assets.overlay` có lớp
  phủ ứng viên. Các mask và `assets.corners` là tài nguyên phục vụ kiểm tra.
- UUID `scanId` của DB có thể khác UUID artifact trong URL. Luôn dùng URL trả
  về, không tự ghép đường dẫn ảnh từ scanId.

## 3. Phạm vi và hành vi mặc định

Hoàn thành ba chức năng riêng biệt:

1. **Lịch sử tự động:** kết quả đã được backend lưu phải xem lại được trong app,
   kể cả sau khi đóng/mở app, nếu server và kho ảnh còn hoạt động.
2. **Lưu ảnh vào điện thoại:** người dùng chủ động xuất ảnh nguồn hoặc overlay
   vào thư viện ảnh. Đây không phải thao tác tạo thêm scan hoặc chạy lại model.
3. **Nhập ảnh thư viện:** chọn ảnh có sẵn, xem lại và gửi vào cùng luồng phân tích
   hiện tại, giữ độ phân giải gốc mà ứng dụng nhận được từ bộ chọn ảnh.

Bản đầu dùng **một ảnh phân tích = một bản ghi lịch sử**, đúng mô hình BE hiện có.
Hai ảnh mặt trước/mặt sau hiện là hai scan riêng. Không tự ghép thành một phiên
theo thời gian gần nhau hoặc IMEI demo. Không cần tạo mô hình phiên kiểm định,
đăng nhập, đồng bộ nhiều thiết bị, PDF hay chức năng xóa lịch sử trong phạm vi này.
Không yêu cầu kho offline đầy đủ; khi mất mạng phải thông báo đúng trạng thái.

## 4. Chọn ảnh từ thư viện

- Bổ sung nút "Chọn từ thư viện" dễ thấy. Camera không mở được hoặc bị từ chối
  quyền vẫn phải cho phép chọn ảnh; không khóa nút này theo `_cameraReady`.
- Cho phép chọn ảnh cho ô mặt trước hoặc mặt sau trong luồng hiện tại. Tái sử
  dụng màn hình xem lại, đổi nhãn "Chụp lại" thành "Chọn lại" khi nguồn là thư viện.
  Có thể kết hợp một ảnh camera với một ảnh thư viện; giữ quy tắc đủ hai ảnh của
  luồng đang có. Không tự suy ra mặt trước/sau từ tên file hoặc nội dung model.
- Nếu hỗ trợ thêm phân tích một ảnh độc lập, phải có luồng riêng rõ ràng; không
  âm thầm thay quy tắc hai ảnh của luồng camera. Đây là mở rộng tùy chọn.
- Ưu tiên plugin chính thức `image_picker`; kiểm tra SDK/minSDK và chọn phiên
  bản tương thích thực tế, không nâng hàng loạt dependency hoặc Flutter SDK.
  Dùng picker hệ thống, hỗ trợ hủy chọn và khôi phục `retrieveLostData()` trên
  Android khi activity bị hệ thống hủy; khôi phục đúng ô ảnh đang chọn và đưa
  về xem lại, không tự upload khi khôi phục.
- Khi mở picker, lịch sử hoặc màn hình khác, quản lý camera qua cơ chế tuần tự
  hiện có: không để camera mở lại trên màn hình bị che, không mở hai controller,
  không setState sau dispose, chỉ mở lại khi thực sự về màn hình chụp.
- Không đặt maxWidth/maxHeight hoặc imageQuality để nén/resize ảnh gửi đi.
  Thumbnail có thể giảm kích thước giải mã riêng; tuyệt đối không upload thumbnail.
  Không crop/warp/CLAHE ảnh trước khi gửi BE; chuẩn hóa EXIF vẫn ở Python.
- Tái sử dụng lớp đầu vào chung cho camera/thư viện. Dùng XFile/bytes hoặc bản
  sao trong vùng riêng app khi cần; không giả định mọi URI đều là file path.
  Nếu giữ nháp qua lần khởi động app, sao chép vào vùng lưu bền của app cùng
  metadata; đừng chỉ lưu đường dẫn cache hoặc quyền URI tạm.
- Kiểm tra dung lượng theo giới hạn thực tế BE/worker (hiện 25 MB/ảnh), kiểu ảnh
  và khả năng decode. Ưu tiên JPEG/PNG; với HEIC/WebP không được backend hỗ trợ,
  báo rõ hoặc bổ sung chuyển đổi có kiểm chứng, không đổi đuôi file để giả JPEG.
- Sửa upload đang luôn gán `capture.jpg`: giữ tên/MIME phù hợp nội dung đầu vào.
  Không đổi byte chỉ để khớp đuôi. Mọi nguồn vẫn POST tới BE, không gọi Python
  trực tiếp từ điện thoại. Hủy picker không tạo request hoặc làm mất ảnh đã giữ.

Tài liệu chính thức cần đối chiếu:
[image_picker](https://pub.dev/packages/image_picker),
[Android Photo Picker](https://developer.android.com/training/data-storage/shared/photo-picker).

## 5. Lưu ảnh đã kiểm tra vào thư viện điện thoại

- Thêm nút "Lưu ảnh" cho từng mặt trong `ResultScreen` và màn hình chi tiết lịch sử.
  Cho chọn "Ảnh nguồn" (`assets.source`) hoặc "Ảnh có vùng đánh dấu"
  (`assets.overlay`). Nếu loại ảnh không tồn tại thì ẩn/khóa đúng lựa chọn và
  giải thích; không lưu loại khác rồi báo đã lưu loại người dùng chọn.
- Tải bytes từ URL asset qua BE, dùng cùng `API_BASE_URL` và cơ chế resolve URL.
  Giữ PNG, đúng kích thước, không chụp screenshot widget và không tự vẽ lại mask.
  Không dùng `displayImage.url` để suy đoán ảnh nguồn vì URL đó có thể là overlay.
- Android: dùng thư viện tương thích hoặc platform channel với MediaStore theo
  phiên bản hệ điều hành; không ghi trực tiếp đường dẫn hardcode `/sdcard`.
  Chỉ xin quyền thực sự cần ở thời điểm lưu. Không thêm quyền quản lý toàn bộ
  bộ nhớ chỉ để chọn/lưu vài ảnh. iOS dùng cơ chế Photos/add permission phù hợp;
  cập nhật mô tả quyền tiếng Việt và báo rõ nền tảng nào đã được kiểm thử.
- Có trạng thái đang lưu, chống bấm lặp khi thao tác chưa xong. Tên ảnh chứa
  scanId, nhãn mặt và loại ảnh; thông báo "Đã lưu vào thư viện ảnh" chỉ sau khi
  thao tác ghi hoàn thành. Cache tạm trong app không được coi là lưu vào thư viện.
- Từ chối quyền, tải lỗi, thiếu tài nguyên, hết dung lượng hoặc lỗi ghi phải có
  thông báo và thử lại. Không làm mất kết quả phân tích đang xem khi lưu thất bại.
- Chỉ lưu khi người dùng yêu cầu; không tự đưa toàn bộ ảnh kiểm tra vào thư viện.
  Lưu ảnh, mở lịch sử và xem chi tiết tuyệt đối không POST phân tích lại.

Tài liệu nền tảng:
[Android shared media/MediaStore](https://developer.android.com/training/data-storage/shared/media).
Nếu chọn plugin xuất ảnh, kiểm tra tài liệu và bảo trì/tương thích trước khi thêm.

## 6. Lịch sử quét bằng dữ liệu thật

API hiện có cần tái sử dụng:

```http
GET /api/scans?page=0&size=20&sortBy=createdAt&sortDir=desc
GET /api/scans/{scanId}
GET /api/detections/{scanId}
GET /api/damage-assets/{artifactId}/{filename}.png
```

- Thay dữ liệu mẫu của `HistoryScreen` bằng danh sách phân trang từ BE. Parser
  phải xử lý cấu trúc Page của Spring thực tế: `content`, `number`, `size`,
  `last`, `totalElements` và các trường đang trả về; không coi response là List.
- Thêm nút mở lịch sử từ màn hình chụp/kết quả. Khi đi từ lịch sử sang chi tiết,
  dùng GET scanId và tái sử dụng phần trình bày kết quả; không gọi model lại.
- Có tải trang đầu, danh sách rỗng, kéo làm mới, tải trang tiếp, lỗi/thử lại và
  thumbnail tải thất bại. Chống request tải trang lặp, trùng scanId, kết quả
  request cũ ghi đè lần refresh mới và pagination lệch khi vừa có scan mới.
- Mỗi dòng hiển thị thumbnail, thời gian thật quy đổi theo múi giờ thiết bị,
  tên file/scanId ngắn, nhãn mặt nếu có, trạng thái và mức độ ước tính nếu có.
  Không dùng tên iPhone/IMEI demo hay tự tạo metadata khi backend chưa có.
- `ScanSummaryDto` hiện chưa có severity/surface/needsReview. Nếu UI cần các
  trường này, mở rộng DTO/service và contract có kiểm thử; lấy từ dữ liệu đã
  lưu (`damage.observed_surface`, `severity.estimated_severity`, `needs_review`),
  không suy ngược mức độ từ `hasDefect` hoặc màu thumbnail. Giữ tương thích
  bản ghi cũ, dùng null/unknown khi không có dữ liệu.
- `detections` của pipeline mask hiện có thể rỗng dù có ứng viên; `detectionCount`
  bằng 0 không chứng minh ảnh không hư hại. Không hiển thị "0 lỗi" theo trường
  này, cũng không đổi số vùng liên thông thành số vết vật lý.
- Loại bỏ grade A/B/C, mm, loại xước/nứt/móp và nút PDF giả trong luồng lịch sử
  thật. Bộ lọc/tìm kiếm mẫu phải được gỡ hoặc nối API thật; không lọc riêng trang
  hiện tại rồi tạo cảm giác đang tìm toàn bộ lịch sử.
- Chi tiết hiển thị ảnh nguồn/ảnh đã nắn/overlay khi có, cho zoom, các số A/L/W,
  vị trí, lý do, "Mức độ hư hại ước tính" và lưu ảnh. Khi dữ liệu thiếu hiển thị
  rõ; bản ghi cũ không có analysis_json không được biến thành máy lành.
- Trạng thái `estimated` vẫn có thể `needs_review=true` vì hình học xấp xỉ.
  `no_detected_damage` chỉ nói chưa phát hiện ứng viên trên mặt quan sát.
  `insufficient_evidence`, `needs_review`, lỗi kết nối và lỗi ảnh phải tách biệt.
- Đóng/mở app phải tải lại lịch sử từ BE, không phụ thuộc map results ở màn hình
  trước. Mất mạng hiển thị lỗi kết nối, không hiển thị "Chưa có lịch sử" giả.
  Nếu có cache metadata thì ghi rõ dữ liệu lưu trước đó; cache không bắt buộc.

## 7. Độ bền dữ liệu và tương thích backend

- Xác minh đường dẫn artifact ổn định sau restart worker/BE, không phụ thuộc
  thư mục làm việc ngẫu nhiên. Cấu hình `DAMAGE_OUTPUT_DIR` tới kho lưu bền,
  viết hướng dẫn backup/restore cùng database. Nếu đưa worker vào Docker thì
  mount volume ảnh riêng; không khẳng định volume PostgreSQL đã chứa các PNG.
- Giữ kho hiện có và URL cũ hoạt động. Nếu đổi đường dẫn, sao chép/migrate có
  kiểm tra thay vì chuyển thẳng sang thư mục trống; không xóa outputs để dọn test.
- Asset mất trả 404/thông báo ảnh không còn, worker tắt trả lỗi dịch vụ phù hợp,
  vẫn cho biết metadata lịch sử nếu BE/DB còn đọc được. Không tự suy luận lại để
  lấp ảnh mất. Rà soát proxy asset hiện tại để tránh trả lỗi không rõ nghĩa.
- Hạn chế size trang/sort hợp lệ nếu chỉnh API. Mọi đổi schema DB phải thêm
  Flyway migration tiếp theo sau khi kiểm tra các migration đang tồn tại, không
  sửa migration cũ hoặc dùng ddl-auto để thay cho migration có chủ đích.
- POST đã lưu kết quả; không tạo thêm endpoint save/upload lặp nếu chỉ cần xem
  lại hoặc xuất ảnh. Vô hiệu hóa gửi lặp khi request đang chạy. Khi timeout sau
  upload có thể server đã lưu; không khẳng định chắc chắn chưa có bản ghi.
- Bản đầu không có đăng nhập: không gọi danh sách chung của server là "lịch sử
  riêng của tài khoản". Nếu cần quyền sở hữu thì đó là phạm vi bổ sung riêng.

## 8. Ràng buộc giữ nguyên pipeline model

- ROIDamageEngine và detector chỉ nạp một lần/worker; khởi tạo
  `ROIDamageEngine(..., load_phone_detector=False)` rồi dùng lại segmentation
  qua `engine.predict_with_body(rgb_original, phone_mask_original)` như code.
  Không nạp/chạy detector thứ hai, không dùng YOLO/torch.jit.load cho model.pt.
- RGB gốc đúng EXIF và mask nhị phân cùng tọa độ; không resize ảnh upload xuống
  512, không đưa ảnh warp vào checkpoint. Giữ protocol threshold 0.4 và các
  tham số hiện tại; ngưỡng báo ảnh 200 pixel tách khỏi severity.
- Giữ cải tiến nới cạnh có kiểm soát, cùng H/kích thước cho ảnh và mask,
  nearest-neighbor cho mask; không dilation để tăng vùng hư hại.
- Nhẹ/Vừa/Nặng là heuristic chưa kiểm chứng. Không báo accuracy severity,
  suy ra loại lỗi/độ sâu/chức năng hoặc tình trạng toàn thiết bị.
- Không reset cấu hình mạng: dùng `API_BASE_URL`. Android thật đang kiểm thử
  qua USB reverse, API app `http://127.0.0.1:8080`, BE 8080, worker 8000,
  PostgreSQL Docker 5433. Chỉ một worker cùng địa chỉ/cổng trên Windows.

## 9. Kiểm thử bắt buộc và tiêu chí nghiệm thu

Viết test có ý nghĩa cho hành vi mới, tái sử dụng test sẵn có. Kiểm tra:

1. Chọn ảnh JPEG/PNG đúng ô mặt; hủy chọn không đổi ảnh cũ; chọn lại; ghép camera
   và thư viện; lỗi quyền/đọc file/ảnh quá lớn/không hỗ trợ; ảnh EXIF xoay.
2. Android background/resume/picker activity bị hủy: khôi phục đúng ảnh/ô, không
   mở camera trùng, không tự upload, không lỗi setState/dispose.
3. Ảnh gửi giữ kích thước/bytes nhận từ picker, không phải thumbnail; upload đúng
   filename/MIME. Backend nhận ảnh vẫn chạy đúng một detector cho một request.
4. Lưu ảnh nguồn và overlay: bytes/kích thước đúng asset, file mở được trong
   thư viện điện thoại thật; hủy/từ chối quyền/tải lỗi/ghi lỗi không báo thành công.
5. Chụp/chọn → phân tích → có scanId → lịch sử → chi tiết: dữ liệu khớp kết quả
   đã lưu. Thoát/mở app, restart BE/worker cùng kho ảnh vẫn xem được ảnh cũ.
6. Phân trang nhiều hơn một trang, refresh, chống trùng, lịch sử rỗng thật,
   mất mạng, HTTP lỗi, JSON lỗi, bản ghi legacy, asset 404 và worker tắt.
7. Mở danh sách/chi tiết và lưu ảnh không tăng bộ đếm detector/request phân tích.
   Không có POST mới hay bản ghi scan mới chỉ vì xem hoặc xuất ảnh.
8. Không có dữ liệu REC/demo/grade giả trong lịch sử; null không thành số 0 hoặc
   Nhẹ; không diễn giải detectionCount=0 là máy lành; vẫn thể hiện giới hạn severity.

Chạy flutter analyze/test, test Java phù hợp nếu đổi BE, và các kiểm thử Python
liên quan nếu chạm pipeline. Có ít nhất một lượt BE/DB/worker thật không mock.
Kiểm thử plugin native trên Android thật; nếu không truy cập thiết bị thì báo
đúng phần chưa kiểm thử, không nhận unit test là bằng chứng lưu ảnh native thành công.

Môi trường đã hoạt động cần kiểm tra lại trước khi chạy:

```powershell
# image-processing, Python của dự án
& D:\XuLiAnh\.venv\Scripts\python.exe -m pytest tests -p no:cacheprovider --basetemp outputs/pytest-gallery-history -q
# backend
mvn -B -ntp '-Dmaven.repo.local=target/m2' test
# app
flutter analyze
flutter test
```

Tách API/persistence/gallery service khỏi widget để test và quản lý lỗi rõ ràng.
Giữ phong cách UI hiện có, dùng tiếng Việt dễ hiểu. Chỉ cài dependency cần thiết.
Không cần thêm tính năng ngoài phạm vi hoặc yêu cầu người dùng nhập dòng máy/kích thước.

Khi hoàn tất, báo file thay đổi, migration/dependency, lệnh chạy, kết quả test,
luồng thao tác từng chức năng, nơi lưu ảnh và giới hạn còn lại. Nếu thiếu công cụ
hoặc thiết bị thì ghi chính xác phần bị chặn; không dùng mock để tuyên bố đã
hoàn thành kiểm thử thực tế. Hoàn thành phần có thể thực hiện trước khi kết thúc.
