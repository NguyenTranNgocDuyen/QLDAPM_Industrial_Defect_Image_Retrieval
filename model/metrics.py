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


def predictions_from_normal_probabilities(
    normal_probabilities: list[float] | np.ndarray, threshold: float
) -> list[int]:
    """Map P(normal) to ImageFolder indices: 0=defective, 1=normal."""
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be in [0, 1].")
    return (np.asarray(normal_probabilities) >= threshold).astype(int).tolist()


def calibrate_normal_threshold(
    labels: list[int], normal_probabilities: list[float]
) -> tuple[float, dict[str, Any]]:
    """Choose the P(normal) cutoff maximizing defective F1 on validation data.

    Ties select the lower cutoff, a conservative QC choice that sends more
    uncertain images to the defective path.
    """
    if len(labels) != len(normal_probabilities) or not labels:
        raise ValueError("labels and normal_probabilities must be non-empty and equally sized.")
    candidates = sorted({0.0, 0.5, 1.0, *[float(value) for value in normal_probabilities]})
    best_threshold = 0.5
    best_metrics = binary_metrics(
        labels, predictions_from_normal_probabilities(normal_probabilities, best_threshold)
    )
    for threshold in candidates:
        metrics = binary_metrics(labels, predictions_from_normal_probabilities(normal_probabilities, threshold))
        if (metrics["f1_defective"], -threshold) > (
            best_metrics["f1_defective"], -best_threshold
        ):
            best_threshold, best_metrics = threshold, metrics
    return float(best_threshold), best_metrics
