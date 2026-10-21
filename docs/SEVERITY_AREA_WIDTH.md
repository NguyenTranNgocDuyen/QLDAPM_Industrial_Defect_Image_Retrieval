# Phân cấp theo diện tích và bề rộng — 21/10/2026

Cấu hình mặc định: `image-processing/defect_vision/severity.v6.json`, phiên bản
`geometry-v6-area-2-5-width-5-8-unvalidated`. Đây là các ngưỡng thử nghiệm theo
đề xuất của người dùng, chưa được hiệu chỉnh/kiểm chứng bằng nhãn mức độ của con người.

## Quy tắc đang dùng

| Chỉ số | Nhẹ | Vừa | Dải Nặng của chỉ số |
|---|---|---|---|
| A: diện tích ứng viên / bề mặt quan sát | A ≤ 2% | 2% < A ≤ 5% | A > 5% |
| W: bề rộng P90 lớn nhất / cạnh ngắn mặt | W < 5% | 5% ≤ W < 8% | W ≥ 8% |

Mức tổng hợp có ưu tiên diện tích:

1. Có ứng viên và A ≤ 2%: **Nhẹ**, kể cả W hoặc skeleton lớn.
2. **Nặng** chỉ khi **A > 5% VÀ W ≥ 8%**.
3. Những trường hợp có ứng viên còn lại với A > 2%: **Vừa**. Ví dụ A=6%, W=7% vẫn Vừa.

Đúng 2% là Nhẹ; đúng 5% diện tích vẫn Vừa; đúng 8% bề rộng đạt điều kiện W của Nặng.
Ngưỡng W=5% mô tả dải của chỉ số bề rộng trong `metric_levels`, không tự nâng
vùng A nhỏ lên Vừa. `metric_levels` phục vụ đối chiếu từng chỉ số, còn
`estimated_severity` là mức tổng hợp. Các giá trị nội bộ là tỷ lệ (0.02, 0.05, 0.08).

Skeleton vẫn đo/hiển thị, chỉ tham khảo. `candidate_pixels_original >= 200` chỉ
là cờ báo ảnh gốc; không tham gia phân cấp. Mask rỗng không bị gán Nhẹ:
trả `estimated_severity=null`, `no_detected_damage` trong mặt quan sát.

Ảnh thiếu phần/hình học không đạt chỉ được ước tính sơ bộ A trên phần mask nhìn
thấy ở ảnh gốc, giữ `needs_review=true`, L/W=null. Nếu A > 5% nhưng thiếu W thì
tối đa Vừa, ghi `severe_unconfirmed_without_width`; không coi đây là mức độ toàn mặt/toàn máy.
Không có điện thoại, surface quá nhỏ hoặc lỗi xử lý vẫn trả cần kiểm tra/không đủ dữ liệu.

## Nguyên nhân mức cũ quá nhạy

v1–v3 lấy mức cao nhất từ ba chỉ số; W từ 1.5% đã ở dải Nặng. v4 yêu cầu cả
A và W để lên Nặng, nhưng A từ 0.5% HOẶC W từ 0.5% đã đủ Vừa. Vì vậy vùng
nhỏ cũng dễ bị nâng mức. v5 đưa A ≤ 2% về Nhẹ và A ≤ 5% về Vừa; v6 tiếp tục
đổi dải W theo đề xuất mới thành 5%/8%. Các cấu hình cũ được giữ để tái hiện
lịch sử, không ghi đè kết quả các lần quét đã lưu.

Với mẫu A=0.669490%, W=3.174603%, L=29.401133%, 405 pixel gốc:
v3=Nặng, v4=Vừa, hiện tại v6=**Nhẹ**. Đây là mức hình học của vùng **ứng viên**.
Việc giảm mức không khắc phục phát hiện nhầm của model: ảnh lành vẫn có thể
có ứng viên. UI ghi rõ ứng viên chưa được xác nhận, có thể là phản chiếu/đường viền.
Không công bố độ chính xác phân cấp từ các kiểm thử dưới đây.

## Luồng ảnh giữ nguyên

Không train, đổi checkpoint, threshold 0.4, protocol patch/context hoặc ngưỡng
báo ảnh 200 pixel. RGB gốc đúng EXIF và segmentation gốc vẫn vào
`ROIDamageEngine.predict_with_body`, `load_phone_detector=False`, một engine
mỗi worker, một lượt phone_detect mỗi ảnh. Không sửa/xóa/dilation mask nguồn.
Damage/surface được warp bằng cùng H/kích thước đích, nội suy nearest-neighbor.

