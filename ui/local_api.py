"""FastAPI adapter for the TV1 classifier; no detection boxes are fabricated here."""

from __future__ import annotations

import io
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from model.inference import load_classifier, predict_preprocessed
from preprocessing.pipeline import PreprocessConfig, preprocess_image


DEFAULT_CHECKPOINT = Path("outputs/model_gaussian/defect_classifier.pt")
FALLBACK_CHECKPOINTS = [
    Path("outputs/model/defect_classifier.pt"),
    Path("outputs/model_baseline/defect_classifier.pt"),
    Path("outputs/model_median/defect_classifier.pt"),
    Path("outputs/model_clahe/defect_classifier.pt"),
]

app = FastAPI(
    title="Visual Defect Detection - Local API",
    description="TV1 CNN binary classifier. Detection bounding boxes are supplied later by TV2.",
    version="1.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_model = None
_config: PreprocessConfig | None = None
_classes: list[str] | None = None
_checkpoint_used = ""


def _find_checkpoint() -> Path | None:
    return next((path for path in [DEFAULT_CHECKPOINT, *FALLBACK_CHECKPOINTS] if path.exists()), None)


@app.on_event("startup")
async def load_model() -> None:
    """Load a checkpoint once; health remains available when none is present."""
    global _model, _config, _classes, _checkpoint_used
    if _model is not None:
        return
    checkpoint_path = _find_checkpoint()
    if checkpoint_path is None:
        return
    _model, _config, _classes = load_classifier(checkpoint_path)
    _checkpoint_used = str(checkpoint_path)


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    checkpoint: str


class ClassifierResult(BaseModel):
    label: str
    confidence: float
    normal_probability: float
    threshold: float


class PredictResponse(BaseModel):
    # Flat fields keep the original TV1 client contract working.
    label: str
    confidence: float
    preprocessing_ms: float
    inference_ms: float
    # This object is the join point for the future detection-result adapter.
    classifier_result: ClassifierResult


@app.get("/health", response_model=HealthResponse, tags=["Utility"])
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", model_loaded=_model is not None, checkpoint=_checkpoint_used)


@app.post("/predict", response_model=PredictResponse, tags=["Inference"])
async def predict(image: UploadFile = File(..., description="JPG/PNG image")) -> PredictResponse:
    """Preprocess exactly once, then time only the classifier forward pass."""
    if _model is None or _config is None or _classes is None:
        raise HTTPException(status_code=503, detail="Model has not been loaded.")
    contents = await image.read()
    try:
        with Image.open(io.BytesIO(contents)) as source:
            pil_image = source.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Cannot read image: {exc}") from exc

    start = time.perf_counter()
    array = preprocess_image(pil_image, _config)
    preprocessing_ms = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    label, confidence, normal_probability = predict_preprocessed(array, _model, _classes)
    inference_ms = (time.perf_counter() - start) * 1000
    threshold = float(getattr(_model, "decision_threshold", 0.5))
    classifier_result = ClassifierResult(
        label=label,
        confidence=round(confidence, 6),
        normal_probability=round(normal_probability, 6),
        threshold=round(threshold, 6),
    )
    return PredictResponse(
        label=classifier_result.label,
        confidence=classifier_result.confidence,
        preprocessing_ms=round(preprocessing_ms, 2),
        inference_ms=round(inference_ms, 2),
        classifier_result=classifier_result,
    )
