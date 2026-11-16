"""Guarded entry point for a future keycap detector; no phone resources are used."""
from __future__ import annotations
import argparse
from pathlib import Path

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument('--data', type=Path, required=True); args=parser.parse_args()
    if not args.data.is_file(): raise SystemExit(f'Missing keycap YOLO data config: {args.data}')
    try: import ultralytics  # noqa: F401
    except ImportError as error: raise SystemExit('KeyDetector training requires ultralytics and compatible PyTorch. No model was created.') from error
    raise SystemExit('Keycap labels are prepared, but a materialized image/label export and training policy must be selected before training. No model was created.')
if __name__ == '__main__': raise SystemExit(main())
