"""CPU inference benchmark with warm-up and percentile summary."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

from model.inference import load_classifier, predict_preprocessed
from preprocessing.pipeline import preprocess_image


def summarize(values: list[float]) -> dict[str, float]:
    return {"p50_ms": round(float(np.percentile(values, 50)), 3), "p95_ms": round(float(np.percentile(values, 95)), 3), "mean_ms": round(float(np.mean(values)), 3)}


def find_sample(data_dir: Path) -> Path:
    return next(path for path in sorted((data_dir / "test").rglob("*")) if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=Path("outputs/model_gaussian/defect_classifier.pt"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--image", type=Path)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.runs < 30:
        raise ValueError("--runs must be at least 30.")
    model, config, classes = load_classifier(args.checkpoint, device="cpu")
    image_path = args.image or find_sample(args.data_dir)
    with Image.open(image_path) as image:
        source = image.convert("RGB")
    array = preprocess_image(source, config)
    for _ in range(args.warmup):
        predict_preprocessed(array, model, classes)
    timings = []
    for _ in range(args.runs):
        started = time.perf_counter()
        predict_preprocessed(array, model, classes)
        timings.append((time.perf_counter() - started) * 1000)
    report = {"checkpoint": str(args.checkpoint), "sample": str(image_path), "device": "cpu", "warmup_runs": args.warmup, "measured_runs": args.runs, "inference": summarize(timings)}
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
