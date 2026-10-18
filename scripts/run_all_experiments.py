"""
Chay 4 cau hinh training va evaluate, ghi ket qua vao summary.json.
Chay: python scripts/run_all_experiments.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PYTHON = sys.executable
DATA_DIR = "data"
EPOCHS = 15

EXPERIMENTS = [
    {
        "name": "baseline",
        "output_dir": "outputs/model_baseline",
        "eval_dir":   "outputs/eval_baseline",
        "extra_args": [],
    },
    {
        "name": "gaussian",
        "output_dir": "outputs/model_gaussian",
        "eval_dir":   "outputs/eval_gaussian",
        "extra_args": ["--filter-name", "gaussian", "--filter-kernel", "5"],
    },
    {
        "name": "median",
        "output_dir": "outputs/model_median",
        "eval_dir":   "outputs/eval_median",
        "extra_args": ["--filter-name", "median", "--filter-kernel", "5"],
    },
    {
        "name": "clahe",
        "output_dir": "outputs/model_clahe",
        "eval_dir":   "outputs/eval_clahe",
        "extra_args": ["--contrast-enhancement"],
    },
]


def run(cmd: list[str]) -> int:
    print(f"\n>>> {' '.join(cmd)}\n")
    result = subprocess.run(cmd, text=True)
    return result.returncode


summary: list[dict] = []

for exp in EXPERIMENTS:
    print(f"\n{'='*60}")
    print(f"TRAINING: {exp['name'].upper()}")
    print(f"{'='*60}")

    train_cmd = [
        PYTHON, "-m", "model.train",
        "--data-dir", DATA_DIR,
        "--output-dir", exp["output_dir"],
        "--epochs", str(EPOCHS),
        *exp["extra_args"],
    ]
    rc = run(train_cmd)
    if rc != 0:
        print(f"[ERROR] Training failed for {exp['name']} (exit {rc})")
        continue

    checkpoint = Path(exp["output_dir"]) / "defect_classifier.pt"
    if not checkpoint.exists():
        print(f"[ERROR] Checkpoint not found: {checkpoint}")
        continue

    print(f"\n{'='*60}")
    print(f"EVALUATE: {exp['name'].upper()}")
    print(f"{'='*60}")

    eval_cmd = [
        PYTHON, "-m", "model.evaluate",
        "--checkpoint", str(checkpoint),
        "--data-dir", DATA_DIR,
        "--output-dir", exp["eval_dir"],
    ]
    rc = run(eval_cmd)
    if rc != 0:
        print(f"[ERROR] Evaluation failed for {exp['name']} (exit {rc})")
        continue

    metrics_file = Path(exp["eval_dir"]) / "test_metrics.json"
    if metrics_file.exists():
        metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
        row = {
            "config": exp["name"],
            "accuracy":            round(metrics.get("accuracy", 0), 4),
            "precision_defective": round(metrics.get("precision_defective", 0), 4),
            "recall_defective":    round(metrics.get("recall_defective", 0), 4),
            "f1_defective":        round(metrics.get("f1_defective", 0), 4),
            "false_negative":      metrics.get("false_negative_defective", "?"),
        }
        summary.append(row)
        print(f"\n[RESULT] {exp['name']}: acc={row['accuracy']}, "
              f"f1={row['f1_defective']}, FN={row['false_negative']}")

# --- In bang tong ket ---
print(f"\n{'='*60}")
print("SUMMARY TABLE")
print(f"{'='*60}")
header = f"{'Config':<12} {'Accuracy':>9} {'Precision':>10} {'Recall':>8} {'F1':>8} {'FalseNeg':>10}"
print(header)
print("-" * len(header))
for r in summary:
    print(f"{r['config']:<12} {r['accuracy']:>9.4f} {r['precision_defective']:>10.4f} "
          f"{r['recall_defective']:>8.4f} {r['f1_defective']:>8.4f} {r['false_negative']:>10}")

# --- Luu summary ---
summary_path = Path("outputs") / "experiment_summary.json"
summary_path.parent.mkdir(exist_ok=True)
summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n[SAVED] Summary -> {summary_path}")

if summary:
    best = max(summary, key=lambda x: x["f1_defective"])
    print(f"\n[BEST CONFIG] {best['config']} — F1={best['f1_defective']}, "
          f"FN={best['false_negative']}")
    print("\n[NEXT] Viet tai lieu Phase 7 trong docs/phase-07-cnn-classifier.md")
