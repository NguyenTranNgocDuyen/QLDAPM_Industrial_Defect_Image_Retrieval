"""Evaluate the saved classifier on the untouched data/test split."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import torch
from torch import nn

from model.data import make_loader
from model.metrics import binary_metrics, false_negative_count
from model.train import evaluate_loader
from model.inference import load_classifier


def save_confusion_matrix(matrix: list[list[int]], output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5, 4))
    image = ax.imshow(matrix, cmap="Blues")
    for row in range(2):
        for col in range(2):
            ax.text(col, row, str(matrix[row][col]), ha="center", va="center")
    ax.set(xticks=[0, 1], yticks=[0, 1], xticklabels=["defective", "normal"], yticklabels=["defective", "normal"], xlabel="Prediction", ylabel="Actual", title="Confusion matrix")
    fig.colorbar(image, ax=ax)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def evaluate(checkpoint: str | Path, data_dir: str | Path, output_dir: str | Path, batch_size: int) -> dict:
    model, config, _ = load_classifier(checkpoint)
    loader = make_loader(Path(data_dir) / "test", config, batch_size, shuffle=False)
    _, metrics = evaluate_loader(model, loader, nn.BCEWithLogitsLoss(), torch.device("cpu"))
    labels, predictions = [], []
    model.eval()
    with torch.no_grad():
        for images, targets in loader:
            logits = model(images)
            labels.extend(targets.int().tolist())
            predictions.extend((torch.sigmoid(logits) >= 0.5).int().tolist())
    metrics["false_negative_defective"] = false_negative_count(labels, predictions)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "test_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    save_confusion_matrix(metrics["confusion_matrix"], output_dir / "confusion_matrix.png")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", default="outputs/model/defect_classifier.pt")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-dir", default="outputs/evaluation")
    parser.add_argument("--batch-size", type=int, default=16)
    result = evaluate(**vars(parser.parse_args()))
    print(json.dumps({key: value for key, value in result.items() if key != "classification_report"}, indent=2))
