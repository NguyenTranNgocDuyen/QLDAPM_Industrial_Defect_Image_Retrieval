"""
Sap xep NEU Surface Defect dataset vao layout TV1.

Chien luoc phan loai binary:
  normal    = patches (bo mat phang, khong co lo hong) 
  defective = crazing + inclusion + pitted_surface + rolled-in_scale + scratches

Chay:
    python scripts/arrange_neu.py
"""

from __future__ import annotations

import shutil
import random
from pathlib import Path

NEU_ROOT  = Path(r"d:\STUDY\XU LI ANH\mvtec-raw\neu\NEU-DET")
DATA_DIR  = Path(__file__).parent.parent / "data"
SEED = 42
EXTS = {".jpg", ".jpeg", ".png", ".bmp"}

# "patches" la bo mat phang, dung lam "normal"
# Con lai la "defective"
NORMAL_CLASSES    = ["patches"]
DEFECTIVE_CLASSES = ["crazing", "inclusion", "pitted_surface",
                     "rolled-in_scale", "scratches"]

random.seed(SEED)

def collect(folder: Path) -> list[Path]:
    return [p for p in sorted(folder.glob("*")) if p.suffix.lower() in EXTS]


# Thu thap anh tu ca train + validation
def gather(cls_list: list[str]) -> list[Path]:
    files: list[Path] = []
    for split_name in ["train", "validation"]:
        images_dir = NEU_ROOT / split_name / "images"
        if not images_dir.exists():
            continue
        for cls in cls_list:
            cls_dir = images_dir / cls
            if cls_dir.exists():
                found = collect(cls_dir)
                files.extend(found)
                print(f"  {split_name}/{cls}: {len(found)} images")
    return files


print("[GATHER] Collecting normal images (patches)...")
normal_all = gather(NORMAL_CLASSES)

print("\n[GATHER] Collecting defective images...")
defective_all = gather(DEFECTIVE_CLASSES)

random.shuffle(normal_all)
random.shuffle(defective_all)

print(f"\n[STATS]")
print(f"  normal   : {len(normal_all)} images")
print(f"  defective: {len(defective_all)} images")

# Can bang so luong: lay toi da = normal_all
n_normal = len(normal_all)
n_defect = min(len(defective_all), n_normal * 3)  # max 3x defective
defective_all = defective_all[:n_defect]
print(f"  Using: {n_normal} normal + {n_defect} defective (balanced for training)")


def split_copy(files: list[Path], cls: str) -> None:
    n = len(files)
    t = int(n * 0.70)
    v = t + int(n * 0.15)
    parts = {"train": files[:t], "val": files[t:v], "test": files[v:]}
    for split, flist in parts.items():
        dest = DATA_DIR / split / cls
        dest.mkdir(parents=True, exist_ok=True)
        # Xoa .gitkeep neu co
        gitkeep = dest / ".gitkeep"
        if gitkeep.exists():
            gitkeep.unlink()
        for f in flist:
            shutil.copy2(f, dest / f.name)
        print(f"  {split}/{cls}: {len(flist)} images")


print("\n[SPLIT] Copying to data/ ...")
split_copy(normal_all,    "normal")
split_copy(defective_all, "defective")

print("\n[DONE] Dataset ready!")
total = 0
for split in ["train", "val", "test"]:
    for cls in ["normal", "defective"]:
        folder = DATA_DIR / split / cls
        count = len([f for f in folder.iterdir()
                     if f.suffix.lower() in EXTS])
        total += count
        print(f"  data/{split}/{cls}: {count} images")

print(f"\n  Total images: {total}")

# Tim ten file defective dau tien de chay experiment
first_defect = next(
    (f for f in (DATA_DIR / "train" / "defective").iterdir()
     if f.suffix.lower() in EXTS),
    None,
)
print("\n[NEXT] Run preprocessing experiment:")
if first_defect:
    print(f'  python -m preprocessing.experiment "data\\train\\defective\\{first_defect.name}"')
else:
    print("  python -m preprocessing.experiment data\\train\\defective\\<filename>.jpg")
