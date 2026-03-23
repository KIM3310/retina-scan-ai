"""Runtime monitoring and engineering-validation helpers.

These surfaces are intentionally framed as engineering / portfolio validation
artifacts. They are not clinical validation claims.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.monitoring.resource_pack import data_files as resource_pack_files
from app.monitoring.resource_pack import (
    external_data_summary,
    load_clinical_cases,
    load_quality_scenarios,
    load_release_checks,
    resource_pack_summary,
)
from app.monitoring.resource_pack import (
    load_validation_cases as load_resource_validation_cases,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
EVALS_DIR = REPO_ROOT / "evals"
ARTIFACTS_DIR = EVALS_DIR / "artifacts"
VALIDATION_SUMMARY_PATH = ARTIFACTS_DIR / "synthetic_validation_summary.json"
MODEL_CARD_PATH = DOCS_DIR / "model-card.md"
RISK_REGISTER_PATH = DOCS_DIR / "risk-register.md"
VALIDATION_PLAN_PATH = DOCS_DIR / "validation-plan.md"
DEPLOYMENT_PATH = DOCS_DIR / "deployment.md"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
LOW_QUALITY_THRESHOLD = 0.55


def _round(value: float) -> float:
    return round(float(value), 2)


def _percentage(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _path_status(path: Path) -> dict:
    return {
        "present": path.exists(),
        "path": str(path.relative_to(REPO_ROOT)),
    }


@dataclass
class RuntimeMonitor:
    """In-memory monitor for runtime and engineering validation surfaces."""

    start_time: float = field(default_factory=time.time)
    total_inferences: int = 0
    low_quality_inferences: int = 0
    recent_latencies_ms: list[float] = field(default_factory=list)
    quality_flag_counts: dict[str, int] = field(default_factory=dict)
    last_model_architecture: str = "unknown"
    last_model_mode: str = "unknown"
    last_inference_timestamp: float | None = None

    def record_inference(
        self,
        *,
        preprocessing: dict,
        model_info: dict,
        elapsed_ms: float,
    ) -> None:
        """Record one completed inference pipeline."""
        self.total_inferences += 1
        self.last_inference_timestamp = time.time()
        self.last_model_architecture = str(model_info.get("architecture", "unknown"))
        self.last_model_mode = str(model_info.get("mode", "unknown"))

        quality_score = float(preprocessing.get("quality_score", 1.0))
        quality_flags = [str(flag) for flag in preprocessing.get("quality_flags", [])]

        if quality_score < LOW_QUALITY_THRESHOLD or quality_flags:
            self.low_quality_inferences += 1

        for flag in quality_flags:
            self.quality_flag_counts[flag] = self.quality_flag_counts.get(flag, 0) + 1

        self.recent_latencies_ms.append(_round(elapsed_ms))
        if len(self.recent_latencies_ms) > 200:
            self.recent_latencies_ms.pop(0)

    def _latency_summary(self) -> dict:
        if not self.recent_latencies_ms:
            return {
                "sample_window": 0,
                "avg_ms": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
            }

        ordered = sorted(self.recent_latencies_ms)
        count = len(ordered)
        p50_idx = int((count - 1) * 0.50)
        p95_idx = int((count - 1) * 0.95)
        return {
            "sample_window": count,
            "avg_ms": _round(sum(ordered) / count),
            "p50_ms": _round(ordered[p50_idx]),
            "p95_ms": _round(ordered[p95_idx]),
        }

    def get_validation_summary(self) -> dict:
        """Return the bundled engineering-validation artifact."""
        payload = _load_json(VALIDATION_SUMMARY_PATH)
        if payload is not None:
            return payload

        return {
            "artifact_version": "missing",
            "evaluation_tier": "engineering_synthetic",
            "clinical_validation": "not_performed",
            "status": "missing_artifact",
            "limitations": [
                "Validation artifact not generated yet.",
                "No clinical validation is claimed by this repository.",
            ],
            "artifact_path": str(VALIDATION_SUMMARY_PATH.relative_to(REPO_ROOT)),
        }

    def get_resource_pack(self) -> dict:
        """Return the built-in synthetic review pack."""
        return {
            "resource_pack_id": "retina-scan-ai-resource-pack-v1",
            "intended_use": "portfolio review and engineering discussion",
            "clinical_validation": "not_claimed",
            "reviewer_fast_path": [
                "/health",
                "/api/v1/ops/resource-pack",
                "/api/v1/ops/validation-summary",
                "/api/v1/ops/monitoring",
                "/api/v1/ops/release-readiness",
            ],
            "summary": resource_pack_summary(),
            "external_data": external_data_summary(),
            "clinical_cases": list(load_clinical_cases()),
            "quality_scenarios": list(load_quality_scenarios()),
            "validation_cases": list(load_resource_validation_cases()),
            "release_checks": list(load_release_checks()),
            "files": {
                key: str(path.relative_to(REPO_ROOT))
                for key, path in resource_pack_files().items()
            },
        }

    def get_monitoring_snapshot(self) -> dict:
        """Return a compact operational snapshot for portfolio review."""
        uptime_seconds = time.time() - self.start_time
        return {
            "intended_use": "engineering review and portfolio demonstration",
            "clinical_validation": "not_claimed",
            "reviewer_fast_path": [
                "/health",
                "/api/v1/ops/resource-pack",
                "/api/v1/ops/validation-summary",
                "/api/v1/ops/monitoring",
                "/api/v1/ops/release-readiness",
            ],
            "runtime": {
                "uptime_seconds": _round(uptime_seconds),
                "total_inferences": self.total_inferences,
                "last_model_architecture": self.last_model_architecture,
                "last_model_mode": self.last_model_mode,
                "latency_ms": self._latency_summary(),
            },
            "image_quality": {
                "low_quality_threshold": LOW_QUALITY_THRESHOLD,
                "low_quality_inferences": self.low_quality_inferences,
                "low_quality_rate_pct": _percentage(
                    self.low_quality_inferences,
                    self.total_inferences,
                ),
                "quality_flag_counts": dict(sorted(self.quality_flag_counts.items())),
            },
            "artifact_status": {
                "validation_summary": _path_status(VALIDATION_SUMMARY_PATH),
                "model_card": _path_status(MODEL_CARD_PATH),
                "risk_register": _path_status(RISK_REGISTER_PATH),
                "validation_plan": _path_status(VALIDATION_PLAN_PATH),
                "deployment_doc": _path_status(DEPLOYMENT_PATH),
                "ci_workflow": _path_status(CI_WORKFLOW_PATH),
            },
            "resource_pack": resource_pack_summary(),
        }

    def get_release_readiness(self) -> dict:
        """Return a portfolio-safe readiness summary.

        This intentionally avoids production or clinical-readiness claims.
        """
        checks = {
            "engineering_validation_artifact": VALIDATION_SUMMARY_PATH.exists(),
            "model_card": MODEL_CARD_PATH.exists(),
            "risk_register": RISK_REGISTER_PATH.exists(),
            "validation_plan": VALIDATION_PLAN_PATH.exists(),
            "deployment_doc": DEPLOYMENT_PATH.exists(),
            "ci_workflow": CI_WORKFLOW_PATH.exists(),
            "resource_pack": all(path.exists() for path in resource_pack_files().values()),
        }
        blockers = [name for name, passed in checks.items() if not passed]

        next_actions = [
            "Keep synthetic/offline evaluation language separate from clinical validation claims.",
            "Train and validate on representative real-world datasets before making sensitivity/specificity claims.",
        ]
        if self.last_model_mode == "demo_heuristic":
            next_actions.append(
                "Current runtime uses demo_heuristic mode; pair with trained weights and audited dataset lineage before any clinical deployment discussion."
            )

        return {
            "status": "portfolio_review_ready" if not blockers else "needs_attention",
            "intended_use": "portfolio review and engineering discussion",
            "clinical_validation": "not_claimed",
            "reviewer_fast_path": [
                "/health",
                "/api/v1/ops/resource-pack",
                "/api/v1/ops/validation-summary",
                "/api/v1/ops/monitoring",
                "/api/v1/ops/release-readiness",
            ],
            "checks": checks,
            "blockers": blockers,
            "next_actions": next_actions,
        }
