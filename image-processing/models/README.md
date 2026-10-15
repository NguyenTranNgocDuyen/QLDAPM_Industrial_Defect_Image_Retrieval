# Model Weights Directory

This directory stores trained deep learning weights for phone segmentation and perspective correction.

> [!NOTE]
> Large weight files (`*.pt`, `*.onnx`, etc.) are ignored by git to comply with GitHub's 100MB file limit.

---

## How to Get the Phone Segmentation Model

You have 3 easy ways to obtain or use the model:

### Option 1: Automatic Download via Roboflow (Recommended)
When someone clones the repository, they don't need to manually download weights.
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Put your Roboflow API Key into `.env`:
   ```env
   ROBOFLOW_API_KEY=your_key_here
   ROBOFLOW_PHONE_MODEL_ID=phone-segmentation-uiymg/1
   ```
3. Run the pipeline with `--auto-perspective`. On the first run, the model will be automatically downloaded to your local cache (`~/.cache/inference`) and used for inference:
   ```bash
   python -m defect_vision.pipeline_cli --input data/394k.jpeg --auto-perspective --method clahe --output-dir outputs/run-394k
   ```

---

### Option 2: Pre-download via Script
To pre-download and verify the model before running the pipeline:
```bash
python scripts/download_model.py
```
Or pass the API key directly:
```bash
python scripts/download_model.py --api-key your_roboflow_api_key
```

If you host `weights.pt` on Google Drive, GitHub Releases, or Hugging Face, you can also download directly:
```bash
python scripts/download_model.py --url "https://your-storage-host.com/weights.pt"
```

---

### Option 3: Manual / Offline Placement
If you have the original `weights.pt` file from training:
Simply place it directly in this directory:
```
image-processing/models/weights.pt
```
The system will automatically detect and prioritize local weights for fast, offline inference without network requests.
