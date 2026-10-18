"""Dataset loaders that reuse TV1's preprocessing pipeline."""

from __future__ import annotations

from pathlib import Path

import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision.datasets import ImageFolder
from torchvision.transforms import v2

from preprocessing.pipeline import PreprocessConfig, preprocess_image


EXPECTED_CLASSES = ["defective", "normal"]


class PreprocessedImageFolder(Dataset):
    """ImageFolder adapter returning preprocessed CHW float tensors and class labels."""

    def __init__(self, root: str | Path, config: PreprocessConfig, augment: bool = False) -> None:
        self.dataset = ImageFolder(str(root))
        if set(self.dataset.classes) != set(EXPECTED_CLASSES):
            raise ValueError(
                f"Expected class folders {EXPECTED_CLASSES}; found {self.dataset.classes} in {root}."
            )
        self.config = config
        self.class_to_idx = self.dataset.class_to_idx
        self.classes = self.dataset.classes
        self.augment = (
            v2.Compose([
                v2.RandomHorizontalFlip(p=0.5),
                v2.RandomRotation(degrees=10),
                v2.ColorJitter(brightness=0.12, contrast=0.12),
            ])
            if augment else None
        )

    def __len__(self) -> int:
        return len(self.dataset)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]:
        path, label = self.dataset.samples[index]
        with Image.open(path) as image:
            rgb_image = image.convert("RGB")
            if self.augment is not None:
                rgb_image = self.augment(rgb_image)
            array = preprocess_image(rgb_image, self.config)
        return torch.from_numpy(array).permute(2, 0, 1), label


def make_loader(root: str | Path, config: PreprocessConfig, batch_size: int, shuffle: bool, augment: bool = False) -> DataLoader:
    """Create a loader; augmentation is intentionally opt-in for train only."""
    dataset = PreprocessedImageFolder(root, config, augment=augment)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, num_workers=0, pin_memory=torch.cuda.is_available())
