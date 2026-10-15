# Phase 7 - YOLO Baseline

Phase 7 establishes the model boundary for the detector supplied by TV2. The
pipeline accepts a BGR `uint8` image, runs the detector, clips invalid boxes,
draws the processed image, and returns the shared `detection-result` contract
with `preprocessingMs`, `inferenceMs`, `postprocessingMs`, and `totalMs`.

## Run without a model

This mode is deterministic and is used for contract tests and UI integration:

```powershell
cd image-processing
$env:PYTHONPATH="."
python -m defect_vision.yolo_baseline_cli --mock
```

The command writes `outputs/yolo-baseline/annotated.png` and
`outputs/yolo-baseline/baseline_result.json`.

## Run the TV2 model

Install the optional runtime and provide the model file:

```powershell
python -m pip install -r requirements-yolo.txt
python -m defect_vision.yolo_baseline_cli `
  --input path\to\device.jpg `
  --model path\to\tv2-baseline.pt `
  --output-dir outputs\yolo-tv2
```

The adapter uses Ultralytics confidence, IoU, image-size, and device options.
No model is downloaded implicitly, so the exact TV2 weights remain explicit and
reproducible.

## Current boundary

Phase 7 provides model loading, inference, postprocessing, visualization, and
contract timing. Training, dataset splitting, model calibration, and accuracy
benchmarking require the TV2 dataset and weights and are the next integration
step after those artifacts are supplied.

