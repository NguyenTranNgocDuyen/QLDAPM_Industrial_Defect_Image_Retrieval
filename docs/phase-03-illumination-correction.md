# Phase 3 - Illumination Correction

## 1. Bài toán được giải quyết

Thiết bị điện tử thường có bề mặt tối, bóng hoặc phản chiếu. Cùng một vết xước có thể gần như biến mất trong bóng râm, bị cháy sáng dưới đèn hoặc có độ tương phản khác nhau giữa các vị trí trên ảnh.

Illumination Correction cố gắng giảm biến thiên do ánh sáng để đặc trưng của vết xước, nứt, móp và vết bẩn ổn định hơn. Nó không thể khôi phục chi tiết đã bị mất hoàn toàn do vùng ảnh bị đen hoặc cháy sáng.

## 2. Vị trí trong pipeline

```text
Ảnh camera/upload
  -> Decode và sửa orientation
  -> Perspective Correction (tùy chọn)
  -> Illumination Correction (tùy chọn)
  -> Resize/letterbox và normalize theo model
  -> YOLO
  -> Detection Result
```

Input là ảnh `uint8` grayscale, BGR hoặc BGRA. Output giữ nguyên chiều rộng, chiều cao và số kênh. Với ảnh màu, các phép correction chỉ thay đổi kênh sáng `L` trong LAB để hạn chế thay đổi màu của lỗi.

## 3. Các phương pháp được chọn

| Phương pháp | Giải quyết | Độ phức tạp | Rủi ro | Vai trò trong Phase 3 |
|---|---|---:|---|---|
| Gamma | Toàn ảnh quá tối hoặc quá sáng | Thấp | Không sửa được ánh sáng cục bộ | Baseline toàn cục |
| CLAHE | Tương phản cục bộ thấp | Thấp | Khuếch đại noise/texture | Baseline cục bộ |
| Background estimation | Ánh sáng thay đổi chậm theo vị trí | Trung bình | Halo nếu kernel quá nhỏ | Phương pháp chính cho ánh sáng không đều |
| Background + CLAHE | Ánh sáng không đều và chi tiết yếu | Trung bình | Dễ xử lý quá tay | Chỉ bật sau thực nghiệm |
| Histogram equalization toàn cục | Trải histogram toàn ảnh | Thấp | Màu/tương phản gắt, nhạy vùng sáng lớn | Không chọn làm mặc định |
| Retinex | Chiếu sáng phức tạp | Cao hơn | Cần tuning, dễ halo và lệch màu | Chưa cần cho prototype |

Các lựa chọn trên phù hợp sáu tuần vì đều chạy bằng OpenCV, dễ giải thích, có thể bật/tắt và đo thời gian riêng.

## 4. Cách hoạt động

### Gamma Correction

Mỗi mức sáng `I` được biến đổi thành:

```text
I_output = 255 * (I_input / 255) ^ gamma
```

- `gamma < 1`: làm sáng vùng tối.
- `gamma > 1`: làm tối ảnh sáng.
- `gamma = 1`: giữ nguyên.

Chế độ auto ước lượng gamma từ mean luminance và đưa nó về gần `target_mean=128`. Nếu ảnh vừa có bóng tối vừa có vùng rất sáng nhưng mean đã gần 128, Gamma gần như không thay đổi ảnh; khi đó cần phương pháp cục bộ.

### CLAHE

CLAHE chia kênh sáng thành các ô, cân bằng histogram từng ô rồi nội suy giữa chúng. `clip_limit` giới hạn mức khuếch đại histogram để giảm nguy cơ làm noise quá mạnh.

Baseline:

```text
clip_limit = 2.0
grid_size = 8 x 8
```

### Background Estimation

Kênh sáng được làm mờ Gaussian bằng kernel lớn để ước lượng trường chiếu sáng thay đổi chậm:

```text
background = GaussianBlur(L, large_kernel)
corrected = L * median(background) / background
```

Kernel phải lớn hơn đáng kể so với vết lỗi và cấu trúc thiết bị. Kernel quá nhỏ sẽ xem phím, logo hoặc vết tối là ánh sáng nền và tạo quầng sáng quanh chúng. Baseline demo dùng `201`, nhưng cần thử `101`, `151`, `201`, `301` theo độ phân giải ảnh thật.

