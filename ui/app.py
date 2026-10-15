"""Streamlit UI for TV1's Normal/Defective CNN classifier."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from PIL import Image

from model.inference import load_classifier, predict_image


DEFAULT_CHECKPOINT = Path("outputs/model/defect_classifier.pt")


@st.cache_resource(show_spinner=False)
def get_model(checkpoint_path: str):
    return load_classifier(checkpoint_path)


def main() -> None:
    st.set_page_config(page_title="Visual Defect Detection", page_icon="🔎", layout="centered")
    st.title("Visual Defect Detection")
    st.caption("CNN binary classification: Normal or Defective")
    uploaded = st.file_uploader("Choose an electronic-device image", type=["jpg", "jpeg", "png", "bmp", "webp"])
    if uploaded is None:
        st.info("Upload an image to preview it, then choose Analyze image.")
        return

    image = Image.open(uploaded).convert("RGB")
    st.image(image, caption="Selected image", use_container_width=True)
    if not st.button("Analyze image", type="primary"):
        return
    if not DEFAULT_CHECKPOINT.exists():
        st.error(f"No trained model found at `{DEFAULT_CHECKPOINT}`. Train it with `python -m model.train` first.")
        return
    try:
        with st.spinner("Running preprocessing and CNN inference…"):
            model, config, classes = get_model(str(DEFAULT_CHECKPOINT))
            label, confidence = predict_image(image, model, config, classes)
    except Exception as error:
        st.exception(error)
        return

    is_defective = label == "defective"
    st.subheader("Result")
    st.error("Status: DEFECTIVE") if is_defective else st.success("Status: NORMAL")
    st.metric("Confidence", f"{confidence:.1%}")
    st.caption("This result is a general device-status classification. YOLO detection should separately identify defect type and location.")


if __name__ == "__main__":
    main()
