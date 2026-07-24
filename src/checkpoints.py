"""Safe checkpoint loading utilities for model entrypoints."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch


class UnsupportedCheckpointError(ValueError):
    """Raised when a checkpoint does not match the supported repo schema."""


@dataclass(frozen=True)
class ModelCheckpoint:
    model_state_dict: dict[str, torch.Tensor]
    config: dict[str, Any]


def load_model_checkpoint(
    checkpoint_path: str | Path,
    map_location: torch.device | str,
) -> ModelCheckpoint:
    """Load a repo-produced model checkpoint without enabling pickle execution.

    Supported schema is the dictionary written by ``src.train.train`` with a
    ``model_state_dict`` mapping and an optional plain ``config`` mapping.
    """
    checkpoint = torch.load(checkpoint_path, map_location=map_location, weights_only=True)
    if not isinstance(checkpoint, Mapping):
        raise UnsupportedCheckpointError(
            "Unsupported checkpoint shape: expected a mapping with model_state_dict"
        )

    if "model_state_dict" not in checkpoint:
        raise UnsupportedCheckpointError("Unsupported checkpoint shape: missing model_state_dict")

    model_state_dict = _validate_model_state_dict(checkpoint["model_state_dict"])
    config = checkpoint.get("config", {})
    if config is None:
        config = {}
    if not isinstance(config, Mapping):
        raise UnsupportedCheckpointError(
            "Unsupported checkpoint shape: config must be a mapping when present"
        )

    return ModelCheckpoint(model_state_dict=model_state_dict, config=dict(config))


def _validate_model_state_dict(value: Any) -> dict[str, torch.Tensor]:
    if not isinstance(value, Mapping):
        raise UnsupportedCheckpointError(
            "Unsupported checkpoint shape: model_state_dict must be a state dict mapping"
        )

    state_dict: dict[str, torch.Tensor] = {}
    for key, tensor in value.items():
        if not isinstance(key, str):
            raise UnsupportedCheckpointError(
                "Unsupported checkpoint shape: state dict keys must be strings"
            )
        if not isinstance(tensor, torch.Tensor):
            raise UnsupportedCheckpointError(
                "Unsupported checkpoint shape: state dict values must be torch.Tensor instances"
            )
        state_dict[key] = tensor
    return state_dict
