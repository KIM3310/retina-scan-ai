"""ResNet18 transfer learning model for retinal disease classification."""

import torch
import torch.nn as nn
from torchvision import models
from torchvision.models import ResNet18_Weights


class RetinalClassifier(nn.Module):
    """ResNet18-based classifier fine-tuned for retinal disease detection.

    Transfer learning strategy:
    1. Load ImageNet-pretrained ResNet18
    2. Replace final FC layer for target classes
    3. Optionally freeze backbone for feature extraction mode
    """

    def __init__(self, num_classes: int = 5, pretrained: bool = True, freeze_backbone: bool = False):
        super().__init__()

        weights = ResNet18_Weights.DEFAULT if pretrained else None
        self.backbone = models.resnet18(weights=weights)

        if freeze_backbone:
            for param in self.backbone.parameters():
                param.requires_grad = False

        in_features = self.backbone.fc.in_features
        self.backbone.fc = nn.Sequential(
            nn.Dropout(p=0.3),
            nn.Linear(in_features, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(p=0.2),
            nn.Linear(256, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x)

    def get_feature_extractor(self) -> nn.Module:
        """Return backbone without FC layer for Grad-CAM feature extraction."""
        layers = list(self.backbone.children())[:-1]
        return nn.Sequential(*layers)

    def unfreeze_backbone(self) -> None:
        """Unfreeze all backbone parameters for full fine-tuning."""
        for param in self.backbone.parameters():
            param.requires_grad = True

    def count_parameters(self) -> dict[str, int]:
        total = sum(p.numel() for p in self.parameters())
        trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        return {"total": total, "trainable": trainable, "frozen": total - trainable}


def build_model(num_classes: int = 5, pretrained: bool = True, freeze_backbone: bool = False) -> RetinalClassifier:
    """Factory function for creating RetinalClassifier."""
    model = RetinalClassifier(
        num_classes=num_classes,
        pretrained=pretrained,
        freeze_backbone=freeze_backbone,
    )
    return model
