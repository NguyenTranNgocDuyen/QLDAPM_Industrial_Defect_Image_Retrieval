# Phase 2 - Perspective Correction

## 1. Bài toán được giải quyết

Khi camera không vuông góc với điện thoại, bàn phím hoặc chuột, các cạnh song song ngoài thực tế có thể hội tụ trên ảnh. Phần gần camera trông lớn hơn phần xa camera; vết xước, nứt và móp cũng bị thay đổi hình dạng hoặc tỷ lệ.

Perspective Correction biến vùng tứ giác chứa thiết bị thành ảnh nhìn chính diện. Mục tiêu trong dự án là giảm biến thiên do góc chụp để việc so sánh bề mặt và detection ổn định hơn, không phải chỉ làm ảnh đẹp hơn.

## 2. Vị trí trong pipeline

```text
Ảnh camera/upload
  -> Decode và sửa orientation
  -> Perspective Correction (tùy chọn)
  -> Illumination/Color Correction (tùy chọn)
  -> Resize/letterbox
  -> YOLO
  -> Detection Result
```

Input:

- Ảnh BGR, BGRA hoặc grayscale.
- Bốn điểm là bốn góc ngoài của thiết bị trên ảnh.

Output:

- Ảnh thiết bị đã được đưa về hình chữ nhật nhìn chính diện.
- Ma trận homography để truy vết phép biến đổi.
- Kích thước output, các điểm đã sắp xếp và thời gian xử lý.

Nếu YOLO chạy trên ảnh đã hiệu chỉnh, bounding box thuộc không gian tọa độ của ảnh này. Theo contract Phase 1, Flutter phải hiển thị đúng `displayImage` trước khi vẽ box.

## 3. Homography hoạt động như thế nào

Một điểm ảnh nguồn `p = (x, y)` được ánh xạ sang điểm đích `p' = (x', y')` bằng ma trận homography `H` kích thước 3x3:

```text
[u]   [h11 h12 h13] [x]
[v] = [h21 h22 h23] [y]
[w]   [h31 h32 h33] [1]

x' = u / w
y' = v / w
```

Bốn cặp điểm không thẳng hàng cung cấp đủ ràng buộc để tìm `H`. Trong code:

- `cv2.getPerspectiveTransform(source, destination)` tính homography.
- `cv2.warpPerspective(image, H, size)` biến đổi toàn bộ vùng ảnh.

Bốn điểm được chuẩn hóa thành:

```text
top-left -> top-right -> bottom-right -> bottom-left
```

Điểm đích là bốn góc của một hình chữ nhật. Chiều rộng và chiều cao được lấy theo cạnh lớn hơn của hai cạnh đối diện để hạn chế cắt mất nội dung.

## 4. Cách sử dụng

Từ thư mục `image-processing`:

```powershell
python -m defect_vision.perspective_cli `
  --input samples\keyboard.jpg `
  --points "118,74;1060,93;1108,676;82,651" `
  --output-dir outputs\keyboard-01
```

Điểm có thể truyền theo thứ tự bất kỳ. Module kiểm tra:

- Có đúng bốn điểm hay không.
- Các điểm có khác nhau và nằm trong ảnh hay không.
- Bốn điểm có tạo thành tứ giác lồi đủ lớn hay không.

Để thử ngay mà chưa cần ảnh thật:

```powershell
python -m defect_vision.demo
```

Demo tạo một bề mặt thiết bị tổng hợp có vết xước/nứt, làm méo phối cảnh rồi chạy hiệu chỉnh. Nó chỉ kiểm tra pipeline hình học; không thay thế đánh giá trên dữ liệu thật.

## 5. Perspective Correction có giúp YOLO không?

Có khả năng giúp khi:

- Góc chụp giữa các ảnh thay đổi nhiều nhưng thiết bị có biên ngoài rõ.
- Vết lỗi nhỏ bị co lại mạnh ở phía xa camera.
- Dataset huấn luyện chủ yếu là ảnh gần chính diện.
- Cần chuẩn hóa thiết bị trước các phép phân tích bề mặt khác.

Có thể không giúp hoặc làm xấu kết quả khi:

- YOLO đã được train với nhiều góc nhìn và augmentation perspective phù hợp.
- Bốn góc chọn sai, biên thiết bị bị che hoặc thiết bị không gần phẳng.
- Nội suy làm mờ vết xước rất mảnh hoặc tạo artifact quanh vết nứt.
- Phép kéo giãn quá mạnh làm thay đổi hình dạng đặc trưng của lỗi.
- Thời gian tìm góc và warp lớn hơn lợi ích đạt được.

Vì vậy module không tự động bật trong mọi lần inference. Cần so sánh cùng một tập ảnh với `perspective=off` và `perspective=on`.

## 6. Cách đánh giá

### Chất lượng hình học

- Cạnh thiết bị sau hiệu chỉnh có gần ngang/dọc hơn không?
- Thiết bị có bị cắt mất phần nào không?
- Tỷ lệ chiều rộng/chiều cao có hợp lý không?
- Vết lỗi nhỏ có còn nhìn thấy rõ không?

### Ảnh hưởng đến detection

Chạy cùng model, threshold và tập test cho hai cấu hình:

| Cấu hình | Precision | Recall | mAP50 | mAP50-95 | Preprocess ms | Inference ms |
|---|---:|---:|---:|---:|---:|---:|
| Baseline, không correction | | | | | | |
| Perspective correction | | | | | | |

Chỉ kết luận phương pháp có ích khi metrics detection hoặc độ ổn định giữa các góc chụp được cải thiện trên nhiều ảnh. Một ảnh before/after đẹp chưa đủ để kết luận.

### Bộ ảnh thử tối thiểu

- Ảnh chính diện làm đối chứng.
- Ảnh nghiêng nhẹ, vừa và mạnh.
- Ảnh có đủ các loại lỗi đang có dữ liệu.
- Ảnh biên bị che hoặc nền phức tạp để kiểm tra failure case.

## 7. Chi phí và lựa chọn cho đồ án

| Phương án | Độ phức tạp | Demo | Rủi ro | Chọn ở Phase 2 |
|---|---|---|---|---|
| Chọn 4 điểm thủ công | Thấp | Rất rõ | Phụ thuộc người chọn | Có |
| Contour lớn nhất tự động | Trung bình | Tốt khi nền sạch | Dễ chọn nhầm nền/đổ bóng | Chưa bật |
| Keypoint/deep corner detector | Cao | Khó giải thích hơn | Cần dữ liệu/model riêng | Không |

Chọn điểm thủ công phù hợp để chứng minh thuật toán và tạo baseline trong sáu tuần. Tự động tìm bốn góc chỉ nên thêm sau khi có ảnh camera thật và xác nhận biên thiết bị đủ ổn định.

## 8. Các file triển khai

- `image-processing/defect_vision/perspective.py`: thuật toán và validation.
- `image-processing/defect_vision/perspective_cli.py`: CLI, lưu ảnh và timing.
- `image-processing/defect_vision/demo.py`: dữ liệu demo tổng hợp.
- `image-processing/tests/test_perspective.py`: unit test.
