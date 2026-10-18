"""
Sap xep dataset MVTec AD transistor (sau khi da giai nen)
vao layout cua TV1: data/train|val|test/{normal,defective}/

Buoc 1: Tai transistor.tar.xz tu https://www.mvtec.com/company/research/datasets/mvtec-ad
Buoc 2: Giai nen: python -c "import tarfile; tarfile.open(r'<duong_dan>\transistor.tar.xz').extractall(r'd:\STUDY\XU LI ANH\mvtec-raw')"
Buoc 3: Chay script nay: python scripts/arrange_transistor.py
"""

from __future__ import annotations

import shutil
import random
from pathlib import Path

# === CAU HINH - SUA NEU CAN ===
RAW_DIR  = Path(r"d:\STUDY\XU LI ANH\mvtec-raw\transistor")
DATA_DIR = Path(__file__).parent.parent / "data"
SEED = 42
SPLIT = (0.70, 0.15, 0.15)
EXTS = {".png", ".jpg", ".jpeg", ".bmp"}
# ================================

if not RAW_DIR.exists():
    raise SystemExit(
        f"[ERROR] Khong tim thay thu muc: {RAW_DIR}\n"
        "Hay kiem tra lai duong dan sau khi giai nen."
    )

random.seed(SEED)

def collect(folder: Path) -> list[Path]:
    return [p for p in sorted(folder.rglob("*")) if p.suffix.lower() in EXTS]

# Normal images: train/good + test/good
normal = collect(RAW_DIR / "train" / "good")
test_good = RAW_DIR / "test" / "good"
if test_good.exists():
    normal += collect(test_good)

# Defective images: toan bo sub-folder trong test/ tru good
defective: list[Path] = []
for sub in sorted((RAW_DIR / "test").iterdir()):
    if sub.is_dir() and sub.name != "good":
        defective += collect(sub)
        print(f"   Found defect type: {sub.name} ({len(collect(sub))} images)")

random.shuffle(normal)
random.shuffle(defective)

print(f"\n[STATS]")
print(f"   normal   : {len(normal)} images")
print(f"   defective: {len(defective)} images")

if not normal or not defective:
    raise SystemExit("[ERROR] No images found. Check RAW_DIR path.")


def split_copy(files: list[Path], cls: str) -> None:
    n = len(files)
    t = int(n * SPLIT[0])
    v = t + int(n * SPLIT[1])
    parts = {"train": files[:t], "val": files[t:v], "test": files[v:]}
    for split, flist in parts.items():
        dest = DATA_DIR / split / cls
        dest.mkdir(parents=True, exist_ok=True)
        for f in flist:
            shutil.copy2(f, dest / f.name)
        print(f"   {split}/{cls}: {len(flist)} images")


print("\n[SPLIT] Copying to data/ ...")
split_copy(normal,    "normal")
split_copy(defective, "defective")

print("\n[DONE] Dataset ready!")
for split in ["train", "val", "test"]:
    for cls in ["normal", "defective"]:
        folder = DATA_DIR / split / cls
        count = len([f for f in folder.iterdir() if f.suffix.lower() in EXTS])
        print(f"   data/{split}/{cls}: {count} images")

# In ten mot file defective de dung buoc tiep
first_defect = next(
    (DATA_DIR / "train" / "defective").glob("*.png"), None
) or next((DATA_DIR / "train" / "defective").iterdir(), None)

print(f"\n[NEXT] Chay experiment preprocessing:")
if first_defect:
    print(f'   python -m preprocessing.experiment "data\\train\\defective\\{first_defect.name}"')
else:
    print("   python -m preprocessing.experiment data\\train\\defective\\<filename>.png")
