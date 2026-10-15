#!/usr/bin/env python3
"""Entry-point script to download and verify phone segmentation model weights."""

import sys
from pathlib import Path

# Ensure image-processing directory is on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
MODULE_DIR = SCRIPT_DIR.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from defect_vision.download_model import main

if __name__ == "__main__":
    sys.exit(main())
