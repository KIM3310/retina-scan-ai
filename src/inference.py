"""Single-image inference pipeline."""

from pathlib import Path

import torch
from PIL import Image
from torchvision import transforms

from src.config import CLASS_LABELS
from src.model import build_model


class RetinalPredictor:
    """Inference wrapper for retinal disease classification."""

    def __init__(self, checkpoint_path: str | Path, device: str | None = None):
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))

        checkpoint = torch.load(checkpoint_path, map_location=self.device, weights_only=False)
        ckpt_config = checkpoint.get("config", {})

        self.model = build_model(
            num_classes=ckpt_config.get("num_classes", 5),
            pretrained=False,
        ).to(self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()

        img_size = ckpt_config.get("img_size", 224)
        self.transform = transforms.Compose([
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        self.class_labels = CLASS_LABELS

    @torch.no_grad()
    def predict(self, image: Image.Image) -> dict:
        """Predict disease class for a single retinal image.

        Returns dict with predicted class, confidence, and all probabilities.
        """
        tensor = self.transform(image.convert("RGB")).unsqueeze(0).to(self.device)

        output = self.model(tensor)
        probs = torch.softmax(output, dim=1)
        pred_idx = output.argmax(dim=1).item()
        confidence = probs[0, pred_idx].item()

        return {
            "predicted_class": pred_idx,
            "predicted_label": self.class_labels.get(pred_idx, f"Class {pred_idx}"),
            "confidence": confidence,
            "probabilities": {
                self.class_labels.get(i, f"Class {i}"): float(probs[0, i])
                for i in range(probs.shape[1])
            },
        }

    def predict_from_path(self, image_path: str | Path) -> dict:
        """Predict from a file path."""
        image = Image.open(image_path).convert("RGB")
        result = self.predict(image)
        result["image_path"] = str(image_path)
        return result
