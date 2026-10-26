"""Versioned thresholds for keyboard inspection; deliberately separate from phone damage."""
CONFIG = {
    "version": "keyboard-baseline-v1",
    "max_upload_bytes": 25 * 1024 * 1024,
    "quality": {"min_blur": 45.0, "min_brightness": 28.0, "max_brightness": 230.0,
                "max_clipping_ratio": 0.20},
    "keys": {"min_area": 350, "max_area_fraction": 0.08, "row_tolerance_factor": 0.65,
             "shift_factor": 0.38, "tilt_degrees": 12.0, "missing_gap_factor": 1.85},
}
