import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prepare_keyboard_datasets import clamped, split_for


def test_clamped_voc_box_stays_inside_image():
    box = {"x1": 529, "y1": 363, "x2": 641, "y2": 543}
    assert clamped(box, 640, 640) == (529, 363, 640, 543)


def test_split_assignment_is_deterministic_and_disjoint():
    rows = [{"sha256": f"{index:03}"} for index in range(20)]
    first, second = split_for(rows), split_for(list(reversed(rows)))
    assert first == second
    assert set(first.values()) == {"train", "val", "test"}