### Combined

Combined chạy Background Estimation trước, sau đó CLAHE. Đây không mặc định là phương pháp tốt nhất: bước thứ hai có thể khuếch đại noise hoặc artifact do bước đầu tạo ra.

## 5. Chạy code

Từ thư mục `image-processing`:

```powershell
python -m defect_vision.illumination_demo
```

Chạy trên ảnh thật:

```powershell
python -m defect_vision.illumination_cli `
  --input samples\phone-dark.jpg `
  --method all `
  --background-kernel 201 `
  --output-dir outputs\phone-dark
```

Các method hợp lệ: `gamma`, `clahe`, `background`, `combined`, `all`.

Output:

- `01_original.png`: ảnh nguồn.
- `02_*.png`: ảnh theo từng phương pháp.
- `comparison.png`: lưới before/after phục vụ demo và báo cáo.
- `metrics.json`: tham số, thời gian và thống kê luminance trước/sau.

## 6. Metrics ảnh được ghi lại

- `mean`: độ sáng trung bình.
- `std`: độ phân tán mức sáng; không đồng nghĩa trực tiếp với chất lượng tốt.
- `p05`, `p95`: mức sáng percentile 5% và 95%.
- `dark_fraction`: tỷ lệ pixel có luminance dưới 40.
- `bright_fraction`: tỷ lệ pixel có luminance trên 215.
- `clipped_dark_fraction`: tỷ lệ pixel gần đen hoàn toàn.
- `clipped_bright_fraction`: tỷ lệ pixel gần cháy sáng.
- `elapsedMs`: thời gian riêng của phương pháp.

Các metrics này giúp phát hiện xử lý quá tay, nhưng kết luận cuối vẫn phải dựa vào khả năng nhìn thấy lỗi và metrics detection.

## 7. Liên hệ trực tiếp với lỗi ngoại quan

- Vết xước mảnh: CLAHE có thể làm cạnh rõ hơn, nhưng cũng có thể làm texture nhựa giống vết xước.
- Vết nứt: background correction có thể giúp phần nứt nằm trong bóng râm; kernel nhỏ có thể tạo halo quanh đường nứt.
- Vết bẩn: thay đổi màu và sáng thường dễ thấy hơn sau khi ánh sáng nền được cân bằng.
- Móp/biến dạng: illumination correction không thay thế đặc trưng hình học; highlight phản xạ đôi khi chính là tín hiệu của vết móp.
- Bề mặt bóng: vùng cháy sáng đã mất chi tiết không thể được thuật toán khôi phục chính xác.

## 8. Cách đánh giá với YOLO

Chuẩn bị một tập test cố định gồm ảnh đủ sáng, thiếu sáng, quá sáng, bóng lệch và phản chiếu. Chạy cùng model và threshold cho từng cấu hình:

| Cấu hình | Precision | Recall | mAP50 | mAP50-95 | Preprocess ms | Inference ms | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| Không correction | | | | | | | |
| Gamma | | | | | | | |
| CLAHE | | | | | | | |
| Background | | | | | | | |
| Background + CLAHE | | | | | | | |

Ngoài bảng tổng, cần tách metrics theo điều kiện ánh sáng. Một phương pháp có thể tăng recall ở ảnh tối nhưng giảm precision ở ảnh đủ sáng.

## 9. Quy tắc chọn phương pháp

- Ảnh tối hoặc sáng tương đối đồng đều: thử Gamma trước.
- Chi tiết lỗi có tương phản cục bộ thấp: thử CLAHE mức nhẹ.
- Ánh sáng thay đổi từ trái sang phải hoặc có bóng lớn: thử Background Estimation.
- Chỉ dùng Combined khi Background vẫn để chi tiết quá yếu và kết quả YOLO xác nhận có lợi.
- Không correction nếu ảnh đã ổn định hoặc model đã học tốt các điều kiện ánh sáng đó.

## 10. Các file triển khai

- `image-processing/defect_vision/illumination.py`: thuật toán, validation và metrics.
- `image-processing/defect_vision/illumination_cli.py`: CLI so sánh và lưu output.
- `image-processing/defect_vision/illumination_demo.py`: demo ánh sáng không đều.
- `image-processing/tests/test_illumination.py`: unit test.
