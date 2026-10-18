from __future__ import annotations

import io

import numpy as np
import pytest
import torch
from PIL import Image

pytest.importorskip("fastapi", reason="Install requirements.txt/tv1.txt to run API endpoint tests.")
from fastapi.testclient import TestClient

import ui.local_api as api
from preprocessing.pipeline import PreprocessConfig


class ConstantNormalModel(torch.nn.Module):
    decision_threshold = 0.5

    def forward(self, tensor):
        return torch.full((len(tensor),), 2.0)


def image_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(np.full((12, 12, 3), 120, dtype=np.uint8), "RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def test_health_and_predict_preprocess_once(monkeypatch) -> None:
    api._model = ConstantNormalModel().eval()
    api._config = PreprocessConfig(image_size=8)
    api._classes = ["defective", "normal"]
    api._checkpoint_used = "test.pt"
    calls = 0
    original = api.preprocess_image

    def counted(image, config):
        nonlocal calls
        calls += 1
        return original(image, config)

    monkeypatch.setattr(api, "preprocess_image", counted)
    with TestClient(api.app) as client:
        health = client.get("/health")
        response = client.post("/predict", files={"image": ("sample.png", image_bytes(), "image/png")})
    assert health.json()["model_loaded"] is True
    assert response.status_code == 200
    body = response.json()
    assert calls == 1
    assert body["label"] == "normal"
    assert body["classifier_result"]["threshold"] == 0.5
    assert body["preprocessing_ms"] >= 0
    assert body["inference_ms"] >= 0


def test_predict_rejects_invalid_image() -> None:
    api._model = ConstantNormalModel().eval()
    api._config = PreprocessConfig(image_size=8)
    api._classes = ["defective", "normal"]
    with TestClient(api.app) as client:
        response = client.post("/predict", files={"image": ("bad.txt", b"not an image", "text/plain")})
    assert response.status_code == 400
