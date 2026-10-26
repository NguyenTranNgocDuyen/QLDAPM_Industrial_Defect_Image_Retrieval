"""Validate a real segmentation manifest without inventing data or scores."""
from __future__ import annotations
import argparse, csv, hashlib
from pathlib import Path
from PIL import Image
REQUIRED={"source","license","image_path","damage_mask_path","body_mask_path","annotation_id","group_id","split","sha256"}
def validate(path: Path) -> list[str]:
    rows=list(csv.DictReader(path.open(encoding="utf-8"))); errors=[]; groups={}; splits=set()
    if not rows: return ["manifest has no rows"]
    if set(rows[0]) != REQUIRED: errors.append(f"columns must be exactly {sorted(REQUIRED)}")
    for index,row in enumerate(rows,2):
        splits.add(row.get("split")); group=row.get("group_id"); groups.setdefault(group,set()).add(row.get("split"))
        image=Path(row.get("image_path","")); damage=Path(row.get("damage_mask_path","")); body=Path(row.get("body_mask_path",""))
        for item in (image,damage,body):
            if not item.is_file(): errors.append(f"line {index}: missing {item}")
        if image.is_file() and row.get("sha256") != hashlib.sha256(image.read_bytes()).hexdigest(): errors.append(f"line {index}: sha256 mismatch")
        if image.is_file() and damage.is_file() and body.is_file():
            size=Image.open(image).size
            if Image.open(damage).size != size or Image.open(body).size != size: errors.append(f"line {index}: masks must match image dimensions")
    if "test" not in splits: errors.append("independent test split is required")
    for group,assigned in groups.items():
        if len(assigned)>1: errors.append(f"group leakage: {group} occurs in {sorted(assigned)}")
    return errors
if __name__ == "__main__":
    p=argparse.ArgumentParser();p.add_argument("manifest");a=p.parse_args(); errors=validate(Path(a.manifest)); print("VALID" if not errors else "\n".join(errors)); raise SystemExit(bool(errors))
