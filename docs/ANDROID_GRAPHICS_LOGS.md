# Chẩn đoán log đồ họa Android — 20/10/2026

## Kết luận hiện tại

`run-app.ps1` và `watch-app-log.ps1` lọc console và lưu log đầy đủ trước khi lọc.
Chúng không sửa driver hoặc loại bỏ nguyên nhân sinh log. Chạy `flutter run`
trực tiếp vẫn nhận log gốc. Chưa có bản sửa tận gốc được xác minh cho hai dòng:

```text
I/mali_config: @get_buffer_dataspace_setting: update dataspace from GE (...)
E/gralloc4: Empty SMPTE 2094-40 data
```

API_BASE_URL chỉ cấu hình nơi gửi HTTP trong Dart, không cấu hình camera hay
metadata đồ họa. Hai dòng trên tự xuất hiện khi mở màn hình camera, chưa gửi ảnh.
Không dùng riêng chúng để kết luận upload/model lỗi, cũng không khẳng định mọi
lỗi native đều vô hại. Nếu có preview đen, treo, ảnh sai màu hoặc crash, cần
đối chiếu thêm lỗi camera, Flutter/AndroidRuntime và hành vi thực tế.

## Phép thử đã chạy trên thiết bị thật

- Redmi M2103K19G/camellian, Android 13, Mali/MediaTek, kết nối USB.
- Flutter 3.44.1 / Dart 3.12.1; camera 0.12.1;
  camera_android_camerax 0.7.5+1. Giữ cùng code và thư viện camera giữa hai lượt.
- Lượt mặc định PID 24943: log khởi động xác nhận Impeller/Vulkan.
- Lượt `--no-enable-impeller` PID 25851: log xác nhận opt-out Impeller;
  dumpsys media.camera xác nhận camera 0 đang được chính app sử dụng.
- Cả hai lượt vẫn lặp gralloc4/mali_config. Trong cửa sổ 10 giây cuối của
  snapshot tương ứng: mặc định 125/125 dòng, tắt Impeller 251/249 dòng.
  Đây là đếm log, không phải FPS hoặc benchmark hiệu năng; không suy ra đổi
  renderer làm nhanh/chậm hay ổn định hơn từ các số này.
- Điện thoại Awake trong phép thử. Không thay model, API backend hoặc giảm
  độ phân giải ảnh để làm biến mất log. Không đổi mức log hệ thống.
- Sau phép thử đã chạy lại renderer mặc định và để app hoạt động.

Log thô (build output được ignore):

- `app/build/logs/graphics-baseline-flutter.log`
- `app/build/logs/graphics-baseline-adb.log`
- `app/build/logs/graphics-skia-flutter.log`
- `app/build/logs/graphics-skia-adb.log`

## Giới hạn và hướng điều tra tiếp

Chưa xác định được dòng code cụ thể trong vendor driver gây phát log trên máy
này. Không kết luận đổi CameraX sang Camera2 hoặc cập nhật firmware chắc chắn
sẽ hết; cần phép thử riêng, giữ các biến khác cố định. Không đổi thư viện camera
hay tắt tăng tốc phần cứng toàn app chỉ để che một thông báo chưa chẩn đoán.

Nếu tiếp tục điều tra: so sánh camera mở/đã đóng, ví dụ Flutter tối giản, thiết
bị khác và các backend camera. Đo bằng logcat thô, kiểm tra preview/chụp/EXIF,
độ phân giải và upload trước khi giữ bất kỳ thay đổi tương thích nào.

Tài liệu chính thức:

- [Flutter Impeller](https://docs.flutter.dev/perf/impeller): tùy chọn thử tắt
  Impeller; runtime 3.44.1 đã cảnh báo opt-out sẽ bị loại bỏ trong tương lai.
- [Flutter issue 120995](https://github.com/flutter/flutter/issues/120995): từng
  có báo cáo đúng chuỗi log này; issue đã đóng, không cung cấp bản sửa áp dụng
  được cho repository này. Việc có issue tương tự không chứng minh cùng nguyên nhân.
