"""Load a trained checkpoint and classify one image."""

from __future__ import annotations

from pathlib import Path

import torch
from PIL import Image

from model.cnn import DefectCNN
from preprocessing.pipeline import PreprocessConfig, preprocess_image


def load_classifier(checkpoint_path: str | Path, device: str = "cpu") -> tuple[DefectCNN, PreprocessConfig, list[str]]:
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model = DefectCNN().to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model, PreprocessConfig(**checkpoint["preprocess"]), checkpoint["classes"]


def predict_image(image: Image.Image, model: DefectCNN, config: PreprocessConfig, classes: list[str], device: str = "cpu") -> tuple[str, float]:
    """Return class name and its confidence. Model logit encodes ImageFolder class index 1."""
    array = preprocess_image(image, config)
    tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0).to(device)
    with torch.no_grad():
        normal_probability = torch.sigmoid(model(tensor)).item()
    index = int(normal_probability >= 0.5)
    confidence = normal_probability if index == 1 else 1.0 - normal_probability
    return classes[index], confidence
