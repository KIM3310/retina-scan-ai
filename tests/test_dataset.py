"""Tests for dataset and transform pipelines."""

from pathlib import Path

import pytest
import torch
from PIL import Image

from src.dataset import RetinalDataset, get_train_transforms, get_val_transforms


@pytest.fixture
def sample_dataset(tmp_path: Path) -> Path:
    """Create a minimal dataset directory structure with synthetic images."""
    classes = ["Normal", "Diabetic_Retinopathy", "Glaucoma", "Cataract", "AMD"]
    for cls in classes:
        cls_dir = tmp_path / cls
        cls_dir.mkdir()
        for i in range(5):
            img = Image.new("RGB", (256, 256), color=(i * 50, 100, 150))
            img.save(cls_dir / f"img_{i}.png")
    return tmp_path


class TestTransforms:
    def test_train_transforms_output_shape(self):
        transform = get_train_transforms(224)
        img = Image.new("RGB", (512, 512))
        tensor = transform(img)
        assert tensor.shape == (3, 224, 224)

    def test_val_transforms_output_shape(self):
        transform = get_val_transforms(224)
        img = Image.new("RGB", (512, 512))
        tensor = transform(img)
        assert tensor.shape == (3, 224, 224)

    def test_normalized_range(self):
        transform = get_val_transforms(224)
        img = Image.new("RGB", (224, 224), color=(128, 128, 128))
        tensor = transform(img)
        assert tensor.min() >= -3.0
        assert tensor.max() <= 3.0


class TestRetinalDataset:
    def test_dataset_length(self, sample_dataset: Path):
        dataset = RetinalDataset(sample_dataset, transform=get_val_transforms())
        assert len(dataset) == 25  # 5 classes x 5 images

    def test_dataset_item(self, sample_dataset: Path):
        dataset = RetinalDataset(sample_dataset, transform=get_val_transforms())
        img, label = dataset[0]
        assert isinstance(img, torch.Tensor)
        assert img.shape == (3, 224, 224)
        assert isinstance(label, int)
        assert 0 <= label < 5

    def test_class_mapping(self, sample_dataset: Path):
        dataset = RetinalDataset(sample_dataset, transform=get_val_transforms())
        assert len(dataset.class_to_idx) == 5

    def test_empty_directory(self, tmp_path: Path):
        dataset = RetinalDataset(tmp_path, transform=get_val_transforms())
        assert len(dataset) == 0

    def test_unsupported_files_ignored(self, tmp_path: Path):
        cls_dir = tmp_path / "Normal"
        cls_dir.mkdir()
        (cls_dir / "readme.txt").write_text("not an image")
        Image.new("RGB", (64, 64)).save(cls_dir / "real.png")
        dataset = RetinalDataset(tmp_path, transform=get_val_transforms())
        assert len(dataset) == 1
