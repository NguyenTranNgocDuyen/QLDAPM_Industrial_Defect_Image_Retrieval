"""Illumination correction for electronic-device surface images."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Literal, Sequence

import cv2
import numpy as np
from numpy.typing import NDArray


Image = NDArray[np.uint8]
IlluminationMethod = Literal["gamma", "clahe", "background", "combined"]
SUPPORTED_METHODS: tuple[IlluminationMethod, ...] = (
    "gamma",
    "clahe",
    "background",
    "combined",
)


class IlluminationCorrectionError(ValueError):
    """Raised when illumination-correction input or parameters are invalid."""


@dataclass(frozen=True)
class LuminanceStats:
    mean: float
    std: float
    p05: float
    p95: float
    dark_fraction: float
    bright_fraction: float
    clipped_dark_fraction: float
    clipped_bright_fraction: float

    def to_dict(self) -> dict[str, float]:
        return {key: round(float(value), 4) for key, value in asdict(self).items()}


@dataclass(frozen=True)
class IlluminationResult:
    image: Image
    method: IlluminationMethod
    elapsed_ms: float
    before: LuminanceStats
    after: LuminanceStats
    parameters: dict[str, float | int]


def _validate_image(image: Image) -> None:
    if not isinstance(image, np.ndarray) or image.size == 0:
        raise IlluminationCorrectionError("Input image must be a non-empty array.")
    if image.dtype != np.uint8:
        raise IlluminationCorrectionError("Input image must use uint8 pixels.")
    if image.ndim not in (2, 3):
        raise IlluminationCorrectionError("Input image must be grayscale or color.")
    if image.ndim == 3 and image.shape[2] not in (1, 3, 4):
        raise IlluminationCorrectionError("Unsupported number of image channels.")


def _split_luminance(image: Image) -> tuple[Image, tuple[str, Image | None]]:
    """Return luminance and enough context to rebuild the source format."""
    if image.ndim == 2:
        return image.copy(), ("gray", None)
    if image.shape[2] == 1:
        return image[:, :, 0].copy(), ("gray-3d", None)

    if image.shape[2] == 4:
        bgr = image[:, :, :3]
        alpha = image[:, :, 3].copy()
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        return lab[:, :, 0].copy(), ("bgra", np.dstack((lab[:, :, 1:], alpha)))

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    return lab[:, :, 0].copy(), ("bgr", lab[:, :, 1:].copy())


def _merge_luminance(luminance: Image, context: tuple[str, Image | None]) -> Image:
    mode, chroma = context
    if mode == "gray":
        return luminance
    if mode == "gray-3d":
        return luminance[:, :, None]
    if mode == "bgr":
        assert chroma is not None
        lab = np.dstack((luminance, chroma))
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    if mode == "bgra":
        assert chroma is not None
        lab = np.dstack((luminance, chroma[:, :, :2]))
        bgr = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        return np.dstack((bgr, chroma[:, :, 2]))
    raise AssertionError(f"Unexpected image mode: {mode}")


def analyze_luminance(image: Image) -> LuminanceStats:
    """Measure brightness distribution on grayscale or LAB L channel."""
    _validate_image(image)
    luminance, _ = _split_luminance(image)
    values = luminance.astype(np.float32)
    return LuminanceStats(
        mean=float(values.mean()),
        std=float(values.std()),
        p05=float(np.percentile(values, 5)),
        p95=float(np.percentile(values, 95)),
        dark_fraction=float(np.mean(values < 40)),
        bright_fraction=float(np.mean(values > 215)),
        clipped_dark_fraction=float(np.mean(values <= 5)),
        clipped_bright_fraction=float(np.mean(values >= 250)),
    )


def estimate_gamma(image: Image, target_mean: float = 128.0) -> float:
    """Estimate gamma so the mean luminance moves toward the target."""
    _validate_image(image)
    if not 1.0 <= target_mean <= 254.0:
        raise IlluminationCorrectionError("target_mean must be between 1 and 254.")

    luminance, _ = _split_luminance(image)
    current = float(luminance.mean())
    if current <= 1.0 or current >= 254.0:
        return 1.0

    gamma = np.log(target_mean / 255.0) / np.log(current / 255.0)
    return float(np.clip(gamma, 0.4, 2.5))


def gamma_correction(
    image: Image,
    gamma: float | None = None,
    *,
    target_mean: float = 128.0,
) -> tuple[Image, float]:
    """Correct global brightness on luminance while preserving color channels."""
    _validate_image(image)
    actual_gamma = estimate_gamma(image, target_mean) if gamma is None else gamma
    if not np.isfinite(actual_gamma) or actual_gamma <= 0:
        raise IlluminationCorrectionError("gamma must be a positive finite number.")

    luminance, context = _split_luminance(image)
    lookup = np.clip(
        ((np.arange(256, dtype=np.float32) / 255.0) ** actual_gamma) * 255.0,
        0,
        255,
    ).astype(np.uint8)
    corrected = cv2.LUT(luminance, lookup)
    return _merge_luminance(corrected, context), float(actual_gamma)


def clahe_correction(
    image: Image,
    *,
    clip_limit: float = 2.0,
    grid_size: int = 8,
) -> Image:
    """Improve local luminance contrast with CLAHE on LAB L or grayscale."""
    _validate_image(image)
    if not np.isfinite(clip_limit) or clip_limit <= 0:
        raise IlluminationCorrectionError("clip_limit must be positive.")
    if grid_size < 2:
        raise IlluminationCorrectionError("grid_size must be at least 2.")

    luminance, context = _split_luminance(image)
    clahe = cv2.createCLAHE(
        clipLimit=float(clip_limit), tileGridSize=(grid_size, grid_size)
    )
    corrected = clahe.apply(luminance)
    return _merge_luminance(corrected, context)


def background_correction(image: Image, *, kernel_size: int = 201) -> Image:
    """Normalize slowly varying illumination using a blurred background model."""
    _validate_image(image)
    if kernel_size < 3 or kernel_size % 2 == 0:
        raise IlluminationCorrectionError(
            "kernel_size must be an odd integer greater than or equal to 3."
        )

    luminance, context = _split_luminance(image)
    luminance_float = luminance.astype(np.float32)
    background = cv2.GaussianBlur(
        luminance_float,
        (kernel_size, kernel_size),
        sigmaX=0,
        borderType=cv2.BORDER_REFLECT,
    )
    target = max(float(np.median(background)), 1.0)
    corrected = luminance_float * target / np.maximum(background, 1.0)
    corrected = np.clip(corrected, 0, 255).astype(np.uint8)
    return _merge_luminance(corrected, context)


def correct_illumination(
    image: Image,
    method: IlluminationMethod = "combined",
    *,
    gamma: float | None = None,
    target_mean: float = 128.0,
    clip_limit: float = 2.0,
    grid_size: int = 8,
    background_kernel: int = 201,
) -> IlluminationResult:
    """Run one correction method and return before/after metrics."""
    _validate_image(image)
    if method not in SUPPORTED_METHODS:
        raise IlluminationCorrectionError(
            f"Unsupported method '{method}'. Expected one of {SUPPORTED_METHODS}."
        )

    before = analyze_luminance(image)
    parameters: dict[str, float | int]
    started_at = perf_counter()

    if method == "gamma":
        corrected, actual_gamma = gamma_correction(
            image, gamma, target_mean=target_mean
        )
        parameters = {
            "gamma": round(actual_gamma, 6),
            "targetMean": float(target_mean),
        }
    elif method == "clahe":
        corrected = clahe_correction(
            image, clip_limit=clip_limit, grid_size=grid_size
        )
        parameters = {"clipLimit": float(clip_limit), "gridSize": grid_size}
    elif method == "background":
        corrected = background_correction(image, kernel_size=background_kernel)
        parameters = {"backgroundKernel": background_kernel}
    else:
        normalized = background_correction(image, kernel_size=background_kernel)
        corrected = clahe_correction(
            normalized, clip_limit=clip_limit, grid_size=grid_size
        )
        parameters = {
            "backgroundKernel": background_kernel,
            "clipLimit": float(clip_limit),
            "gridSize": grid_size,
        }

    elapsed_ms = (perf_counter() - started_at) * 1000.0
    return IlluminationResult(
        image=corrected,
        method=method,
        elapsed_ms=elapsed_ms,
        before=before,
        after=analyze_luminance(corrected),
        parameters=parameters,
    )


def make_comparison_grid(
    images: Sequence[tuple[str, Image]], *, columns: int = 3
) -> Image:
    """Build a labeled grid for visual before/after inspection."""
    if not images:
        raise IlluminationCorrectionError("At least one image is required.")
    if columns < 1:
        raise IlluminationCorrectionError("columns must be at least 1.")

    prepared = [(label, _to_bgr(image)) for label, image in images]
    cell_height = max(image.shape[0] for _, image in prepared)
    cell_width = max(image.shape[1] for _, image in prepared)
    header_height = 42
    rows = (len(prepared) + columns - 1) // columns
    canvas = np.full(
        (rows * (cell_height + header_height), columns * cell_width, 3),
        245,
        dtype=np.uint8,
    )

    for index, (label, image) in enumerate(prepared):
        row, column = divmod(index, columns)
        x = column * cell_width
        y = row * (cell_height + header_height)
        resized = _fit_to_cell(image, cell_width, cell_height)
        offset_x = x + (cell_width - resized.shape[1]) // 2
        offset_y = y + header_height + (cell_height - resized.shape[0]) // 2
        canvas[
            offset_y : offset_y + resized.shape[0],
            offset_x : offset_x + resized.shape[1],
        ] = resized
        cv2.putText(
            canvas,
            label.upper(),
            (x + 14, y + 29),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (35, 35, 35),
            2,
            cv2.LINE_AA,
        )
    return canvas


def _to_bgr(image: Image) -> Image:
    _validate_image(image)
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 1:
        return cv2.cvtColor(image[:, :, 0], cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image.copy()


def _fit_to_cell(image: Image, width: int, height: int) -> Image:
    scale = min(width / image.shape[1], height / image.shape[0])
    output_size = (
        max(1, int(round(image.shape[1] * scale))),
        max(1, int(round(image.shape[0] * scale))),
    )
    if output_size == (image.shape[1], image.shape[0]):
        return image.copy()
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    return cv2.resize(image, output_size, interpolation=interpolation)
