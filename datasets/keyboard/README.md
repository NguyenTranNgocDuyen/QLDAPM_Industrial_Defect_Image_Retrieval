# Keyboard inspection dataset

This folder is intentionally separate from `data/`, which contains non-keyboard
surface-texture images. Do not mix the two datasets.

## Layout

```text
datasets/keyboard/
  train/images/
  val/images/
  test/images/
  annotations.csv
  LICENSES.md
  DATASET_CARD.md
```

Use one row per visible defect in `annotations.csv`:

```csv
image,split,layout,label,x1,y1,x2,y2,key_label,row,column,reviewer
images/example.jpg,train,ansi_104,missing_key,120,80,170,130,,1,4,reviewer-id
```

Allowed labels are `normal`, `missing_key`, `shifted_key`, `tilted_key`, and
`uncertain`. A normal image has exactly one row with `label=normal` and empty
bounds. `damaged_keycap` and `wrong_keycap` are not accepted by the current
baseline because it has no surface model or labelled reference template.

Run the read-only validator from the repository root:

```powershell
python scripts/validate_keyboard_dataset.py --dataset-dir datasets/keyboard
```

The validator rejects corrupted images, unsupported labels, invalid boxes,
annotation/image mismatches, and exact duplicates that cross train/val/test.
