"""End-to-end preprocessing pipeline for electronic-device defect inspection.

Coordinates perspective correction, illumination balancing, color space analysis,
and quantitative before/after evaluation into a unified workflow.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Sequence

import cv2
import numpy as np
from numpy.typing import NDArray

from .colorspace import (
    compute_channel_stats,
    extract_all_defect_channels,
    make_channel_comparison_grid,
)
from .comparison import (
    EnhancementComparisonRecord,
    evaluate_enhancement_pair,
    make_before_after_comparison_board,
)
from .illumination import (
    IlluminationMethod,
    IlluminationResult,
    correct_illumination,
)
from .image_io import write_image
from .perspective import (
    PerspectiveResult,
    correct_perspective,
    detect_device_corners,
    draw_corners,
    make_before_after,
)
from .yolo_baseline import (
    Detector,
    YoloBaselineConfig,
    build_detector,
    run_baseline_inference,
)

Image = NDArray[np.uint8]


class PipelineError(ValueError):
    """Raised when pipeline input, configuration, or processing fails."""


@dataclass(frozen=True)
class PipelineConfig:
    """Configuration options for the full preprocessing pipeline."""

    points: Sequence[tuple[float, float]] | None = None
    auto_perspective: bool = False
    perspective_model_path: str | None = None
    perspective_model_id: str = "phone-segmentation-uiymg/1"
    roboflow_api_key: str | None = None
    illumination_method: IlluminationMethod | str = "clahe"
    gamma: float | None = None
    target_mean: float = 128.0
    clip_limit: float = 2.0
    grid_size: int = 8
    background_kernel: int = 201
    run_yolo: bool = False
    mock_yolo: bool = False
    yolo_model_path: str = "models/yolo-baseline.pt"
    yolo_confidence: float = 0.25
    yolo_iou: float = 0.45
    yolo_imgsz: int = 640
    yolo_device: str = "cpu"


@dataclass(frozen=True)
class PipelineResult:
    """Output artifacts and metrics produced by the full pipeline."""

    original_image: Image
    preprocessed_image: Image
    perspective_result: PerspectiveResult | None
    illumination_result: IlluminationResult | None
    colorspace_channels: dict[str, Image]
    colorspace_stats: dict[str, dict[str, float | int | str]]
    comparison_record: EnhancementComparisonRecord
    yolo_result: dict[str, object] | None
    yolo_annotated_image: Image | None
    timings_ms: dict[str, float]

    def to_dict(self) -> dict[str, object]:
        summary: dict[str, object] = {
            "timings_ms": {k: round(v, 3) for k, v in self.timings_ms.items()},
            "comparison": self.comparison_record.to_dict(),
            "colorspace_channel_stats": self.colorspace_stats,
        }
        if self.perspective_result is not None:
            summary["perspective"] = {
                "elapsed_ms": round(self.perspective_result.elapsed_ms, 3),
                "output_width": self.perspective_result.output_width,
                "output_height": self.perspective_result.output_height,
                "ordered_corners": self.perspective_result.ordered_corners.round(3).tolist(),
                "transform_matrix": self.perspective_result.transform_matrix.round(8).tolist(),
            }
        if self.illumination_result is not None:
            summary["illumination"] = {
                "method": self.illumination_result.method,
                "elapsed_ms": round(self.illumination_result.elapsed_ms, 3),
                "before": self.illumination_result.before.to_dict(),
                "after": self.illumination_result.after.to_dict(),
                "parameters": self.illumination_result.parameters,
            }
        if self.yolo_result is not None:
            summary["yolo"] = self.yolo_result
        return summary


def run_preprocessing_pipeline(
    image: Image,
    config: PipelineConfig | None = None,
) -> PipelineResult:
    """Execute end-to-end preprocessing pipeline on an input image."""
    if config is None:
        config = PipelineConfig()

    if not isinstance(image, np.ndarray) or image.size == 0:
        raise PipelineError("Input image must be a non-empty numpy array.")
    if image.dtype != np.uint8:
        raise PipelineError("Input image must have dtype uint8.")
    if image.ndim not in (2, 3):
        raise PipelineError("Input image must be grayscale or color.")

    # Ensure 3-channel BGR for downstream consistency
    if image.ndim == 2:
        current_image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.shape[2] == 4:
        current_image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    else:
        current_image = image.copy()

    original_input = current_image.copy()
    timings: dict[str, float] = {}

    # Stage 1: Perspective Correction (explicit points or auto-detected corners)
    persp_result: PerspectiveResult | None = None
    target_points = config.points
    if target_points is None and config.auto_perspective:
        target_points = detect_device_corners(
            current_image,
            segmentation_model=config.perspective_model_path,
            model_id=config.perspective_model_id,
            api_key=config.roboflow_api_key,
        )

    if target_points is not None:
        t0 = perf_counter()
        persp_result = correct_perspective(current_image, target_points)
        current_image = persp_result.image
        timings["perspective_ms"] = (perf_counter() - t0) * 1000.0
    elif config.auto_perspective or config.points:
        print("[Pipeline] Warning: Could not obtain 4 device corners. Perspective correction was skipped.")

    # Stage 2: Illumination Correction
    illum_result: IlluminationResult | None = None
    if config.illumination_method and config.illumination_method != "none":
        t0 = perf_counter()
        illum_result = correct_illumination(
            current_image,
            method=config.illumination_method,  # type: ignore[arg-type]
            gamma=config.gamma,
            target_mean=config.target_mean,
            clip_limit=config.clip_limit,
            grid_size=config.grid_size,
            background_kernel=config.background_kernel,
        )
        current_image = illum_result.image
        timings["illumination_ms"] = (perf_counter() - t0) * 1000.0

    # Stage 3: Color Space Analysis
    t0 = perf_counter()
    extracted_channels = extract_all_defect_channels(current_image)
    channel_stats = {
        name: compute_channel_stats(ch, name).to_dict()
        for name, ch in extracted_channels.items()
    }
    timings["colorspace_ms"] = (perf_counter() - t0) * 1000.0

    # Stage 4: Quantitative Before & After Evaluation
    t0 = perf_counter()
    comp_record = evaluate_enhancement_pair(
        original=original_input,
        enhanced=current_image,
        technique_name=f"Full Pipeline ({config.illumination_method})",
        elapsed_ms=sum(timings.values()),
    )
    timings["quality_eval_ms"] = (perf_counter() - t0) * 1000.0

    # Stage 5: Optional YOLO Inference
    yolo_result: dict[str, object] | None = None
    yolo_annotated: Image | None = None
    if config.run_yolo or config.mock_yolo:
        t0 = perf_counter()
        detector_config = YoloBaselineConfig(
            model_path=config.yolo_model_path,
            confidence=config.yolo_confidence,
            iou=config.yolo_iou,
            imgsz=config.yolo_imgsz,
            device=config.yolo_device,
        )
        detector = build_detector(detector_config, mock=config.mock_yolo)
        yolo_result, yolo_annotated = run_baseline_inference(
            image=current_image,
            detector=detector,
            source_url="preprocessed_input",
            display_url="06_yolo_annotated.png",
        )
        timings["yolo_ms"] = (perf_counter() - t0) * 1000.0

    timings["total_pipeline_ms"] = sum(timings.values())

    return PipelineResult(
        original_image=original_input,
        preprocessed_image=current_image,
        perspective_result=persp_result,
        illumination_result=illum_result,
        colorspace_channels=extracted_channels,
        colorspace_stats=channel_stats,
        comparison_record=comp_record,
        yolo_result=yolo_result,
        yolo_annotated_image=yolo_annotated,
        timings_ms=timings,
    )


def save_pipeline_artifacts(result: PipelineResult, output_dir: Path) -> dict[str, Path]:
    """Save all intermediate and final pipeline images and summary metrics."""
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_files: dict[str, Path] = {}

    # 1. Original input
    p_orig = output_dir / "01_original.png"
    write_image(p_orig, result.original_image)
    saved_files["original"] = p_orig

    # 2. Perspective (if available)
    if result.perspective_result is not None:
        p_persp = output_dir / "02_perspective.png"
        write_image(p_persp, result.perspective_result.image)
        saved_files["perspective"] = p_persp

        corner_preview = draw_corners(result.original_image, result.perspective_result.ordered_corners)
        p_corners = output_dir / "02_selected_corners.png"
        write_image(p_corners, corner_preview)
        saved_files["selected_corners"] = p_corners

        board = make_before_after(corner_preview, result.perspective_result.image)
        p_persp_board = output_dir / "02_perspective_board.png"
        write_image(p_persp_board, board)
        saved_files["perspective_board"] = p_persp_board

    # 3. Illumination
    if result.illumination_result is not None:
        p_illum = output_dir / "03_illumination.png"
        write_image(p_illum, result.illumination_result.image)
        saved_files["illumination"] = p_illum

    # 4. Color space comparison grid
    grid = make_channel_comparison_grid(result.original_image, result.colorspace_channels)
    p_cs_grid = output_dir / "04_colorspace_grid.png"
    write_image(p_cs_grid, grid)
    saved_files["colorspace_grid"] = p_cs_grid

    # 5. Quality Comparison Board
    comp_board = make_before_after_comparison_board(
        original=result.original_image,
        enhanced=result.preprocessed_image,
        record=result.comparison_record,
    )
    p_comp_board = output_dir / "05_before_after_board.png"
    write_image(p_comp_board, comp_board)
    saved_files["comparison_board"] = p_comp_board

    # 6. Final preprocessed image (ready for downstream tasks)
    p_final = output_dir / "final_preprocessed.png"
    write_image(p_final, result.preprocessed_image)
    saved_files["final_preprocessed"] = p_final

    # 7. YOLO Annotated (if executed)
    if result.yolo_annotated_image is not None:
        p_yolo = output_dir / "06_yolo_annotated.png"
        write_image(p_yolo, result.yolo_annotated_image)
        saved_files["yolo_annotated"] = p_yolo

    # 8. Summary Report JSON
    p_report = output_dir / "pipeline_report.json"
    with open(p_report, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2)
    saved_files["report"] = p_report

    return saved_files
