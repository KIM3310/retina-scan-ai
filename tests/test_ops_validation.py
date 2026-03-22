"""Tests for medical-AI ops and engineering-validation surfaces."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from evals.generate_validation_artifacts import build_validation_artifact


def test_build_validation_artifact_is_portfolio_safe() -> None:
    artifact = build_validation_artifact()

    assert artifact["evaluation_tier"] == "engineering_synthetic"
    assert artifact["clinical_validation"] == "not_performed"
    assert artifact["summary"]["total_cases"] > 0
    assert "limitations" in artifact
    assert any("synthetic" in item.lower() for item in artifact["limitations"])


def test_build_validation_artifact_confusion_matrix_balances() -> None:
    artifact = build_validation_artifact()
    total = artifact["summary"]["total_cases"]
    matrix_total = sum(sum(row.values()) for row in artifact["confusion_matrix"].values())
    assert matrix_total == total


def test_ops_validation_summary_endpoint_returns_200() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/ops/validation-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["evaluation_tier"] == "engineering_synthetic"
    assert payload["clinical_validation"] == "not_performed"


def test_ops_monitoring_endpoint_contains_runtime_and_artifacts() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/ops/monitoring")

    assert response.status_code == 200
    payload = response.json()
    assert payload["clinical_validation"] == "not_claimed"
    assert "runtime" in payload
    assert "artifact_status" in payload
    assert payload["reviewer_fast_path"][0] == "/health"
    assert payload["artifact_status"]["model_card"]["present"] is True


def test_ops_release_readiness_is_portfolio_framed() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/ops/release-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["clinical_validation"] == "not_claimed"
    assert payload["status"] in {"portfolio_review_ready", "needs_attention"}
    assert payload["reviewer_fast_path"][1] == "/api/v1/ops/validation-summary"
    assert "engineering_validation_artifact" in payload["checks"]
