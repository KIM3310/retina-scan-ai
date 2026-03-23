"""Built-in synthetic review resources for Retina-Scan-AI."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"


def data_files() -> dict[str, Path]:
    return {
        "clinical_cases": DATA_DIR / "clinical_case_pack.json",
        "quality_scenarios": DATA_DIR / "quality_scenarios.json",
        "validation_cases": DATA_DIR / "validation_cases.json",
        "release_checks": DATA_DIR / "release_checks.json",
    }


@lru_cache(maxsize=1)
def load_clinical_cases() -> tuple[dict[str, Any], ...]:
    return tuple(_load_json("clinical_cases"))


@lru_cache(maxsize=1)
def load_quality_scenarios() -> tuple[dict[str, Any], ...]:
    return tuple(_load_json("quality_scenarios"))


@lru_cache(maxsize=1)
def load_validation_cases() -> tuple[dict[str, Any], ...]:
    return tuple(_load_json("validation_cases"))


@lru_cache(maxsize=1)
def load_release_checks() -> tuple[dict[str, Any], ...]:
    return tuple(_load_json("release_checks"))


def resource_pack_summary() -> dict[str, int]:
    return {
        "clinical_case_count": len(load_clinical_cases()),
        "quality_scenario_count": len(load_quality_scenarios()),
        "validation_case_count": len(load_validation_cases()),
        "release_check_count": len(load_release_checks()),
    }


def raw_resource_bytes() -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in data_files().values()}


def _load_json(key: str) -> list[dict[str, Any]]:
    path = data_files()[key]
    payload = json.loads(path.read_text(encoding="utf-8"))
    return cast(list[dict[str, Any]], payload)
