"""Load a trained checkpoint and classify one image."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from PIL import Image

from model.cnn import DefectCNN
from preprocessing.pipeline import PreprocessConfig, preprocess_image


def load_classifier(checkpoint_path: str | Path, device: str = "cpu") -> tuple[DefectCNN, PreprocessConfig, list[str]]:
    """Load current or legacy checkpoints; missing fields use safe old defaults."""
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model = DefectCNN().to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    preprocess = checkpoint.get("preprocess", {})
    config = PreprocessConfig(**preprocess) if preprocess else PreprocessConfig()
    classes = checkpoint.get("classes", ["defective", "normal"])
    # Keep the public three-value return shape used by existing consumers.
    model.decision_threshold = float(checkpoint.get("threshold", 0.5))
    return model, config, classes


def predict_preprocessed(
    array: np.ndarray, model: DefectCNN, classes: list[str], device: str = "cpu"
) -> tuple[str, float, float]:
    """Classify a preprocessed HWC float array and return label, confidence, P(normal)."""
    tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0).to(device)
    with torch.no_grad():
        normal_probability = float(torch.sigmoid(model(tensor)).item())
    threshold = float(getattr(model, "decision_threshold", 0.5))
    index = int(normal_probability >= threshold)
    confidence = normal_probability if index == 1 else 1.0 - normal_probability
    return classes[index], confidence, normal_probability


def predict_image(
    image: Image.Image, model: DefectCNN, config: PreprocessConfig, classes: list[str], device: str = "cpu"
) -> tuple[str, float]:
    """Return class name and confidence using the checkpoint's calibrated cutoff."""
    label, confidence, _ = predict_preprocessed(preprocess_image(image, config), model, classes, device)
    return label, confidence
