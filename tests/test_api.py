"""Tests for FastAPI routes and endpoints."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from tests.conftest import (
    make_diabetic_retinopathy_fundus,
    make_glaucoma_fundus,
    make_normal_fundus,
)


def image_to_bytes(img: Image.Image, fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def normal_jpeg() -> bytes:
    return image_to_bytes(make_normal_fundus())


@pytest.fixture
def dr_jpeg() -> bytes:
    return image_to_bytes(make_diabetic_retinopathy_fundus())


@pytest.fixture
def glaucoma_png() -> bytes:
    return image_to_bytes(make_glaucoma_fundus(), fmt="PNG")


# ── Root and health endpoints ─────────────────────────────────────────────────

class TestSystemEndpoints:
    def test_root_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_has_name(self, client):
        resp = client.get("/")
        assert resp.json()["name"] == "Retina-Scan-AI"

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_status_healthy(self, client):
        resp = client.get("/health")
        assert resp.json()["status"] == "healthy"

    def test_health_components_ready(self, client):
        resp = client.get("/health")
        components = resp.json()["components"]
        for v in components.values():
            assert v == "ready"

    def test_security_headers_present(self, client):
        resp = client.get("/health")
        assert "x-content-type-options" in resp.headers or "X-Content-Type-Options" in resp.headers

    def test_x_request_id_header(self, client):
        resp = client.get("/health")
        assert "x-request-id" in resp.headers or "X-Request-ID" in resp.headers

    def test_cache_control_no_store(self, client):
        resp = client.get("/health")
        cc = resp.headers.get("cache-control", "") or resp.headers.get("Cache-Control", "")
        assert "no-store" in cc


# ── /api/v1/diseases ──────────────────────────────────────────────────────────

class TestDiseasesEndpoint:
    def test_diseases_returns_200(self, client):
        resp = client.get("/api/v1/diseases")
        assert resp.status_code == 200

    def test_diseases_returns_5_entries(self, client):
        resp = client.get("/api/v1/diseases")
        assert len(resp.json()) == 5

    def test_diseases_have_required_fields(self, client):
        resp = client.get("/api/v1/diseases")
        for disease in resp.json():
            assert "label" in disease
            assert "display_name" in disease
            assert "icd10_code" in disease
            assert "description" in disease

    def test_diseases_includes_dr(self, client):
        resp = client.get("/api/v1/diseases")
        labels = [d["label"] for d in resp.json()]
        assert "diabetic_retinopathy" in labels

    def test_diseases_includes_normal(self, client):
        resp = client.get("/api/v1/diseases")
        labels = [d["label"] for d in resp.json()]
        assert "normal" in labels


# ── /api/v1/model/info ────────────────────────────────────────────────────────

class TestModelInfoEndpoint:
    def test_model_info_returns_200(self, client):
        resp = client.get("/api/v1/model/info")
        assert resp.status_code == 200

    def test_model_info_has_architecture(self, client):
        resp = client.get("/api/v1/model/info")
        assert resp.json()["architecture"] == "ResNet18"

    def test_model_info_has_num_classes(self, client):
        resp = client.get("/api/v1/model/info")
        assert resp.json()["num_classes"] == 5

    def test_model_info_mode_is_demo(self, client):
        resp = client.get("/api/v1/model/info")
        assert resp.json()["mode"] == "demo_heuristic"


# ── /api/v1/classify ─────────────────────────────────────────────────────────

class TestClassifyEndpoint:
    def test_classify_jpeg_returns_200(self, client, normal_jpeg):
        resp = client.post(
            "/api/v1/classify",
            files={"file": ("normal.jpg", normal_jpeg, "image/jpeg")},
        )
        assert resp.status_code == 200

    def test_classify_png_returns_200(self, client, glaucoma_png):
        resp = client.post(
            "/api/v1/classify",
            files={"file": ("glaucoma.png", glaucoma_png, "image/png")},
        )
        assert resp.status_code == 200

    def test_classify_response_has_classification(self, client, normal_jpeg):
        resp = client.post(
            "/api/v1/classify",
            files={"file": ("test.jpg", normal_jpeg, "image/jpeg")},
        )
        data = resp.json()
        assert "classification" in data
        assert "predicted_label" in data["classification"]
        assert "confidence" in data["classification"]

    def test_classify_response_has_model_info(self, client, normal_jpeg):
        resp = client.post(
            "/api/v1/classify",
            files={"file": ("test.jpg", normal_jpeg, "image/jpeg")},
        )
        data = resp.json()
        assert "model_info" in data

    def test_classify_with_study_id(self, client, normal_jpeg):
        resp = client.post(
            "/api/v1/classify",
            files={"file": ("test.jpg", normal_jpeg, "image/jpeg")},
            data={"study_id": "TEST-CLASSIFY-001"},
        )
        assert resp.status_code == 200
        assert resp.json()["study_id"] == "TEST-CLASSIFY-001"

    def test_classify_normal_image(self, client, normal_jpeg):
        resp = client.post(
            "/api/v1/classify",
            files={"file": ("normal.jpg", normal_jpeg, "image/jpeg")},
        )
        data = resp.json()
        assert data["classification"]["predicted_label"] == "normal"

    def test_classify_no_file_returns_422(self, client):
        resp = client.post("/api/v1/classify")
        assert resp.status_code == 422

    def test_classify_invalid_content_type_rejected(self, client):
        resp = client.post(
            "/api/v1/classify",
            files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
        )
        assert resp.status_code == 415


# ── /api/v1/analyze ──────────────────────────────────────────────────────────

class TestAnalyzeEndpoint:
    def test_analyze_returns_200(self, client, normal_jpeg):
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", normal_jpeg, "image/jpeg")},
        )
        assert resp.status_code == 200

    def test_analyze_response_structure(self, client, normal_jpeg):
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", normal_jpeg, "image/jpeg")},
        )
        data = resp.json()
        required_keys = {
            "request_id", "study_id", "classification",
            "severity", "risk", "report", "preprocessing", "model_info"
        }
        assert required_keys.issubset(set(data.keys()))

    def test_analyze_classification_valid(self, client, normal_jpeg):
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", normal_jpeg, "image/jpeg")},
        )
        cls = resp.json()["classification"]
        assert cls["predicted_label"] in [
            "normal", "diabetic_retinopathy", "glaucoma", "amd", "cataracts"
        ]
        assert 0.0 <= cls["confidence"] <= 1.0

    def test_analyze_severity_present(self, client, normal_jpeg):
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", normal_jpeg, "image/jpeg")},
        )
        sev = resp.json()["severity"]
        assert "severity" in sev
        assert "severity_score" in sev

    def test_analyze_risk_present(self, client, normal_jpeg):
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", normal_jpeg, "image/jpeg")},
        )
        risk = resp.json()["risk"]
        assert "risk_level" in risk
        assert "raw_score" in risk

    def test_analyze_report_present(self, client, normal_jpeg):
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", normal_jpeg, "image/jpeg")},
        )
        report = resp.json()["report"]
        assert "report_id" in report
        assert "findings_summary" in report
        assert "disclaimer" in report

    def test_analyze_with_clinical_metadata(self, client, dr_jpeg):
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("dr.jpg", dr_jpeg, "image/jpeg")},
            data={
                "study_id": "TEST-META-001",
                "patient_age": "65",
                "hba1c": "9.0",
                "has_hypertension": "true",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["study_id"] == "TEST-META-001"

    def test_analyze_no_file_returns_422(self, client):
        resp = client.post("/api/v1/analyze")
        assert resp.status_code == 422

    def test_analyze_dr_image(self, client, dr_jpeg):
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("dr.jpg", dr_jpeg, "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["classification"]["predicted_label"] == "diabetic_retinopathy"

    def test_analyze_preprocessing_metadata(self, client, normal_jpeg):
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", normal_jpeg, "image/jpeg")},
        )
        prep = resp.json()["preprocessing"]
        assert "quality_score" in prep
        assert "clahe_applied" in prep

    def test_analyze_report_no_pii(self, client, normal_jpeg):
        """Report should not contain PII fields."""
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", normal_jpeg, "image/jpeg")},
        )
        report_text = str(resp.json()["report"])
        assert "patient_name" not in report_text.lower()
        assert "date_of_birth" not in report_text.lower()
