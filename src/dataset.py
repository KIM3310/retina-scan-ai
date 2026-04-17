"""Custom dataset with augmentation pipeline for retinal fundus images."""

from pathlib import Path

import torch
from PIL import Image
from torch.utils.data import Dataset, DataLoader, random_split
from torchvision import transforms

from src.config import TrainConfig


class RetinalDataset(Dataset):
    """Dataset for retinal fundus images organized in class subdirectories.

    Expected structure:
        data/retina/
        ├── Normal/
        ├── Diabetic_Retinopathy/
        ├── Glaucoma/
        ├── Cataract/
        └── AMD/
    """

    def __init__(self, root_dir: Path, transform: transforms.Compose | None = None):
        self.root_dir = Path(root_dir)
        self.transform = transform
        self.samples: list[tuple[Path, int]] = []
        self.class_to_idx: dict[str, int] = {}

        self._load_samples()

    def _load_samples(self) -> None:
        class_dirs = sorted([d for d in self.root_dir.iterdir() if d.is_dir()])
        self.class_to_idx = {d.name: i for i, d in enumerate(class_dirs)}

        for class_dir in class_dirs:
            label = self.class_to_idx[class_dir.name]
            for img_path in class_dir.iterdir():
                if img_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}:
                    self.samples.append((img_path, label))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        img_path, label = self.samples[idx]
        image = Image.open(img_path).convert("RGB")

        if self.transform:
            image = self.transform(image)

        return image, label


def get_train_transforms(img_size: int = 224) -> transforms.Compose:
    """Augmentation pipeline for training: rotation, flip, color jitter, normalization."""
    return transforms.Compose([
        transforms.Resize((img_size, img_size)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.5),
        transforms.RandomRotation(degrees=15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.1, hue=0.05),
        transforms.RandomAffine(degrees=0, translate=(0.05, 0.05)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])


def get_val_transforms(img_size: int = 224) -> transforms.Compose:
    """Validation/test transforms: resize + normalize only."""
    return transforms.Compose([
        transforms.Resize((img_size, img_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])


def create_dataloaders(
    config: TrainConfig,
) -> tuple[DataLoader, DataLoader, DataLoader]:
    """Split dataset into train/val/test and return DataLoaders."""
    full_dataset = RetinalDataset(
        root_dir=config.data_dir,
        transform=get_train_transforms(config.img_size),
    )

    total = len(full_dataset)
    test_size = int(total * config.test_split)
    val_size = int(total * config.val_split)
    train_size = total - val_size - test_size

    generator = torch.Generator().manual_seed(config.seed)
    train_set, val_set, test_set = random_split(
        full_dataset, [train_size, val_size, test_size], generator=generator
    )

    val_set.dataset = RetinalDataset(
        root_dir=config.data_dir,
        transform=get_val_transforms(config.img_size),
    )
    test_set.dataset = RetinalDataset(
        root_dir=config.data_dir,
        transform=get_val_transforms(config.img_size),
    )

    train_loader = DataLoader(
        train_set, batch_size=config.batch_size, shuffle=True, num_workers=config.num_workers
    )
    val_loader = DataLoader(
        val_set, batch_size=config.batch_size, shuffle=False, num_workers=config.num_workers
    )
    test_loader = DataLoader(
        test_set, batch_size=config.batch_size, shuffle=False, num_workers=config.num_workers
    )

    return train_loader, val_loader, test_loader
