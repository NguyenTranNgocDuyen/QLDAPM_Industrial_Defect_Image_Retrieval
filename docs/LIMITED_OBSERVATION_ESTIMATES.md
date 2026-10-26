# Ước tính khi ảnh nghiêng hoặc thiếu phần — 21/10/2026

Lưu ý: tài liệu này ghi bước triển khai v3. Chính sách hiện tại là
[severity v6 theo diện tích 2%/5%, bề rộng 5%/8%](SEVERITY_AREA_WIDTH.md),
không còn lấy mức cao nhất từ A/L/W. Cách giữ cảnh báo và đo phần nhìn thấy vẫn áp dụng.

Mặc định mới: `severity.v3.json` / `geometry-v3-observed-fallback-unvalidated`.
Giữ checkpoint và protocol v3; không train thêm. Các ngưỡng vẫn chưa kiểm chứng.

## Hành vi

| Dữ liệu có được | Kết quả |
|---|---|
| Hình học dùng được | Ước tính theo A/L/W như trước, lấy mức cao nhất |
| Hình học thiếu/không ổn định, mặt bị cắt/che | Mức sơ bộ chỉ theo A của mask trên ảnh gốc; L/W để null |
| Nhiều máy nhưng đã chọn một mask | Ước tính cho máy được chọn, giữ cảnh báo mục tiêu cần kiểm tra |
| Không có điện thoại, mask sai/lỗi model hoặc vùng quá nhỏ | Không ép ra Nhẹ/Vừa/Nặng |
| Mask ứng viên rỗng | Chưa phát hiện ứng viên trên phần quan sát; không suy ra toàn máy lành |

Detector vẫn chọn một instance có confidence cao nhất, không gộp mask các máy.
Nhiều instance không còn tự động khóa mọi mức độ; JSON/UI ghi rõ mục tiêu tự
chọn. Cần kiểm tra overlay đúng điện thoại mong muốn. Không tự coi đây là người
dùng đã xác nhận mục tiêu hoặc đã cung cấp hình học vật lý.

Khi phải dùng chế độ sơ bộ, hiển thị **ảnh gốc** cùng overlay gốc để tránh xén
vùng ứng viên theo một tứ giác không đáng tin cậy. Không gửi ảnh warp ngược vào
model, không chạy detector/model lần thứ hai để phục vụ fallback.

## Giới hạn của mức sơ bộ

- A = số pixel `(damage AND observed_surface)` / số pixel observed_surface,
  tính trên ảnh gốc. Vẫn dùng ngưỡng khởi tạo 0,5% → Vừa; 3% → Nặng.
- Đây là tỷ lệ vùng ứng viên được chiếu trên ảnh, chịu ảnh hưởng phối cảnh,
  không phải phần trăm hư hại thật của toàn mặt hoặc toàn thiết bị.
- Không lấy bbox của phần bị cắt làm kích thước toàn mặt. L/W và số đo skeleton
  chưa tính trong chế độ này đều là null, không gán 0 để giả vờ đã đo.
- Một mức Nhẹ theo diện tích chưa loại trừ vết dài mảnh cần mức cao hơn khi đo
  được chiều dài. UI ghi rõ giới hạn này, không trình bày như kết luận ba chỉ số.
- Không dự đoán hoặc phục hồi phần không xuất hiện trong ảnh, không tô thêm mask.
- `needs_review=true`, `heuristic_unvalidated=true` luôn giữ trong mức sơ bộ.
  Vùng dưới 256 pixel không được ép phân cấp. Ngưỡng báo ảnh 200 pixel gốc độc lập.

JSON bổ sung:

```json
{
  "status": "estimated",
  "estimated_severity": "moderate",
  "needs_review": true,
  "estimation_basis": "observed_area_only",
  "severity_is_partial": true,
  "scope": "observed_surface_only",
  "measurement_coordinate_space": "source",
  "area_ratio": 0.02,
  "skeleton_length_ratio": null,
  "width_ratio": null,
  "unassessed_metrics": ["skeleton_length_ratio", "width_ratio"],
  "locations_coordinate_space": "source"
}
```

`locations` ở chế độ này dùng `candidate_pixels_source`, không gọi số pixel
nguồn là pixel rectified. Hợp đồng JSON được cập nhật. `transformMatrix=null`,
`displayImage.coordinateSpace=source`; không xuất asset warped gây nhầm hệ tọa độ.
Lỗi hình học đã biết có thể fallback; lỗi mask/model vẫn là lỗi xử lý rõ ràng.

## Nới cạnh phiên bản 2

`corner_expansion.v2.json` / `corner-expansion-v2-unvalidated` là mặc định mới:

