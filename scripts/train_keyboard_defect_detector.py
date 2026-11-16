"""Train only the binary BSX-derived keyboard_defect detector.

This script intentionally never imports phone models or datasets.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument('--data', type=Path, default=Path('datasets/keyboard/derived/bsx-keyboard-defect/data.yaml')); parser.add_argument('--epochs', type=int, default=50); parser.add_argument('--project', type=Path, default=Path('outputs/keyboard-training')); args=parser.parse_args()
    if not args.data.is_file(): raise SystemExit(f'Missing derived keyboard dataset config: {args.data}. Run scripts/prepare_keyboard_datasets.py first.')
    try: from ultralytics import YOLO
    except ImportError as error: raise SystemExit('Training requires ultralytics and its compatible PyTorch build. Install them in a dedicated keyboard environment, then rerun.') from error
    args.project.mkdir(parents=True, exist_ok=True)
    provenance={'task':'binary_keyboard_defect','data':str(args.data),'data_sha256':digest(args.data),'epochs':args.epochs,'classes':['keyboard_defect']}
    (args.project/'run-provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    YOLO('yolo11n.pt').train(data=str(args.data), epochs=args.epochs, project=str(args.project), name='binary-defect')
    return 0
if __name__ == '__main__': raise SystemExit(main())
