"""Metrics shared by validation and held-out test evaluation."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, precision_recall_fscore_support


def binary_metrics(labels: list[int], predictions: list[int]) -> dict[str, Any]:
    """Return metrics where class 0=defective and class 1=normal (ImageFolder ordering)."""
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predictions, average="binary", pos_label=0, zero_division=0
    )
    matrix = confusion_matrix(labels, predictions, labels=[0, 1])
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision_defective": float(precision),
        "recall_defective": float(recall),
        "f1_defective": float(f1),
        "confusion_matrix": matrix.tolist(),
        "classification_report": classification_report(
            labels, predictions, labels=[0, 1], target_names=["defective", "normal"], zero_division=0, output_dict=True
        ),
    }


def false_negative_count(labels: list[int], predictions: list[int]) -> int:
    """Count defective images predicted normal—the high-risk error for quality control."""
    return int(np.sum((np.asarray(labels) == 0) & (np.asarray(predictions) == 1)))