## Tệp thay đổi trong lần chỉnh chính sách

- `image-processing/defect_vision/damage_severity.py`: chính sách ưu tiên A, biên A dùng `>`; giữ chính sách cũ khi đọc cấu hình cũ.
- `severity.v5.json`, `severity.v6.json` cùng thư mục: các ngưỡng có phiên bản, cờ chưa kiểm chứng; v6 là mặc định.
- `contracts/detection-result.schema.json`: nhận `area_led_width_confirmation`.
- `app/lib/features/inspection/presentation/result_screen.dart`: giải thích mức tổng hợp, skeleton tham khảo, cảnh báo ứng viên; số pixel trong mục thông tin phát hiện riêng.
- Các kiểm thử `test_severity_confirmation.py`, `test_damage_severity.py`, `test_observed_area.py`, `test_damage_integration.py`, `app/test/damage_result_test.dart` và fixture trong `scripts/verify_backend_postgres.py`.

Backend Java chuyển tiếp/lưu JSON severity hiện có, không cần đổi DTO hoặc database.

## Chạy và kiểm thử

Worker đang chạy cần khởi động lại một lần sau khi đổi cấu hình. Không chạy thêm
worker trùng cổng. Nếu `DAMAGE_SEVERITY_CONFIG` trỏ cấu hình cũ thì bỏ biến đó
hoặc trỏ tới v6. Health phải có `severity_config_version` bằng phiên bản v6 ở trên.

```powershell
cd D:\XuLiAnh\Industrial-Defect-Image-Retrieval\image-processing
& D:\XuLiAnh\.venv\Scripts\python.exe -m defect_vision.damage_api --port 8000 --device cpu
```

Đã nạp lại worker cổng 8000 trong lượt tích hợp này. Backend cổng 8080 tiếp tục
gọi worker đó. App chỉ cần phân tích lại ảnh để nhận mức mới; mở lịch sử cũ vẫn
hiện kết quả được lưu ở thời điểm quét. Hot restart/chạy lại Flutter để có lời giải
thích UI mới. Lệnh chạy app USB đã lọc log hệ thống:

```powershell
cd D:\XuLiAnh\Industrial-Defect-Image-Retrieval\app
powershell -ExecutionPolicy Bypass -File .\scripts\run-app.ps1
```

Kiểm thử Python và Flutter:

```powershell
cd D:\XuLiAnh\Industrial-Defect-Image-Retrieval\image-processing
& D:\XuLiAnh\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp outputs/test-tmp-local-v6
cd ..\app
flutter test --no-pub
```

146 kiểm thử Python và 41 kiểm thử Flutter đã qua; kiểm tra tĩnh hai tệp Flutter
thay đổi không báo lỗi. Bao gồm ranh giới 2%/5%/8%, dải W=5%, tương thích cấu
hình cũ, vết dài mảnh, đốm ngắn dày, mảng rộng, mask rỗng/sai kích thước, đổi
độ phân giải, mask không bị sửa và tái sử dụng engine/detector.

Kiểm thử qua backend thật, checkpoint thật và PostgreSQL:

```powershell
cd D:\XuLiAnh\Industrial-Defect-Image-Retrieval\image-processing
& D:\XuLiAnh\.venv\Scripts\python.exe scripts/verify_observed_estimates.py --case back outputs/severity-confirmation-verification/original/before.json --output-dir outputs/severity-confirmation-verification/v6-replay
```

Ảnh kiểm thử vẫn giữ nguyên 405 pixel, mask/overlay đúng tọa độ và tỷ lệ đo,
JSON lưu/đọc lại khớp; health xác nhận v6 và đúng một lượt detector cho một ảnh.
Bằng chứng lưu tại `image-processing/outputs/severity-confirmation-verification/v6-replay/`.
Thư mục outputs bị Git ignore; lệnh này tạo lần quét kiểm thử có đánh dấu trong lịch sử.

Giới hạn: phân cấp này cố ý giảm ảnh hưởng của vùng diện tích nhỏ; vết mảnh dài
có thể vẫn được gán Nhẹ theo chính sách người dùng đã chọn. Sai segmentation,
phối cảnh, phản chiếu và mask vài pixel có thể làm số đo sai lệch. Đây không phải
đánh giá loại lỗi, độ sâu, chức năng hoặc sức khỏe toàn thiết bị.
