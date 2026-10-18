"""Streamlit demo nâng cao cho CNN Visual Defect Classifier — TV1.

Chạy từ thư mục gốc project:
    streamlit run ui/app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st
from PIL import Image

from model.inference import load_classifier, predict_image
from preprocessing.enhancement import equalize_luminance
from preprocessing.filtering import gaussian_filter
from preprocessing.histogram import grayscale_histogram
from preprocessing.normalize import normalize_pixels
from preprocessing.pipeline import PreprocessConfig, preprocess_image
from preprocessing.resize import resize_image

# ---------------------------------------------------------------------------
# Hằng số
# ---------------------------------------------------------------------------

DEFAULT_CHECKPOINT = Path("outputs/model_gaussian/defect_classifier.pt")
FALLBACK_CHECKPOINTS = [
    Path("outputs/model/defect_classifier.pt"),
    Path("outputs/model_baseline/defect_classifier.pt"),
]
EXPERIMENT_SUMMARY = Path("outputs/experiment_summary.json")

COLOR_DEFECTIVE = "#EF4444"   # đỏ
COLOR_NORMAL    = "#22C55E"   # xanh lá

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_checkpoint() -> Path | None:
    for p in [DEFAULT_CHECKPOINT, *FALLBACK_CHECKPOINTS]:
        if p.exists():
            return p
    return None


@st.cache_resource(show_spinner=False)
def get_model(checkpoint_path: str):
    return load_classifier(checkpoint_path)


def _render_preprocessing_steps(pil_image: Image.Image, config: PreprocessConfig) -> None:
    """Hiển thị 5 bước preprocessing side-by-side."""
    original_arr = np.asarray(pil_image, dtype=np.uint8)

    # Bước 1: Resize
    resized = np.asarray(resize_image(pil_image, config.image_size), dtype=np.uint8)

    # Bước 2: Filter
    if config.filter_name == "gaussian":
        filtered = gaussian_filter(resized, config.filter_kernel)
        filter_label = f"Gaussian (k={config.filter_kernel})"
    elif config.filter_name == "median":
        from preprocessing.filtering import median_filter
        filtered = median_filter(resized, config.filter_kernel)
        filter_label = f"Median (k={config.filter_kernel})"
    else:
        filtered = resized.copy()
        filter_label = "No filter"

    # Bước 3: Contrast enhancement
    if config.contrast_enhancement:
        enhanced = equalize_luminance(filtered)
    else:
        enhanced = filtered.copy()

    # Bước 4: Normalize (visualize bằng cách scale về 0–255)
    normalized = normalize_pixels(enhanced)
    normalized_vis = (normalized * 255).clip(0, 255).astype(np.uint8)

    labels = ["① Original", f"② Resized\n({config.image_size}×{config.image_size})", f"③ {filter_label}", "④ Enhanced", "⑤ Normalized\n(model input)"]
    images = [original_arr, resized, filtered, enhanced, normalized_vis]

    cols = st.columns(5)
    for col, img_arr, label in zip(cols, images, labels):
        with col:
            st.image(img_arr, caption=label, use_container_width=True)


def _render_histogram_comparison(pil_image: Image.Image, config: PreprocessConfig) -> None:
    """Vẽ histogram ảnh gốc vs ảnh sau preprocessing."""
    original_arr = np.asarray(pil_image.resize((config.image_size, config.image_size)), dtype=np.uint8)
    processed_arr = (preprocess_image(pil_image, config) * 255).clip(0, 255).astype(np.uint8)

    hist_original = grayscale_histogram(original_arr)
    hist_processed = grayscale_histogram(processed_arr)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3))
    fig.patch.set_facecolor("#0E1117")

    for ax, hist, title in [(ax1, hist_original, "Original"), (ax2, hist_processed, "Sau preprocessing")]:
        ax.set_facecolor("#1A1D23")
        ax.plot(np.arange(256), hist, color="#F59E0B", linewidth=1.2)
        ax.fill_between(np.arange(256), hist, alpha=0.25, color="#F59E0B")
        ax.set(xlim=(0, 255), xlabel="Intensity", ylabel="Pixel count", title=title)
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.title.set_color("white")
        ax.tick_params(colors="white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#2D3139")
        ax.grid(alpha=0.15, color="white")

    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def _confidence_bar(confidence: float, is_defective: bool) -> None:
    """Thanh tiến trình màu đỏ/xanh + nhãn phần trăm."""
    color = COLOR_DEFECTIVE if is_defective else COLOR_NORMAL
    label = "DEFECTIVE" if is_defective else "NORMAL"
    st.markdown(
        f"""
        <div style="margin-bottom:4px">
            <span style="font-weight:700;font-size:14px;color:{color}">{label}</span>
            <span style="float:right;color:#9CA3AF;font-size:13px">{confidence:.1%}</span>
        </div>
        <div style="background:#1F2937;border-radius:6px;height:12px;overflow:hidden">
            <div style="background:{color};width:{confidence*100:.1f}%;height:100%;
                        border-radius:6px;transition:width 0.4s ease"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_experiment_table() -> None:
    """Đọc experiment_summary.json và hiển thị bảng kết quả."""
    if not EXPERIMENT_SUMMARY.exists():
        st.info(f"Chưa có file `{EXPERIMENT_SUMMARY}`. Chạy `python scripts/run_all_experiments.py` trước.")
        return

    with open(EXPERIMENT_SUMMARY) as f:
        records = json.load(f)

    import pandas as pd

    df = pd.DataFrame(records)
    df = df.rename(columns={
        "config": "Config",
        "accuracy": "Accuracy",
        "precision_defective": "Precision (Defect)",
        "recall_defective": "Recall (Defect)",
        "f1_defective": "F1 (Defect)",
        "false_negative": "False Negative",
    })
    df["Accuracy"] = df["Accuracy"].map("{:.2%}".format)
    df["Precision (Defect)"] = df["Precision (Defect)"].map("{:.2%}".format)
    df["Recall (Defect)"] = df["Recall (Defect)"].map("{:.2%}".format)
    df["F1 (Defect)"] = df["F1 (Defect)"].map("{:.4f}".format)

    # Highlight dòng tốt nhất
    def highlight_best(row):
        style = [""] * len(row)
        if str(row["Config"]) == "gaussian":
            style = ["background-color:#1a2e1a;color:#86EFAC"] * len(row)
        return style

    st.dataframe(df.style.apply(highlight_best, axis=1), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(
        page_title="Visual Defect Detection — TV1 Demo",
        page_icon="🔎",
        layout="wide",
    )

    # ---- Sidebar ----
    with st.sidebar:
        st.markdown("## 🔬 Model Info")
        st.markdown("""
| Thuộc tính | Giá trị |
|-----------|---------|
| Kiến trúc | DefectCNN (3 conv blocks) |
| Best config | **Gaussian filter**, kernel=5 |
| Test accuracy | **97.22%** |
| F1 (defective) | **0.9817** |
| False Negative | **1 / 180** |
| Input size | 224 × 224 RGB |
| Loss | BCEWithLogitsLoss |
""")
        st.divider()
        st.markdown("### 📂 Checkpoint")
        checkpoint_path = _find_checkpoint()
        if checkpoint_path:
            st.success(f"`{checkpoint_path}`")
        else:
            st.error("Chưa tìm thấy checkpoint.\nTrain trước:\n```\npython -m model.train --filter-name gaussian\n```")

        st.divider()
        st.markdown("### ▶️ Cách chạy")
        st.code("streamlit run ui/app.py", language="bash")
        st.code("uvicorn ui.local_api:app --reload --port 8000", language="bash")

    # ---- Main area ----
    st.title("🔎 Visual Defect Detection")
    st.caption("CNN Binary Classification: Normal / Defective — TV1 Demo")

    uploaded = st.file_uploader(
        "Upload ảnh thiết bị điện tử",
        type=["jpg", "jpeg", "png", "bmp", "webp"],
        help="Ảnh điện thoại, laptop, bàn phím…",
    )

    if uploaded is None:
        st.info("⬆️  Upload một ảnh để bắt đầu phân tích.")
        st.divider()
        st.subheader("📊 Kết quả thực nghiệm 4 cấu hình")
        _render_experiment_table()
        return

    pil_image = Image.open(uploaded).convert("RGB")

    col_img, col_result = st.columns([1, 1], gap="large")

    with col_img:
        st.subheader("Ảnh đầu vào")
        st.image(pil_image, use_container_width=True)

    with col_result:
        st.subheader("Kết quả phân loại")
        if not st.button("▶  Phân tích ảnh", type="primary", use_container_width=True):
            st.info("Bấm **Phân tích ảnh** để chạy CNN.")
        else:
            checkpoint_path = _find_checkpoint()
            if checkpoint_path is None:
                st.error(
                    "Không tìm thấy model checkpoint.\n\n"
                    "```\npython -m model.train --filter-name gaussian\n```"
                )
            else:
                with st.spinner("🔄 Đang chạy preprocessing và CNN inference…"):
                    try:
                        model, config, classes = get_model(str(checkpoint_path))
                        label, confidence = predict_image(pil_image, model, config, classes)
                    except Exception as e:
                        st.exception(e)
                        return

                is_defective = label == "defective"

                # Banner kết quả
                if is_defective:
                    st.error("🚨  **PHÁT HIỆN LỖI NGOẠI QUAN**")
                else:
                    st.success("✅  **THIẾT BỊ KHÔNG LỖI**")

                st.markdown("#### Độ tin cậy")
                _confidence_bar(confidence, is_defective)
                st.metric("Confidence", f"{confidence:.2%}", delta=None)

                st.divider()
                st.markdown(f"**Label raw:** `{label}` | **Checkpoint:** `{checkpoint_path.name}`")

                # Lưu config vào session state để dùng bên dưới
                st.session_state["_last_config"] = config
                st.session_state["_last_run"] = True

    # ---- Preprocessing steps (chỉ hiện sau khi phân tích) ----
    if st.session_state.get("_last_run"):
        config: PreprocessConfig = st.session_state["_last_config"]
        st.divider()
        st.subheader("🔧 Preprocessing Pipeline")
        _render_preprocessing_steps(pil_image, config)

        st.divider()
        st.subheader("📈 Histogram so sánh")
        _render_histogram_comparison(pil_image, config)

    # ---- Expander "Về pipeline" ----
    with st.expander("ℹ️  Về pipeline CNN"):
        st.markdown("""
**Luồng xử lý:**

```
Ảnh gốc
  → Resize (224×224, LANCZOS)
  → Gaussian blur (kernel 5×5)   — loại bỏ nhiễu sensor
  → (Contrast enhancement, nếu bật)
  → Normalize [0, 1]
  → DefectCNN (3 conv blocks + AdaptiveAvgPool + Linear(128→1))
  → Sigmoid → P(normal)
  → Threshold 0.5 → Normal / Defective
```

**Tại sao Gaussian?**  
Gaussian loại bỏ nhiễu Gaussian ngẫu nhiên từ camera mà không làm mờ cạnh vết lỗi quá mức.  
Config này đạt **Accuracy 97.22%, F1 0.9817, False Negative = 1** trên tập test 180 ảnh.

**Tại sao BCEWithLogitsLoss?**  
Bài toán nhị phân — single logit giúp giảm tham số, tăng numerical stability, calibration tốt hơn softmax 2 class.

**False Negative quan trọng hơn False Positive** trong QC: thiết bị lỗi bị bỏ qua là rủi ro thương hiệu. Vì vậy Recall và FN là chỉ số ưu tiên.
""")

    # ---- Bảng so sánh thực nghiệm ----
    st.divider()
    st.subheader("📊 Bảng so sánh 4 cấu hình thực nghiệm")
    _render_experiment_table()


if __name__ == "__main__":
    main()
