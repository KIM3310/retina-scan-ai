"""Model evaluation with confusion matrix, classification report, and ROC curves."""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import torch
import torch.nn as nn
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
    roc_curve,
)
from torch.utils.data import DataLoader
from tqdm import tqdm

from src.config import TrainConfig
from src.dataset import create_dataloaders
from src.model import build_model


@torch.no_grad()
def collect_predictions(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Collect all predictions, labels, and probabilities from a DataLoader."""
    model.eval()
    all_labels = []
    all_preds = []
    all_probs = []

    for images, labels in tqdm(loader, desc="Evaluating"):
        images = images.to(device)
        outputs = model(images)
        probs = torch.softmax(outputs, dim=1)
        _, predicted = outputs.max(1)

        all_labels.extend(labels.cpu().numpy())
        all_preds.extend(predicted.cpu().numpy())
        all_probs.extend(probs.cpu().numpy())

    return np.array(all_labels), np.array(all_preds), np.array(all_probs)


def plot_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    class_names: list[str],
    output_path: Path,
) -> None:
    """Generate and save confusion matrix heatmap."""
    cm = confusion_matrix(y_true, y_pred)
    cm_normalized = cm.astype("float") / cm.sum(axis=1)[:, np.newaxis]

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=class_names,
                yticklabels=class_names, ax=axes[0])
    axes[0].set_title("Confusion Matrix (Counts)")
    axes[0].set_ylabel("True Label")
    axes[0].set_xlabel("Predicted Label")

    sns.heatmap(cm_normalized, annot=True, fmt=".2f", cmap="Blues", xticklabels=class_names,
                yticklabels=class_names, ax=axes[1])
    axes[1].set_title("Confusion Matrix (Normalized)")
    axes[1].set_ylabel("True Label")
    axes[1].set_xlabel("Predicted Label")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Confusion matrix saved: {output_path}")


def plot_roc_curves(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    class_names: list[str],
    output_path: Path,
) -> dict[str, float]:
    """Generate per-class ROC curves and compute AUC scores."""
    n_classes = len(class_names)
    auc_scores = {}

    fig, ax = plt.subplots(figsize=(10, 8))

    for i in range(n_classes):
        y_binary = (y_true == i).astype(int)
        fpr, tpr, _ = roc_curve(y_binary, y_prob[:, i])
        auc_val = roc_auc_score(y_binary, y_prob[:, i])
        auc_scores[class_names[i]] = float(auc_val)
        ax.plot(fpr, tpr, label=f"{class_names[i]} (AUC={auc_val:.3f})")

    ax.plot([0, 1], [0, 1], "k--", alpha=0.5)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curves (One-vs-Rest)")
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"ROC curves saved: {output_path}")

    return auc_scores


def evaluate(checkpoint_path: str | Path, config: TrainConfig | None = None) -> dict:
    """Full evaluation pipeline on test set.

    Returns dict with accuracy, classification report, AUC scores.
    """
    if config is None:
        config = TrainConfig()

    config.output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    ckpt_config = checkpoint.get("config", {})

    model = build_model(
        num_classes=ckpt_config.get("num_classes", config.num_classes),
        pretrained=False,
    ).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])

    _, _, test_loader = create_dataloaders(config)
    print(f"Test set: {len(test_loader.dataset)} images")

    y_true, y_pred, y_prob = collect_predictions(model, test_loader, device)

    accuracy = accuracy_score(y_true, y_pred)
    report = classification_report(y_true, y_pred, target_names=config.class_names, output_dict=True)
    report_text = classification_report(y_true, y_pred, target_names=config.class_names)

    print(f"\nTest Accuracy: {accuracy:.4f}")
    print(f"\n{report_text}")

    plot_confusion_matrix(y_true, y_pred, config.class_names, config.output_dir / "confusion_matrix.png")
    auc_scores = plot_roc_curves(y_true, y_prob, config.class_names, config.output_dir / "roc_curves.png")

    results = {
        "accuracy": float(accuracy),
        "classification_report": report,
        "auc_scores": auc_scores,
        "macro_auc": float(np.mean(list(auc_scores.values()))),
        "checkpoint": str(checkpoint_path),
        "test_size": len(test_loader.dataset),
    }

    results_path = config.output_dir / "evaluation_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved: {results_path}")

    return results


if __name__ == "__main__":
    import sys
    ckpt = sys.argv[1] if len(sys.argv) > 1 else "checkpoints/best_model.pth"
    evaluate(ckpt)
