"""Train the CNN on data/train and select the best checkpoint using data/val."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch
from torch import nn

from model.cnn import DefectCNN
from model.data import make_loader
from model.metrics import binary_metrics
from preprocessing.pipeline import PreprocessConfig


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def evaluate_loader(model: nn.Module, loader, loss_fn: nn.Module, device: torch.device) -> tuple[float, dict]:
    model.eval()
    total_loss, labels, predictions = 0.0, [], []
    with torch.no_grad():
        for images, targets in loader:
            images, targets = images.to(device), targets.float().to(device)
            logits = model(images)
            total_loss += loss_fn(logits, targets).item() * len(targets)
            labels.extend(targets.int().cpu().tolist())
            predictions.extend((torch.sigmoid(logits) >= 0.5).int().cpu().tolist())
    return total_loss / len(loader.dataset), binary_metrics(labels, predictions)


def train(args: argparse.Namespace) -> Path:
    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    config = PreprocessConfig(args.image_size, args.filter_name, args.filter_kernel, args.contrast_enhancement)
    train_loader = make_loader(Path(args.data_dir) / "train", config, args.batch_size, shuffle=True)
    val_loader = make_loader(Path(args.data_dir) / "val", config, args.batch_size, shuffle=False)
    model = DefectCNN().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
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
        val_loss, metrics = evaluate_loader(model, val_loader, loss_fn, device)
        record = {"epoch": epoch, "train_loss": running_loss / len(train_loader.dataset), "val_loss": val_loss, **metrics}
        history.append(record)
        print(f"Epoch {epoch:03d}/{args.epochs}: val_loss={val_loss:.4f}, defect_f1={metrics['f1_defective']:.4f}")
        if metrics["f1_defective"] > best_f1:
            best_f1 = metrics["f1_defective"]
            torch.save({"model_state": model.state_dict(), "preprocess": asdict(config), "classes": train_loader.dataset.classes}, checkpoint)

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
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--filter-name", choices=["none", "gaussian", "median"], default="none")
    parser.add_argument("--filter-kernel", type=int, default=5)
    parser.add_argument("--contrast-enhancement", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cpu", action="store_true")
    checkpoint_path = train(parser.parse_args())
    print(f"Saved best model to {checkpoint_path}")
