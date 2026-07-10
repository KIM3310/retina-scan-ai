"""Regression tests for safe model checkpoint loading."""

from pathlib import Path

import pytest
import torch

from src.checkpoints import UnsupportedCheckpointError, load_model_checkpoint


def test_load_model_checkpoint_accepts_repo_checkpoint(tmp_path: Path):
    checkpoint_path = tmp_path / "repo-checkpoint.pth"
    state_dict = {
        "backbone.conv1.weight": torch.zeros(1),
        "classifier.bias": torch.ones(1),
    }
    torch.save(
        {
            "epoch": 1,
            "model_state_dict": state_dict,
            "config": {"num_classes": 2, "img_size": 128},
        },
        checkpoint_path,
    )

    checkpoint = load_model_checkpoint(checkpoint_path, map_location=torch.device("cpu"))

    assert checkpoint.model_state_dict == state_dict
    assert checkpoint.config == {"num_classes": 2, "img_size": 128}


def test_load_model_checkpoint_rejects_missing_model_state_dict(tmp_path: Path):
    checkpoint_path = tmp_path / "unsupported-checkpoint.pth"
    torch.save({"weights": {"layer.weight": torch.zeros(1)}}, checkpoint_path)

    with pytest.raises(UnsupportedCheckpointError, match="model_state_dict"):
        load_model_checkpoint(checkpoint_path, map_location=torch.device("cpu"))


def test_load_model_checkpoint_rejects_non_mapping_model_state_dict(tmp_path: Path):
    checkpoint_path = tmp_path / "bad-state-dict.pth"
    torch.save({"model_state_dict": ["layer.weight"]}, checkpoint_path)

    with pytest.raises(UnsupportedCheckpointError, match="state dict"):
        load_model_checkpoint(checkpoint_path, map_location=torch.device("cpu"))


def test_load_model_checkpoint_rejects_non_tensor_state_values(tmp_path: Path):
    checkpoint_path = tmp_path / "bad-state-value.pth"
    torch.save({"model_state_dict": {"layer.weight": "not-a-tensor"}}, checkpoint_path)

    with pytest.raises(UnsupportedCheckpointError, match="torch.Tensor"):
        load_model_checkpoint(checkpoint_path, map_location=torch.device("cpu"))
