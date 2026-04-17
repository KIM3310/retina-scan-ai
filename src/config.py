"""Hyperparameters and configuration for retinal disease classification."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TrainConfig:
    data_dir: Path = Path("data/retina")
    output_dir: Path = Path("outputs")
    checkpoint_dir: Path = Path("checkpoints")

    # Model
    model_name: str = "resnet18"
    num_classes: int = 5
    pretrained: bool = True
    freeze_backbone: bool = False

    # Training
    batch_size: int = 32
    num_epochs: int = 30
    learning_rate: float = 1e-4
    weight_decay: float = 1e-4
    lr_step_size: int = 10
    lr_gamma: float = 0.1

    # Early stopping
    patience: int = 7
    min_delta: float = 1e-4

    # Data
    img_size: int = 224
    val_split: float = 0.15
    test_split: float = 0.15
    num_workers: int = 4
    seed: int = 42

    # Classes
    class_names: list[str] = field(
        default_factory=lambda: [
            "Normal",
            "Diabetic Retinopathy",
            "Glaucoma",
            "Cataract",
            "AMD",
        ]
    )


CLASS_LABELS = {
    0: "Normal",
    1: "Diabetic Retinopathy",
    2: "Glaucoma",
    3: "Cataract",
    4: "Age-related Macular Degeneration",
}
