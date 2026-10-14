# Phase 4 - Color Space Analysis

## 1. Bản chất và bài toán thực tế

Khi kiểm tra ngoại quan thiết bị điện tử (điện thoại, linh kiện), các khuyết tật trên bề mặt có bản chất vật lý và quang học rất đa dạng:
- **Vết xước (Scratch) / Vết nứt (Crack):** Thường làm thay đổi khả năng tán xạ ánh sáng, tạo ra sự chênh lệch rõ rệt về cường độ sáng (*Luminance/Value*), nhưng không làm đổi màu sắc nền.
- **Vết ố hóa chất, gỉ sét, đốm bẩn (Stain/Discoloration):** Có thể có cường độ sáng gần tương đương màu vỏ máy (độ tương phản xám rất thấp), nhưng độ bão hòa màu (*Saturation*) hoặc sắc thái màu (*Hue/Chroma*) lại khác biệt rõ rệt.

Nếu chỉ sử dụng ảnh mức xám thông thường (`Grayscale`), hệ thống sẽ mất hoàn toàn thông tin màu, khiến các lỗi dạng ố/bẩn/đổi màu bị chìm vào nền. Ngược lại, nếu chỉ dựa vào RGB, 3 kênh màu bị tương quan mạnh với cường độ sáng, gây khó khăn cho việc phân ngưỡng và trích xuất đặc trưng.

## 2. Vị trí trong pipeline

```text
Ảnh camera / Upload
  -> Perspective Correction (Phase 2)
  -> Illumination Correction (Phase 3)
  -> Color Space Transformation & Channel Decomposition (Phase 4)
       |--> [Kênh Luminance L / Gray] -> Dùng cho TV2 (Canny, Threshold phát hiện Crack/Scratch)
       |--> [Kênh Saturation S / Chrominance A, B] -> Dùng cho phát hiện Stain / Discoloration
       |--> [Ảnh BGR/RGB chuẩn hóa] -> Đầu vào cho YOLO Object Detection
```

## 3. Các không gian màu được nghiên cứu

| Không gian màu | Các kênh | Ứng dụng trong phát hiện lỗi | Ưu điểm đối với bài toán |
|---|---|---|---|
| **BGR / RGB** | Blue, Green, Red | Đầu vào mặc định của camera và YOLO | Chuẩn công nghiệp cho Deep Learning |
| **Grayscale** | Gray | Xử lý ảnh truyền thống (Canny, Sobel, Threshold) | Giảm 3 lần dung lượng, tính toán nhanh nhất |
| **HSV** | Hue (H), Saturation (S), Value (V) | Tách biệt sắc thái màu (H), độ rực màu (S) và độ sáng (V) | Kênh **S** cực kỳ nhạy với các vết ố, bẩn, dầu loang trên bề mặt mạ |
| **LAB (CIE-L\*a\*b\*)** | Lightness (L), a\* (Green-Red), b\* (Blue-Yellow) | Mô phỏng mắt người, tách biệt hoàn toàn độ sáng (L) và sắc độ (a, b) | Kênh **L** lý tưởng để khử nhiễu/tăng sáng (CLAHE), kênh **a, b** phát hiện oxy hóa/đổi màu |

## 4. Công thức định lượng độ tương phản (Contrast Metrics)

Để đánh giá một kênh màu có hiệu quả trong việc làm nổi bật khuyết tật hay không, Phase 4 triển khai 3 chỉ số định lượng:

1. **Michelson Contrast:**
   $$\text{Michelson} = \frac{|\mu_{\text{defect}} - \mu_{\text{bg}}|}{\mu_{\text{defect}} + \mu_{\text{bg}} + \epsilon}$$
2. **Weber Contrast:**
   $$\text{Weber} = \frac{\mu_{\text{defect}} - \mu_{\text{bg}}}{\mu_{\text{bg}} + \epsilon}$$
3. **Contrast-to-Noise Ratio (CNR):**
   $$\text{CNR} = \frac{|\mu_{\text{defect}} - \mu_{\text{bg}}|}{\sqrt{\sigma_{\text{defect}}^2 + \sigma_{\text{bg}}^2 + \epsilon}}$$
   *CNR là chỉ số quan trọng nhất: kênh nào có CNR cao nhất là kênh tách biệt khuyết tật khỏi nền tốt nhất và ít bị nhiễu nhất.*

## 5. Kết quả thực nghiệm Demo

Thực nghiệm trên mẫu vỏ kim loại tổng hợp chứa đồng thời vết ố hóa chất (stain), vết xước mảnh (scratch) và vết nứt (crack):

```text
--- Defect Contrast & CNR Analysis across Color Spaces ---
Channel      | Defect Mean  | BG Mean    | Michelson  | CNR     
--------------------------------------------------------------
Gray         | 156.99       | 114.75     | 0.155      | 1.03    
H            | 24.92        | 105.00     | 0.616      | 3.54    
S            | 139.15       | 21.45      | 0.733      | 3.07    
V            | 189.96       | 120.75     | 0.223      | 1.51    
L            | 166.62       | 123.47     | 0.149      | 1.00    
A            | 133.35       | 127.00     | 0.024      | 3.65    
B_channel    | 167.95       | 124.75     | 0.148      | 2.71    
--------------------------------------------------------------
-> Kênh tối ưu nhất để tách khuyết tật màu/ố: [A] (CNR = 3.65) và [S] (CNR = 3.07).
-> Kênh tối ưu cho vết xước vật lý (thay đổi độ sáng): [L] và [Gray].
```

## 6. Hướng dẫn chạy và kiểm thử

Từ thư mục `image-processing`:

1. **Chạy demo và sinh biểu đồ so sánh:**
   ```powershell
   $env:PYTHONPATH="."
   python -m defect_vision.colorspace_cli --output-dir outputs/colorspace-demo
   ```
2. **Chạy trên ảnh thiết bị thật:**
   ```powershell
   $env:PYTHONPATH="."
   python -m defect_vision.colorspace_cli --input <duong_dan_anh> --output-dir outputs/test-device
   ```
3. **Chạy unit tests:**
   ```powershell
   $env:PYTHONPATH="."
   pytest tests/test_colorspace.py
   ```
