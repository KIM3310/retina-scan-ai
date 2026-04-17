"""Training loop with early stopping, LR scheduling, and metric logging."""

import json
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.optim import Adam
from torch.optim.lr_scheduler import StepLR
from torch.utils.data import DataLoader
from tqdm import tqdm

from src.config import TrainConfig
from src.dataset import create_dataloaders
from src.model import build_model


class EarlyStopping:
    """Stop training when validation loss stops improving."""

    def __init__(self, patience: int = 7, min_delta: float = 1e-4):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss: float | None = None
        self.should_stop = False

    def __call__(self, val_loss: float) -> bool:
        if self.best_loss is None or val_loss < self.best_loss - self.min_delta:
            self.best_loss = val_loss
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.should_stop = True
        return self.should_stop


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
) -> dict[str, float]:
    """Run one training epoch."""
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for images, labels in tqdm(loader, desc="Training", leave=False):
        images, labels = images.to(device), labels.to(device)

        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        running_loss += loss.item() * images.size(0)
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

    return {
        "train_loss": running_loss / total,
        "train_acc": correct / total,
    }


@torch.no_grad()
def validate(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> dict[str, float]:
    """Run validation."""
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0

    for images, labels in tqdm(loader, desc="Validation", leave=False):
        images, labels = images.to(device), labels.to(device)

        outputs = model(images)
        loss = criterion(outputs, labels)

        running_loss += loss.item() * images.size(0)
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

    return {
        "val_loss": running_loss / total,
        "val_acc": correct / total,
    }


def train(config: TrainConfig | None = None) -> Path:
    """Full training pipeline with early stopping and checkpointing.

    Returns path to the best checkpoint.
    """
    if config is None:
        config = TrainConfig()

    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    train_loader, val_loader, _ = create_dataloaders(config)
    print(f"Train: {len(train_loader.dataset)}, Val: {len(val_loader.dataset)}")

    model = build_model(
        num_classes=config.num_classes,
        pretrained=config.pretrained,
        freeze_backbone=config.freeze_backbone,
    ).to(device)

    params = model.count_parameters()
    print(f"Parameters — total: {params['total']:,}, trainable: {params['trainable']:,}")

    criterion = nn.CrossEntropyLoss()
    optimizer = Adam(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    scheduler = StepLR(optimizer, step_size=config.lr_step_size, gamma=config.lr_gamma)
    early_stopping = EarlyStopping(patience=config.patience, min_delta=config.min_delta)

    history: list[dict] = []
    best_val_loss = float("inf")
    best_checkpoint = config.checkpoint_dir / "best_model.pth"

    for epoch in range(1, config.num_epochs + 1):
        start = time.time()
        lr = optimizer.param_groups[0]["lr"]

        train_metrics = train_one_epoch(model, train_loader, criterion, optimizer, device)
        val_metrics = validate(model, val_loader, criterion, device)
        scheduler.step()

        elapsed = time.time() - start
        epoch_log = {"epoch": epoch, "lr": lr, "time": elapsed, **train_metrics, **val_metrics}
        history.append(epoch_log)

        print(
            f"Epoch {epoch:02d}/{config.num_epochs} | "
            f"Train Loss: {train_metrics['train_loss']:.4f} Acc: {train_metrics['train_acc']:.4f} | "
            f"Val Loss: {val_metrics['val_loss']:.4f} Acc: {val_metrics['val_acc']:.4f} | "
            f"LR: {lr:.6f} | {elapsed:.1f}s"
        )

        if val_metrics["val_loss"] < best_val_loss:
            best_val_loss = val_metrics["val_loss"]
            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "val_loss": best_val_loss,
                    "val_acc": val_metrics["val_acc"],
                    "config": {
                        "num_classes": config.num_classes,
                        "model_name": config.model_name,
                        "img_size": config.img_size,
                    },
                },
                best_checkpoint,
            )
            print(f"  -> Saved best model (val_loss: {best_val_loss:.4f})")

        if early_stopping(val_metrics["val_loss"]):
            print(f"Early stopping at epoch {epoch}")
            break

    history_path = config.output_dir / "training_history.json"
    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)

    print(f"\nTraining complete. Best val_loss: {best_val_loss:.4f}")
    print(f"Checkpoint: {best_checkpoint}")
    print(f"History: {history_path}")

    return best_checkpoint


if __name__ == "__main__":
    train()
