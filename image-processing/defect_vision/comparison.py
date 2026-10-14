"""Before-and-after comparison suite for image enhancement techniques.

Evaluates whether an enhancement technique actually benefits electronic-device
defect inspection by computing quantitative image quality metrics:
- Global contrast (standard deviation of luminance)
- Local contrast / edge sharpness (Laplacian variance, Tenengrad gradient energy)
- Entropy (information content)
- Defect visibility / CNR if a defect mask is provided
- Noise amplification estimation (high-frequency energy in homogeneous background)
- Processing latency
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Sequence

import cv2
import numpy as np
from numpy.typing import NDArray

Image = NDArray[np.uint8]


class ComparisonError(ValueError):
    """Raised when comparison images or parameters are invalid."""


@dataclass(frozen=True)
class ImageQualityMetrics:
    """Quantitative image metrics relevant to defect inspection."""

    mean_luminance: float
    contrast_std: float
    sharpness_laplacian_var: float
    tenengrad_energy: float
    entropy: float
    background_noise_std: float

    def to_dict(self) -> dict[str, float]:
        return {key: round(float(val), 4) for key, val in asdict(self).items()}


@dataclass(frozen=True)
class EnhancementComparisonRecord:
    """Comparison record between original and enhanced image."""

    technique_name: str
    elapsed_ms: float
    original_metrics: ImageQualityMetrics
    enhanced_metrics: ImageQualityMetrics
    contrast_gain_ratio: float
    sharpness_gain_ratio: float
    noise_gain_ratio: float
    defect_cnr_before: float | None
    defect_cnr_after: float | None
    recommendation: str  # Beneficial / Marginal / Caution (Noise amplified)

    def to_dict(self) -> dict[str, object]:
        return {
            "technique_name": self.technique_name,
            "elapsed_ms": round(float(self.elapsed_ms), 3),
            "original_metrics": self.original_metrics.to_dict(),
            "enhanced_metrics": self.enhanced_metrics.to_dict(),
            "contrast_gain_ratio": round(float(self.contrast_gain_ratio), 4),
            "sharpness_gain_ratio": round(float(self.sharpness_gain_ratio), 4),
            "noise_gain_ratio": round(float(self.noise_gain_ratio), 4),
            "defect_cnr_before": round(float(self.defect_cnr_before), 4) if self.defect_cnr_before is not None else None,
            "defect_cnr_after": round(float(self.defect_cnr_after), 4) if self.defect_cnr_after is not None else None,
            "recommendation": self.recommendation,
        }


def _validate_image(image: Image) -> None:
    if not isinstance(image, np.ndarray) or image.size == 0:
        raise ComparisonError("Image must be a non-empty numpy array.")
    if image.dtype != np.uint8:
        raise ComparisonError("Image must have dtype uint8.")
    if image.ndim not in (2, 3):
        raise ComparisonError("Image must be 2D or 3D.")


def _to_gray(image: Image) -> Image:
    _validate_image(image)
    if image.ndim == 2:
        return image
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def compute_entropy(gray: Image) -> float:
    """Calculate Shannon entropy (information content in bits/pixel)."""
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    total_pixels = gray.size
    prob = hist / float(total_pixels)
    prob_non_zero = prob[prob > 0]
    return float(-np.sum(prob_non_zero * np.log2(prob_non_zero)))


def compute_tenengrad(gray: Image) -> float:
    """Calculate Tenengrad gradient energy (sum of squared Sobel gradients)."""
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    grad_sq = gx**2 + gy**2
    return float(np.mean(grad_sq))


def estimate_background_noise(gray: Image, mask: Image | None = None) -> float:
    """Estimate background high-frequency noise using median absolute deviation of Laplacian."""
    # Compute high frequency response via Laplacian
    lap = cv2.Laplacian(gray, cv2.CV_64F, ksize=3)
    if mask is not None:
        bg_pixels = lap[mask == 0]
        if bg_pixels.size > 0:
            return float(np.std(bg_pixels))
    return float(np.std(lap))


def compute_image_quality_metrics(image: Image, defect_mask: Image | None = None) -> ImageQualityMetrics:
    """Compute comprehensive image quality metrics for defect detection."""
    gray = _to_gray(image)
    mean_val = float(np.mean(gray))
    std_val = float(np.std(gray))

    # Laplacian variance (sharpness)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    lap_var = float(np.var(lap))

    # Tenengrad energy
    tenengrad = compute_tenengrad(gray)

    # Shannon entropy
    entropy_val = compute_entropy(gray)

    # Noise estimation
    noise_std = estimate_background_noise(gray, defect_mask)

    return ImageQualityMetrics(
        mean_luminance=mean_val,
        contrast_std=std_val,
        sharpness_laplacian_var=lap_var,
        tenengrad_energy=tenengrad,
        entropy=entropy_val,
        background_noise_std=noise_std,
    )


def compute_defect_cnr(image: Image, defect_mask: Image) -> float:
    """Compute Contrast-to-Noise Ratio (CNR) between defect region and background."""
    gray = _to_gray(image)
    defect_bool = defect_mask > 0
    bg_bool = ~defect_bool

    if not np.any(defect_bool) or not np.any(bg_bool):
        raise ComparisonError("Mask must contain both defect (>0) and background (0) regions.")

    d_pixels = gray[defect_bool].astype(np.float64)
    b_pixels = gray[bg_bool].astype(np.float64)

    d_mean, d_std = float(np.mean(d_pixels)), float(np.std(d_pixels))
    b_mean, b_std = float(np.mean(b_pixels)), float(np.std(b_pixels))

    return abs(d_mean - b_mean) / float(np.sqrt(d_std**2 + b_std**2 + 1e-5))


def evaluate_enhancement_pair(
    original: Image,
    enhanced: Image,
    technique_name: str,
    elapsed_ms: float = 0.0,
    defect_mask: Image | None = None,
) -> EnhancementComparisonRecord:
    """Evaluate whether an enhanced image is demonstrably better than the original."""
    _validate_image(original)
    _validate_image(enhanced)

    orig_metrics = compute_image_quality_metrics(original, defect_mask)
    enh_metrics = compute_image_quality_metrics(enhanced, defect_mask)

    contrast_gain = enh_metrics.contrast_std / (orig_metrics.contrast_std + 1e-5)
    sharpness_gain = enh_metrics.sharpness_laplacian_var / (orig_metrics.sharpness_laplacian_var + 1e-5)
    noise_gain = enh_metrics.background_noise_std / (orig_metrics.background_noise_std + 1e-5)

    cnr_before = None
    cnr_after = None
    if defect_mask is not None:
        cnr_before = compute_defect_cnr(original, defect_mask)
        cnr_after = compute_defect_cnr(enhanced, defect_mask)

    # Decision logic: Does it genuinely help defect detection?
    # - If noise is amplified drastically (noise_gain > 2.0 and CNR drops), mark Caution.
    # - If CNR increases or sharpness increases with acceptable noise, mark Beneficial.
    if cnr_before is not None and cnr_after is not None:
        if cnr_after > cnr_before * 1.15:
            rec = "Highly Beneficial (Defect CNR improved)"
        elif cnr_after < cnr_before * 0.90:
            rec = "Caution (Defect contrast reduced relative to noise)"
        else:
            rec = "Marginal (Defect CNR unchanged)"
    else:
        if noise_gain > 2.2:
            rec = "Caution (Noise severely amplified)"
        elif sharpness_gain > 1.2 and noise_gain < 1.8:
            rec = "Beneficial (Edge sharpness improved without excessive noise)"
        elif contrast_gain > 1.1:
            rec = "Moderate Benefit (Contrast increased)"
        else:
            rec = "Marginal (Negligible difference)"

    return EnhancementComparisonRecord(
        technique_name=technique_name,
        elapsed_ms=elapsed_ms,
        original_metrics=orig_metrics,
        enhanced_metrics=enh_metrics,
        contrast_gain_ratio=contrast_gain,
        sharpness_gain_ratio=sharpness_gain,
        noise_gain_ratio=noise_gain,
        defect_cnr_before=cnr_before,
        defect_cnr_after=cnr_after,
        recommendation=rec,
    )


def make_before_after_comparison_board(
    original: Image,
    enhanced: Image,
    record: EnhancementComparisonRecord,
    tile_size: tuple[int, int] = (360, 360),
) -> Image:
    """Create a side-by-side comparison board with rendered metrics cards and histogram curves."""
    w_t, h_t = tile_size

    orig_bgr = original if original.ndim == 3 else cv2.cvtColor(original, cv2.COLOR_GRAY2BGR)
    enh_bgr = enhanced if enhanced.ndim == 3 else cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

    orig_resized = cv2.resize(orig_bgr, (w_t, h_t))
    enh_resized = cv2.resize(enh_bgr, (w_t, h_t))

    # Add header bars
    cv2.rectangle(orig_resized, (0, 0), (w_t, 28), (20, 20, 20), -1)
    cv2.putText(
        orig_resized,
        "BEFORE (Original)",
        (8, 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )

    cv2.rectangle(enh_resized, (0, 0), (w_t, 28), (20, 20, 20), -1)
    cv2.putText(
        enh_resized,
        f"AFTER ({record.technique_name})",
        (8, 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 128),
        1,
        cv2.LINE_AA,
    )

    # Assemble top visual row
    visual_row = np.hstack([orig_resized, enh_resized])

    # Bottom summary panel
    panel_h = 130
    panel_w = w_t * 2
    panel = np.full((panel_h, panel_w, 3), 32, dtype=np.uint8)

    # Text summary
    lines = [
        f"Technique: {record.technique_name} | Latency: {record.elapsed_ms:.2f} ms",
        f"Contrast Gain: {record.contrast_gain_ratio:.2f}x | Sharpness Gain: {record.sharpness_gain_ratio:.2f}x | Noise Gain: {record.noise_gain_ratio:.2f}x",
    ]
    if record.defect_cnr_before is not None and record.defect_cnr_after is not None:
        lines.append(
            f"Defect CNR: {record.defect_cnr_before:.2f} -> {record.defect_cnr_after:.2f} (Delta: {record.defect_cnr_after - record.defect_cnr_before:+.2f})"
        )
    lines.append(f"Verdict: {record.recommendation}")

    y = 26
    for idx, l in enumerate(lines):
        color = (255, 255, 255)
        if "Verdict" in l:
            color = (0, 230, 100) if "Beneficial" in l else ((0, 200, 255) if "Marginal" in l else (0, 120, 255))
        cv2.putText(panel, l, (16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 1, cv2.LINE_AA)
        y += 24

    return np.vstack([visual_row, panel])
