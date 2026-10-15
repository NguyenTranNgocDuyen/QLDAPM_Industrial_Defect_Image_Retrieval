# Phase 6 - Đánh Giá & So Sánh Ảnh Trước / Sau (Before & After Suite)

## 1. Bản chất và bài toán thực tế

Một hiểu lầm rất phổ biến trong xử lý ảnh là:
> *"Một thuật toán làm ảnh trông sáng hơn, rực rỡ hơn hoặc nét hơn thì chắc chắn sẽ giúp mô hình AI phát hiện lỗi tốt hơn."*

**Thực tế hoàn toàn ngược lại:**
- Tăng tương phản quá mức (ví dụ CLAHE với `clip_limit` quá cao) có thể khuếch đại nhiễu cảm biến (*sensor noise*), làm nổi vân sần bình thường của vỏ nhôm thành các vùng giống khuyết tật $\rightarrow$ gây ra **False Positive**.
- Làm mịn ảnh quá tay bằng Gaussian Filter có thể xóa sạch các vết xước chân tóc mảnh (*fine hairline scratches*) $\rightarrow$ gây ra **False Negative**.
- Phase 6 xây dựng một bộ đo lường định lượng khoa học (*Quantitative Benchmark Suite*) để trả lời câu hỏi: **"Kỹ thuật xử lý ảnh này có thực sự giúp tách khuyết tật tốt hơn không, hay chỉ làm đẹp ảnh nhưng khuếch đại nhiễu?"**

## 2. Các chỉ số định lượng (Quantitative Metrics)

| Chỉ số | Công thức / Ý nghĩa | Vai trò trong kiểm định lỗi ngoại quan |
|---|---|---|
| **Contrast Std ($\sigma_I$)** | Độ lệch chuẩn mức xám toàn ảnh | Đo độ trải rộng dải động; giá trị quá nhỏ nghĩa là ảnh bị mù/mờ sương |
| **Laplacian Variance** | $\text{Var}(\nabla^2 I)$ | Độ sắc nét của biên; giúp kiểm tra vết nứt/xước có bị mờ đi không |
| **Tenengrad Energy** | $\frac{1}{N}\sum (G_x^2 + G_y^2)$ | Năng lượng đạo hàm bậc 1 Sobel; đo mật độ chi tiết cao tần |
| **Shannon Entropy** | $-\sum p_i \log_2(p_i)$ | Lượng thông tin chứa trong ảnh (tính bằng bits/pixel) |
| **Noise Std ($\sigma_{\text{bg}}$)** | Độ lệch chuẩn cao tần trên vùng nền đồng nhất | **Cảnh báo khuếch đại nhiễu:** nếu tỉ lệ tăng nhiễu $> 2.5\times$, rủi ro tạo lỗi giả rất cao |
| **Defect CNR** | $\frac{|\mu_{\text{defect}} - \mu_{\text{bg}}|}{\sqrt{\sigma_{\text{defect}}^2 + \sigma_{\text{bg}}^2}}$ | **Chỉ số quan trọng nhất:** Tỷ số tương phản trên nhiễu giữa vết lỗi và nền xung quanh |

## 3. Kết quả thực nghiệm Benchmark

Thực nghiệm trên mẫu vỏ kim loại bị thiếu sáng (underexposed), chứa vết xước mảnh và vết ố hóa chất cùng nhiễu cảm biến thực tế:

```text
Technique                    | Latency  | Contrast Gain | Noise Gain | Defect CNR       | Verdict
---------------------------------------------------------------------------------------------------------
Gamma Correction (auto)      | 122.4 ms |         1.36x |      1.39x | 1.76 -> 1.93     | Marginal (Defect CNR unchanged)
CLAHE (clip=2.0)             |   5.6 ms |         2.92x |      3.08x | 1.76 -> 2.05     | Highly Beneficial (Defect CNR improved)
CLAHE Aggressive (clip=6.0)  |   5.8 ms |         6.92x |      7.42x | 1.76 -> 1.97     | Marginal / Risk of Noise
---------------------------------------------------------------------------------------------------------
```

### Kết luận khoa học rút ra:
1. **CLAHE với clip_limit chuẩn (2.0):** Tăng tương phản lên $2.92\times$, độ tương phản trên nhiễu của khuyết tật (CNR) tăng từ $1.76 \rightarrow 2.05$ với độ trễ cực thấp ($5.6\text{ ms}$). Đây là phương án hiệu quả nhất được khuyến nghị đưa vào pipeline suy luận.
2. **CLAHE lạm dụng (clip_limit=6.0):** Mặc dù mắt nhìn thấy tương phản tăng tới $6.92\times$, nhưng nhiễu nền bị khuếch đại tới $7.42\times$, làm CNR của vết lỗi bị thụt lùi so với mức đỉnh ($1.97 < 2.05$).
3. **Gamma Correction:** Phù hợp kéo sáng toàn cục nhưng tốc độ ước lượng auto chậm hơn và không cải thiện độ sắc nét cục bộ của vết xước.

## 4. Hướng dẫn chạy và xuất báo cáo

Từ thư mục `image-processing`:

1. **Chạy benchmark tự động và xuất ảnh so sánh:**
   ```powershell
   $env:PYTHONPATH="."
   python -m defect_vision.comparison_cli --output-dir outputs/comparison-demo
   ```
2. **Các tệp xuất ra phục vụ báo cáo đồ án:**
   - `enhancement_benchmark_report.json`: Số liệu định lượng JSON phục vụ vẽ biểu đồ.
   - `compare_clahe_clip2.0.png`: Ảnh ghép Before/After kèm bảng phân tích chỉ số hiển thị trực quan dưới chân ảnh.
   - `compare_gamma_correction_auto.png`: Đánh giá phương pháp Gamma.
3. **Chạy unit tests:**
   ```powershell
   $env:PYTHONPATH="."
   pytest tests/test_comparison.py
   ```
