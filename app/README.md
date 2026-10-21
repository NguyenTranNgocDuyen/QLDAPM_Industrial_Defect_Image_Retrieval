# Flutter App

Phạm vi module:

- Chọn ảnh từ thư viện hoặc chụp từ camera.
- Gửi multipart image tới Spring Boot.
- Hiển thị trạng thái loading/error/result.
- Hiển thị ảnh kết quả và bounding box đúng theo `displayImage`.
- Hiển thị chi tiết lỗi và lịch sử quét.

Flutter chỉ giao tiếp với Spring Boot. App không chứa model và không gọi trực tiếp Python Image Service.

## Camera trên điện thoại

- Màn hình chụp mở camera sau, xin quyền Camera khi chạy lần đầu và không thu âm.
- Sau mỗi lần chụp, màn hình xem lại hiển thị ảnh lớn và cho phép phóng to bằng hai ngón tay. Chọn **Giữ ảnh này** hoặc **Chụp lại** trước khi chuyển sang mặt còn thiếu.
- Hai ô **Mặt trước / Mặt sau** hiển thị ảnh thu nhỏ; chạm vào ô đã có ảnh để xem lại hoặc chụp lại riêng mặt đó.
- Nút **Gửi để phân tích** chỉ bật khi đã có đủ hai ảnh. Chụp đủ ảnh không tự chuyển sang phân tích; người dùng chủ động bấm gửi sau khi kiểm tra ảnh.
- Nút flash điều khiển đèn camera; camera được giải phóng khi ứng dụng xuống nền và mở lại khi quay về.
- Ảnh nằm trong bộ nhớ đệm của ứng dụng. Đường dẫn hai ảnh được chuyển tới `AnalysisScreen.capturedImages`; màn hình phân tích gửi ảnh tới backend, tự nhận vị trí và mức độ ước tính theo ảnh, không yêu cầu nhập dòng máy/kích thước hoặc xác nhận hình học thủ công.
- Phân tích/kết quả đã nối phone damage v3 thật qua Spring Boot: overlay PNG, A/L/W, mức độ ước tính và lý do cần kiểm tra. Không dùng mock grade/mm/loại lỗi. Các chỉ số chất lượng ảnh giả đã được bỏ khỏi màn hình camera.

Hướng dẫn chạy worker/backend/app, cấu hình API và giới hạn: [phone damage v3](../docs/PHONE_DAMAGE_V3.md).

## Android thật qua cáp USB

Cáp USB không tự chuyển tiếp HTTP tới máy tính. Cấu hình cổng trước khi chạy app:

```powershell
& D:/MySystemApplication/My_Android_std/SDK/platform-tools/adb.exe reverse tcp:8080 tcp:8080
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8080
```

Chạy các lệnh trong thư mục `app`; dừng lượt `flutter run` cũ trước khi chạy lại với địa chỉ mới. Sau khi rút/cắm cáp có thể phải chạy lại `adb reverse`. Chỉ cần chuyển tiếp BE 8080; BE gọi Python 8000 trên máy tính. `10.0.2.2` dành cho emulator. Nếu dùng IP Wi-Fi của máy tính, hai thiết bị phải truy cập được nhau qua cổng 8080.

App kiểm tra `/api/health` trong tối đa 8 giây trước khi upload, giữ thời gian xử lý ảnh riêng, và hiển thị lỗi kết nối/HTTP/định dạng cụ thể. Khi lỗi, terminal Flutter có log bắt đầu bằng `[DamageApi]` để đối chiếu với log BE/Python.

## Log Android lặp nhiều

**Các script dưới đây chỉ lọc cách hiển thị log, không sửa nguyên nhân phát sinh
log trong Android/driver.** Chạy `flutter run` trực tiếp vẫn thấy các dòng gốc.
Kiểm tra thiết bị ngày 20/10/2026: cả Impeller/Vulkan mặc định và phép thử
`--no-enable-impeller` đều tiếp tục phát hai dòng này khi camera hoạt động.
Chưa xác định được thay đổi app loại bỏ tận gốc log; đã khôi phục renderer mặc định.
Chi tiết và log thô: [chẩn đoán đồ họa Android](../docs/ANDROID_GRAPHICS_LOGS.md).

Trên thiết bị Mali/MediaTek đang thử, `gralloc4: Empty SMPTE 2094-40 data` và `mali_config: @get_buffer_dataspace_setting` lặp theo khung hình. Mẫu log được kiểm tra có 170/169 dòng tương ứng, không có Flutter exception/crash trong mẫu đó. Không coi chỉ hai thông báo này là bằng chứng upload hoặc model lỗi.

Để lọc ngay terminal chạy Flutter (khuyến nghị), dừng lượt Flutter cũ và chạy trong thư mục `app`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-app.ps1
```

Lệnh này vừa chạy app với API `http://127.0.0.1:8080`, vừa lọc console. Log Flutter/`[DamageApi]`, lỗi build và lỗi native khác vẫn hiển thị; log debug/info/warning native như CXCP, Looper, MIUI được lưu vào file thay vì làm trôi console. Hai thông báo GPU lặp nêu trên cũng được ẩn; việc ẩn không chứng minh lỗi đồ họa đã được sửa. Toàn bộ log chưa lọc lưu trong `app/build/logs/flutter-run-*.log`. Dùng `-ApiBaseUrl http://IP:8080` để đổi API, `-DeviceId ID` để chọn thiết bị, `-ShowNativeLogs` để xem thêm log native, `-ShowGraphicsNoise` để hiện lại log GPU.

Nếu muốn chỉ xem log của app đã chạy, mở terminal khác:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\watch-app-log.ps1
```

Giữ `flutter run` chạy ở terminal thứ nhất, chạy script ở terminal thứ hai. Script chỉ đọc log, không khởi chạy app. Nếu dừng Flutter bằng Ctrl+C rồi mới chạy script trong cùng terminal, app có thể đã dừng nên chưa có PID để đọc.

Script hiện chờ app khởi động thay vì báo lỗi đỏ, tự nối lại khi app restart/đổi PID hoặc thiết bị kết nối lại. Dùng chung bộ lọc gọn với `run-app.ps1`. Bản đầy đủ được lưu tại `app/build/logs`, không xóa log hệ thống hoặc đổi cấu hình driver. Dùng `-Snapshot` để đọc một lần, `-ShowNativeLogs`/`-ShowGraphicsNoise` để mở rộng nội dung, `-WaitSeconds 60` để giới hạn thời gian chờ app (mặc định chờ tới Ctrl+C). Nếu có nhiều thiết bị, thêm `-DeviceId <id>`.

Log `[DamageApi]` chỉ ghi bắt đầu/kết thúc/lỗi theo mỗi ảnh, không ghi theo frame. Khi app đứng ở “Sẵn sàng phân tích ảnh đã chụp”, cần bấm **Phân tích ảnh** để bắt đầu request.

Sau khi thêm thư viện camera hoặc sửa quyền Android, cần build/cài lại ứng dụng (hot reload không đủ):

```sh
flutter pub get
flutter run -d <device-id>
```

Khi ứng dụng hỏi quyền, chọn **Cho phép khi dùng ứng dụng**. Nếu đã từ chối, bật quyền Camera trong cài đặt ứng dụng rồi bấm **Thử lại**.

Kiểm thử: `flutter test`. Tích hợp dùng [camera của Flutter](https://pub.dev/packages/camera).
