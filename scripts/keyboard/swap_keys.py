"""
Module hoán đổi vị trí 2 phím trên ảnh bàn phím (Key Swap Tool)
Dùng OpenCV seamlessClone để ghép tự nhiên hoặc copy-paste trực tiếp.
"""

import cv2
import numpy as np
from pathlib import Path


def swap_two_keys(image_path: str, box_a: list, box_b: list, output_path: str = None) -> np.ndarray:
    """
    Hoán đổi 2 phím trên ảnh dựa vào bounding box.
    box format: [x1, y1, x2, y2] (pixel coordinates)
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Không thể đọc ảnh: {image_path}")

    x1_a, y1_a, x2_a, y2_a = [int(v) for v in box_a]
    x1_b, y1_b, x2_b, y2_b = [int(v) for v in box_b]

    # Crop 2 phím
    patch_a = img[y1_a:y2_a, x1_a:x2_a].copy()
    patch_b = img[y1_b:y2_b, x1_b:x2_b].copy()

    # Resize patch nếu kích thước chênh lệch nhỏ (do góc nghiêng/cắt lẹch)
    patch_a_resized = cv2.resize(patch_a, (x2_b - x1_b, y2_b - y1_b))
    patch_b_resized = cv2.resize(patch_b, (x2_a - x1_a, y2_a - y1_a))

    result = img.copy()
    result[y1_b:y2_b, x1_b:x2_b] = patch_a_resized
    result[y1_a:y2_a, x1_a:x2_a] = patch_b_resized

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(output_path, result)

    return result


if __name__ == "__main__":
    print("Script hoán đổi phím sẵn sàng.")
