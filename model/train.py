"""Train a reproducible binary CNN and calibrate its validation threshold."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import torch
from torch import nn

from model.cnn import DefectCNN
from model.data import make_loader
from model.metrics import binary_metrics, calibrate_normal_threshold, predictions_from_normal_probabilities
from preprocessing.pipeline import PreprocessConfig
from preprocessing.statistics import compute_train_mean_std


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def collect_predictions(model: nn.Module, loader, loss_fn: nn.Module, device: torch.device) -> tuple[float, list[int], list[float]]:
    """Return loss, labels and P(normal), without deciding a threshold yet."""
    model.eval()
    total_loss, labels, normal_probabilities = 0.0, [], []
    with torch.no_grad():
        for images, targets in loader:
            images, targets = images.to(device), targets.float().to(device)
            logits = model(images)
            total_loss += loss_fn(logits, targets).item() * len(targets)
            labels.extend(targets.int().cpu().tolist())
            normal_probabilities.extend(torch.sigmoid(logits).cpu().tolist())
    return total_loss / len(loader.dataset), labels, normal_probabilities


def evaluate_loader(model: nn.Module, loader, loss_fn: nn.Module, device: torch.device, threshold: float = 0.5) -> tuple[float, dict]:
    """Evaluate a loader at a specified P(normal) cutoff."""
    loss, labels, normal_probabilities = collect_predictions(model, loader, loss_fn, device)
    return loss, binary_metrics(labels, predictions_from_normal_probabilities(normal_probabilities, threshold))


def train(args: argparse.Namespace) -> Path:
    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    base_config = PreprocessConfig(
        image_size=args.image_size, filter_name=args.filter_name, filter_kernel=args.filter_kernel,
        contrast_enhancement=args.contrast_enhancement, clahe_clip_limit=args.clahe_clip_limit,
        clahe_tile_grid_size=args.clahe_tile_grid_size,
    )
    mean, std = compute_train_mean_std(Path(args.data_dir) / "train", base_config)
    config = replace(base_config, normalization_mean=mean, normalization_std=std)
    train_loader = make_loader(Path(args.data_dir) / "train", config, args.batch_size, shuffle=True, augment=True)
    val_loader = make_loader(Path(args.data_dir) / "val", config, args.batch_size, shuffle=False)
    model = DefectCNN().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=args.lr_step_size, gamma=args.lr_gamma)
    loss_fn = nn.BCEWithLogitsLoss()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = output_dir / "defect_classifier.pt"
    history, best_f1 = [], -1.0

    for epoch in range(1, args.epochs + 1):
        model.train()
        running_loss = 0.0
        for images, targets in train_loader:
            images, targets = images.to(device), targets.float().to(device)
            optimizer.zero_grad()
            loss = loss_fn(model(images), targets)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * len(targets)

        val_loss, labels, probabilities = collect_predictions(model, val_loader, loss_fn, device)
        default_metrics = binary_metrics(labels, predictions_from_normal_probabilities(probabilities, 0.5))
        threshold, calibrated_metrics = calibrate_normal_threshold(labels, probabilities)
        history.append({
            "epoch": epoch, "train_loss": running_loss / len(train_loader.dataset), "val_loss": val_loss,
            "learning_rate": optimizer.param_groups[0]["lr"], "default_threshold": 0.5,
            "default": default_metrics, "selected_threshold": threshold, "selected": calibrated_metrics,
        })
        print(f"Epoch {epoch:03d}/{args.epochs}: val_loss={val_loss:.4f}, F1@0.5={default_metrics['f1_defective']:.4f}, F1@{threshold:.4f}={calibrated_metrics['f1_defective']:.4f}")
        if calibrated_metrics["f1_defective"] > best_f1:
            best_f1 = calibrated_metrics["f1_defective"]
            torch.save({
                "model_state": model.state_dict(), "preprocess": asdict(config),
                "classes": train_loader.dataset.classes, "threshold": threshold,
                "calibration": {"split": "val", "default_threshold": 0.5, "default_metrics": default_metrics, "selected_metrics": calibrated_metrics},
                "training": {"seed": args.seed, "augmentation": "RandomHorizontalFlip, RandomRotation(10), ColorJitter(0.12)", "scheduler": {"name": "StepLR", "step_size": args.lr_step_size, "gamma": args.lr_gamma}},
            }, checkpoint)
        scheduler.step()

    (output_dir / "training_history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    return checkpoint


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-dir", default="outputs/model")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--lr-step-size", type=int, default=8)
    parser.add_argument("--lr-gamma", type=float, default=0.5)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--filter-name", choices=["none", "gaussian", "median"], default="none")
    parser.add_argument("--filter-kernel", type=int, default=5)
    parser.add_argument("--contrast-enhancement", action="store_true")
    parser.add_argument("--clahe-clip-limit", type=float, default=2.0)
    parser.add_argument("--clahe-tile-grid-size", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cpu", action="store_true")
    checkpoint_path = train(parser.parse_args())
    print(f"Saved best model to {checkpoint_path}")