| Thông số | Trước | Mới |
|---|---:|---:|
| Bao phủ tối thiểu để giữ khung | 98% | 98% |
| Mục tiêu khi cần nới | 98,5% | 99% |
| Dịch cạnh tối đa / cạnh ngắn | 10% | 15% |
| Dịch góc tối đa / cạnh ngắn | 20% | 25% |
| Tỷ lệ tăng diện tích khung tối đa | 1,25 | 1,35 |
| Phần nằm ngoài mask trong khung mới tối đa | 8% | 12% |

Vẫn chỉ nới cạnh thiếu, không phóng cả khung theo tỷ lệ cố định, không buộc giữ
đủ 100% pixel ngoại lai. Góc mới vượt ảnh hoặc vượt các giới hạn thì từ chối.
Nới khung không sửa được góc sai hướng hoặc mask nhận diện sai. Khi nới không
đủ điều kiện, chế độ sơ bộ giúp tiếp tục trả thông tin từ nguồn.

## Kiểm thử đã chạy

- 118 kiểm thử Python đạt; 40 kiểm thử Flutter đạt. Phân tích tĩnh các file UI
  và test sửa đổi không có lỗi/cảnh báo.
- Kiểm tra dài mảnh, diện tích, rỗng, vùng quá nhỏ, sai kích thước, thay đổi độ
  phân giải; hình học thiếu/hỏng giữ source overlay và không chạy lại detector.
- Checkpoint thật: ba ảnh mẫu + trắng, engine khởi tạo một lần/worker,
  bốn request/bốn detector, cùng instance. Đối chiếu mask độc lập bằng nhau.
- Qua BE/DB thật: ảnh 329k bị cắt ở biên trả Nặng **sơ bộ theo vùng nhìn thấy**,
  A khoảng 41,71%, L/W null; ảnh trắng vẫn phone_not_found, grade null.
- Hai capture gần nhất trước sửa đều needs_review/grade null vì nhận ba máy.
  Sau sửa, ảnh nhãn front trả Nặng theo ảnh, giữ cảnh báo mục tiêu; ảnh nhãn back
  tăng bao phủ mask từ 81,54% lên 99,06%, trả Vừa theo ảnh và cảnh báo mục tiêu.
  Cả hai giữ mask thân máy/hư hại gốc bằng nhau từng pixel; JSON lưu/đọc lại đúng,
  mask sau warp khớp cùng H/kích thước, hai request chạy hai detector.
- Đây là kết quả suy luận và kiểm thử tích hợp, không phải nhãn mức độ đúng.
  Ảnh capture là ảnh chụp màn hình laptop có nhiều ảnh điện thoại; không dùng
  để công bố accuracy hoặc độ tin cậy trên điện thoại thực.

Bằng chứng: `image-processing/outputs/partial-estimate-verification/`,
`outputs/damage-verification/verification.json` và
`outputs/backend-postgres-verification/verification.json` (hai đường dẫn sau
tính từ image-processing). Các bản ghi lịch sử cũ giữ nguyên; cần phân tích lại.

## Chạy lại và sử dụng

Worker mới cần khởi động lại để nhận cấu hình/code. Chỉ chạy một worker cổng 8000.
Backend không đổi API và không cần migration cho thay đổi này. App cần chạy lại
để nhận nhãn sơ bộ, cảnh báo và nhãn lịch sử mới.

```powershell
# Trong image-processing
& D:\XuLiAnh\.venv\Scripts\python.exe -m pytest tests -p no:cacheprovider --basetemp outputs/pytest-partial-check -q
& D:\XuLiAnh\.venv\Scripts\python.exe scripts/verify_damage_integration.py
& D:\XuLiAnh\.venv\Scripts\python.exe scripts/verify_backend_postgres.py
# Khi cần tự chạy worker, sau khi dừng worker cũ:
& D:\XuLiAnh\.venv\Scripts\python.exe -m defect_vision.damage_api --port 8000 --device cpu
# Trong app
flutter test
powershell -ExecutionPolicy Bypass -File .\scripts\run-app.ps1
```

Phát lại capture đã lưu: `scripts/verify_observed_estimates.py --case front
PATH/TO/before.json --case back PATH/TO/before.json`. Mỗi thư mục case cần có
source.png, body_original.png, damage_original.png; script tạo các scan test mới.
Muốn chính sách cũ, cấu hình `DAMAGE_SEVERITY_CONFIG` về severity.v2.json trước
khi khởi động worker (không ảnh hưởng checkpoint).

File thay đổi: `damage_service.py`, `damage_severity.py`, `corner_expansion.py`,
config mới `severity.v3.json`, `corner_expansion.v2.json`; contract JSON;
UI analysis/result/history và test liên quan; các script verify và tài liệu.
Không train, không đổi ngưỡng suy luận 0.4 hay mask nguồn.
