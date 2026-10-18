"""
Download MVTec AD transistor category from HuggingFace.
No Kaggle account or MVTec registration needed.

Run:
    python scripts/download_mvtec_transistor.py
"""

from __future__ import annotations

import shutil
import random
from pathlib import Path

# --- Step 1: Download from HuggingFace ---
try:
    from huggingface_hub import snapshot_download
except ImportError:
    raise SystemExit("Run 'pip install huggingface_hub' first.")

RAW_DIR = Path(r"d:\STUDY\XU LI ANH\mvtec-raw")
DATA_DIR = Path(__file__).parent.parent / "data"
SEED = 42
SPLIT_RATIO = (0.70, 0.15, 0.15)

print("[DOWNLOAD] Downloading MVTec AD - transistor from HuggingFace...")
print("   First time ~50-80 MB, subsequent runs use cache")

snapshot_download(
    repo_id="Voxel51/mvtec-ad",
    repo_type="dataset",
    local_dir=str(RAW_DIR),
    allow_patterns=["transistor/**", "**/transistor/**"],
    ignore_patterns=["*.parquet"],
)

print(f"[OK] Download complete. Source: {RAW_DIR}")

# --- Step 2: Find transistor folder ---
transistor_dir = None
for candidate in [
    RAW_DIR / "transistor",
    RAW_DIR / "data" / "transistor",
]:
    if candidate.exists():
        transistor_dir = candidate
        break

if transistor_dir is None:
    print("\n[WARN] Transistor folder not found. Current structure:")
    for p in sorted(RAW_DIR.rglob("*"))[:30]:
        print(f"   {p.relative_to(RAW_DIR)}")
    raise SystemExit("Adjust the path in the script.")

print(f"[DIR] Transistor folder: {transistor_dir}")

# --- Step 3: Collect images ---
random.seed(SEED)
EXTS = {".png", ".jpg", ".jpeg", ".bmp"}

def collect_images(folder: Path) -> list[Path]:
    return [p for p in sorted(folder.rglob("*")) if p.suffix.lower() in EXTS]

normal_train_dir = transistor_dir / "train" / "good"
normal_test_dir  = transistor_dir / "test" / "good"

normal_all = collect_images(normal_train_dir)
if normal_test_dir.exists():
    normal_all += collect_images(normal_test_dir)

defective_all: list[Path] = []
for sub in sorted((transistor_dir / "test").iterdir()):
    if sub.is_dir() and sub.name != "good":
        defective_all += collect_images(sub)

random.shuffle(normal_all)
random.shuffle(defective_all)

print(f"\n[STATS] Images found:")
print(f"   normal   : {len(normal_all)}")
print(f"   defective: {len(defective_all)}")

if len(normal_all) < 10 or len(defective_all) < 10:
    raise SystemExit("Too few images. Check source folder.")

# --- Step 4: Split and copy ---
def split_and_copy(files: list[Path], class_name: str) -> None:
    n = len(files)
    t_end = int(n * SPLIT_RATIO[0])
    v_end = t_end + int(n * SPLIT_RATIO[1])
    parts = {
        "train": files[:t_end],
        "val":   files[t_end:v_end],
        "test":  files[v_end:],
    }
    for split_name, split_files in parts.items():
        dest = DATA_DIR / split_name / class_name
        dest.mkdir(parents=True, exist_ok=True)
        for f in split_files:
            shutil.copy2(f, dest / f.name)
        print(f"   {split_name}/{class_name}: {len(split_files)} images -> {dest}")

print("\n[SPLIT] Splitting and copying to data/...")
split_and_copy(normal_all,    "normal")
split_and_copy(defective_all, "defective")

# --- Step 5: Verify ---
print("\n[DONE] Complete! Quick check:")
for split in ["train", "val", "test"]:
    for cls in ["normal", "defective"]:
        folder = DATA_DIR / split / cls
        count = len([f for f in folder.iterdir() if f.suffix.lower() in EXTS])
        print(f"   data/{split}/{cls}: {count} images")

print("\n[NEXT] Run next:")
print("   python -m preprocessing.experiment data\\train\\defective\\<filename>.png")
