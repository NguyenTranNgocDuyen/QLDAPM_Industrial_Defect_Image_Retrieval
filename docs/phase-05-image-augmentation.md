# Phase 5 - Data Augmentation cho Bề Mặt Thiết Bị Điện Tử

## 1. Bản chất và bài toán thực tế

Trong các bài toán thị giác máy tính công nghiệp, đặc biệt là kiểm tra ngoại quan thiết bị điện tử:
- Số lượng ảnh có khuyết tật (vết xước, nứt, ố, móp) thường **rất khan hiếm** so với ảnh sản phẩm chuẩn (Normal).
- Điều kiện chụp ảnh thực tế rất đa dạng: góc cầm máy của công nhân hoặc robot kiểm định bị nghiêng nhẹ, đèn chiếu sáng bị lệch, rung động băng chuyền, hoặc cảm biến camera bị nhiễu hạt.
- **Rủi ro lớn nhất:** Nếu áp dụng các phép tăng cường dữ liệu bừa bãi (như xoay 90-180 độ cắt mất biên, đổi màu tùy tiện, méo hình cực đoan), bản chất của khuyết tật sẽ bị biến đổi hoặc làm nhãn bounding box bị lệch khỏi vết lỗi.

Phase 5 xây dựng quy trình **Data Augmentation có kiểm soát**, đồng bộ tuyệt đối giữa ảnh và nhãn bounding box theo chuẩn YOLO (`class x_center y_center width height`).

## 2. Phân biệt then chốt: Preprocessing vs Data Augmentation

| Tiêu chí | Preprocessing (Tiền xử lý) | Data Augmentation (Tăng cường dữ liệu) |
|---|---|---|
| **Thời điểm áp dụng** | Áp dụng ở cả **Training** và **Inference** | **Chỉ áp dụng trong quá trình Training** |
| **Mục đích** | Chuẩn hóa ảnh (resize, đưa về mean, khử nhiễu, cân bằng sáng) để đưa vào mô hình ổn định nhất | Tạo ra các biến thể dữ liệu giả lập điều kiện thực tế để mô hình chống overfitting và tổng quát hóa tốt hơn |
| **Xử lý nhãn** | Giữ nguyên hoặc điều chỉnh tỉ lệ khung bao theo ảnh chuẩn | **Bắt buộc biến đổi hình học đồng bộ với Bounding Box** |
| **Tập áp dụng** | Train, Validation, Test | **Tuyệt đối KHÔNG áp dụng lên tập Test/Validation** |

## 3. Các kỹ thuật Augmentation được chọn lọc

### A. Phép biến đổi hình học (Đồng bộ Bounding Box)
1. **Horizontal / Vertical Flip:**
   - Lật ảnh theo trục ngang và trục dọc.
   - Bounding box được tính lại: $x_{\text{new}} = 1.0 - x_{\text{old}}$ (với lật ngang) hoặc $y_{\text{new}} = 1.0 - y_{\text{old}}$ (với lật dọc).
   - *Ý nghĩa thực tế:* Thiết bị có thể được đặt xuôi hoặc ngược chiều trên khay kiểm tra.
2. **Slight Rotation ($\pm 8^\circ$):**
   - Xoay góc nhỏ giả lập góc đặt thiết bị lệch tay.
   - Bốn đỉnh $(x_1, y_1), (x_2, y_2), (x_3, y_3), (x_4, y_4)$ của từng bounding box được nhân với ma trận Affine xoay $M$, sau đó tính lại hình chữ nhật bao ngoài và cắt tỉa (clipping) về khoảng $[0, 1]$.

### B. Phép biến đổi mức pixel (Giữ nguyên Bounding Box)
1. **Brightness & Contrast Adjustment:**
   - Giả lập điều kiện thừa sáng hoặc thiếu sáng bằng công thức tuyến tính $I_{\text{out}} = \alpha I_{\text{in}} + \beta$.
2. **Gaussian Sensor Noise:**
   - Thêm nhiễu Gauss ($\sigma = 10$) mô phỏng nhiễu hạt ISO từ cảm biến camera công nghiệp khi chụp trong buồng tối.
3. **Motion Blur:**
   - Kernel làm mờ chuyển động mô phỏng rung động của camera hoặc băng chuyền rung lắc nhẹ lúc chụp.

## 4. Kết quả thực nghiệm Demo

Thực nghiệm sinh batch gồm 9 biến thể dữ liệu trên mẫu vỏ điện thoại chứa 2 lỗi (scratch và stain):
- `00_original.png` (Gốc)
- `01_horizontal_flip.png` (Lật ngang, box x đảo chiều)
- `02_vertical_flip.png` (Lật dọc, box y đảo chiều)
- `03_rotate_8deg.png` (Xoay +8 độ, tính lại 4 đỉnh box)
- `04_rotate_-8deg.png` (Xoay -8 độ)
- `05_brightness_contrast_a0.85_b-25.png` (Thiếu sáng)
- `06_brightness_contrast_a1.15_b30.png` (Thừa sáng)
- `07_gaussian_noise_s10.png` (Nhiễu cảm biến)
- `08_motion_blur_k5.png` (Rung nhòe chuyển động)

Mỗi ảnh xuất ra đi kèm tệp `.txt` theo đúng định dạng YOLO:
```text
<class_id> <x_center> <y_center> <width> <height>
```
Đồng thời sinh ảnh tổng hợp `augmentation_comparison_grid.png` hiển thị trực quan các bounding box đã biến đổi.

## 5. Hướng dẫn chạy và kiểm thử

Từ thư mục `image-processing`:

1. **Chạy demo sinh batch và lưu nhãn YOLO:**
   ```powershell
   $env:PYTHONPATH="."
   python -m defect_vision.augmentation_cli --output-dir outputs/augmentation-demo
   ```
2. **Chạy toàn bộ unit test:**
   ```powershell
   $env:PYTHONPATH="."
   pytest tests/test_augmentation.py
   ```
