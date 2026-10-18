from __future__ import annotations

import torch

from model.cnn import DefectCNN
from model.inference import load_classifier


def test_legacy_checkpoint_uses_normalization_and_threshold_fallbacks(tmp_path) -> None:
    checkpoint_path = tmp_path / "legacy.pt"
    model = DefectCNN()
    torch.save({"model_state": model.state_dict(), "preprocess": {"image_size": 32, "filter_name": "none", "filter_kernel": 5, "contrast_enhancement": False}, "classes": ["defective", "normal"]}, checkpoint_path)
    loaded, config, classes = load_classifier(checkpoint_path)
    assert loaded.decision_threshold == 0.5
    assert config.normalization_mean is None
    assert classes == ["defective", "normal"]
