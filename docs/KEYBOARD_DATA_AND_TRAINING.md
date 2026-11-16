# Keyboard data and training

The feature has two separate data roles. `keyboard-key-detection` is keycap/grid
data only. `bsx-keyboard-defect` is a binary `keyboard_defect` dataset only.
RSI is an exact subset of BSX and is retained only as provenance.

## Prepare

```powershell
python scripts/prepare_keyboard_datasets.py
```

This preserves all files under `datasets/keyboard/external` and produces manifests,
YOLO labels, and `datasets/keyboard/derived/audit-report.json`.

## Binary defect training

Install Ultralytics and a compatible PyTorch build in a dedicated environment, then:

```powershell
python scripts/train_keyboard_defect_detector.py --epochs 50
```

The command records data configuration hash and training options before invoking
Ultralytics. It does not load phone models. A checkpoint is not considered present
until the trainer has completed and written its output.

## Scientific limits

The BSX labels are generic `keyboard_defect`; they cannot justify metrics for
`missing_key`, `shifted_key`, or `tilted_key`. Those labels in the runtime are
evidence-gated OpenCV geometry heuristics. A generic binary model, if later loaded,
must report `uncertain` rather than one of the three specific labels.
