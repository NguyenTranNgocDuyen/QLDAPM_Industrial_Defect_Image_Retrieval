# TV1 — Classification & Preprocessing: demo boundary

## What is ready for a preprocessing demo

The offline TV1 tools demonstrate aspect-preserving resize/letterbox, Gaussian
and median filtering, RGB/grayscale histograms, CLAHE luminance enhancement,
and reproducible image-quality A/B artifacts. They are report/demo tools only.

```powershell
cd image-processing
$env:PYTHONPATH=".."
.venv\Scripts\python scripts\smoke_tv1_decode.py
.venv\Scripts\python -m preprocessing.experiment data\123k.jpeg --output-dir ..\outputs\preprocessing-experiment
.venv\Scripts\python -m defect_vision.preprocess_benchmark data\123k.jpeg --output-dir ..\outputs\preprocess-benchmark
.venv\Scripts\python -m pytest tests\test_tv1_preprocessing.py -q
```

The experiment contains original, letterboxed resize, Gaussian, median, CLAHE,
histograms (PNG + JSON), and a comparison board. The benchmark emits one PNG
per `raw`, `gaussian`, `median`, `clahe`, `gamma`, `background`, and `combined`
preset plus JSON/CSV with latency, parameters, and config SHA-256.

## Runtime boundary (must not be changed by TV1)

Phone runtime is exactly: `decode_upright_rgb` -> `PhoneSegmenter` ->
`ROIDamageEngine.predict_with_body(raw upright RGB, source-resolution body mask)`.
It does not resize an image to 224 or 512 before v3 inference and does not put
Gaussian, median, CLAHE, gamma, or background correction in the v3 input.
The protocol remains threshold 0.4, patch 512, overlap 128, context 512,
body margin 0, and `inference_variant=native`.

## Evaluation blocker

This repository does not provide a licensed, independently split annotated
dataset or a trained binary CNN classifier. Therefore it must not claim
Normal/Defective CNN classification, trained YOLO performance, confusion
matrix, ROC-AUC, or model-quality metrics. Before any model-evaluation claim,
create a manifest with source/license, image and both masks, SHA-256, group ID,
and an independent test split, then run:

```powershell
.venv\Scripts\python scripts\validate_manifest.py path\to\manifest.csv
```

Only after that, evaluate a real checkpoint against the independent test set
with the metrics specified in `docs/TV1_EVALUATION_REQUIREMENTS.md`.
