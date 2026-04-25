"""Grad-CAM visualization for model interpretability.

Generates heatmaps showing which regions of retinal images the model focuses on
for each prediction, providing clinical interpretability.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

from src.config import CLASS_LABELS
from src.model import build_model


class GradCAM:
    """Gradient-weighted Class Activation Mapping for ResNet18.

    Hooks into the last convolutional layer to capture gradients
    and activations for generating attention heatmaps.
    """

    def __init__(self, model: torch.nn.Module, target_layer: str = "backbone.layer4"):
        self.model = model
        self.model.eval()
        self.gradients: torch.Tensor | None = None
        self.activations: torch.Tensor | None = None

        target = dict(model.named_modules())[target_layer]
        target.register_forward_hook(self._save_activations)
        target.register_full_backward_hook(self._save_gradients)

    def _save_activations(self, module: torch.nn.Module, input: tuple, output: torch.Tensor) -> None:
        self.activations = output.detach()

    def _save_gradients(self, module: torch.nn.Module, grad_input: tuple, grad_output: tuple) -> None:
        self.gradients = grad_output[0].detach()

    def generate(self, input_tensor: torch.Tensor, target_class: int | None = None) -> np.ndarray:
        """Generate Grad-CAM heatmap for a single input image.

        Args:
            input_tensor: Preprocessed image tensor [1, C, H, W]
            target_class: Class index to visualize. Uses predicted class if None.

        Returns:
            Heatmap as numpy array [H, W] with values in [0, 1].
        """
        output = self.model(input_tensor)

        if target_class is None:
            target_class = output.argmax(dim=1).item()

        self.model.zero_grad()
        score = output[0, target_class]
        score.backward()

        weights = self.gradients.mean(dim=(2, 3), keepdim=True)
        cam = (weights * self.activations).sum(dim=1, keepdim=True)
        cam = F.relu(cam)
        cam = F.interpolate(cam, size=input_tensor.shape[2:], mode="bilinear", align_corners=False)

        cam = cam.squeeze().cpu().numpy()
        cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)

        return cam


def visualize_gradcam(
    image_path: str | Path,
    checkpoint_path: str | Path,
    output_path: str | Path | None = None,
    target_class: int | None = None,
) -> dict:
    """Generate and save Grad-CAM visualization for a retinal image.

    Returns prediction info and saves overlay image.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    ckpt_config = checkpoint.get("config", {})

    model = build_model(num_classes=ckpt_config.get("num_classes", 5), pretrained=False).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])

    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    original = Image.open(image_path).convert("RGB")
    input_tensor = transform(original).unsqueeze(0).to(device)

    grad_cam = GradCAM(model)
    heatmap = grad_cam.generate(input_tensor, target_class)

    with torch.no_grad():
        output = model(input_tensor)
        probs = torch.softmax(output, dim=1)
        pred_class = output.argmax(dim=1).item()
        confidence = probs[0, pred_class].item()

    if output_path is None:
        output_path = Path("outputs") / f"gradcam_{Path(image_path).stem}.png"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    original_resized = original.resize((224, 224))
    axes[0].imshow(original_resized)
    axes[0].set_title("Original")
    axes[0].axis("off")

    axes[1].imshow(heatmap, cmap="jet")
    axes[1].set_title("Grad-CAM Heatmap")
    axes[1].axis("off")

    axes[2].imshow(original_resized)
    axes[2].imshow(heatmap, cmap="jet", alpha=0.4)
    pred_label = CLASS_LABELS.get(pred_class, f"Class {pred_class}")
    axes[2].set_title(f"Overlay: {pred_label} ({confidence:.1%})")
    axes[2].axis("off")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "predicted_class": pred_class,
        "predicted_label": pred_label,
        "confidence": confidence,
        "all_probabilities": {CLASS_LABELS.get(i, f"Class {i}"): float(probs[0, i]) for i in range(probs.shape[1])},
        "gradcam_path": str(output_path),
    }


if __name__ == "__main__":
    import sys
    img = sys.argv[1] if len(sys.argv) > 1 else "sample.jpg"
    ckpt = sys.argv[2] if len(sys.argv) > 2 else "checkpoints/best_model.pth"
    result = visualize_gradcam(img, ckpt)
    print(result)
