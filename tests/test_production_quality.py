"""Production quality and integration tests.

Tests covering:
- HIPAA-aware logging (no PII in log output)
- End-to-end pipeline integration
- All disease types through full pipeline
- Error handling
- Security headers
- Data validation
"""

from __future__ import annotations

import io
import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.models.classifier import ClassificationResult, DiseaseLabel, RetinalClassifier
from app.models.risk_scoring import ClinicalMetadata, RiskScorer
from app.models.severity import SeverityGrader
from app.preprocessing.pipeline import RetinalPreprocessor
from app.reporting.clinical_report import DISCLAIMER, ClinicalReportGenerator
from tests.conftest import (
    make_amd_fundus,
    make_cataracts_fundus,
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
def pipeline_components() -> dict:
    return {
        "classifier": RetinalClassifier(demo_mode=True),
        "grader": SeverityGrader(),
        "scorer": RiskScorer(),
        "preprocessor": RetinalPreprocessor(),
        "reporter": ClinicalReportGenerator(),
    }


# ── Full pipeline integration ─────────────────────────────────────────────────

class TestFullPipelineIntegration:
    """Test the complete analysis pipeline for all disease types."""

    @pytest.mark.parametrize("disease,make_fn", [
        ("normal", make_normal_fundus),
        ("diabetic_retinopathy", make_diabetic_retinopathy_fundus),
        ("glaucoma", make_glaucoma_fundus),
        ("amd", make_amd_fundus),
        ("cataracts", make_cataracts_fundus),
    ])
    def test_full_pipeline_each_disease(self, disease, make_fn, pipeline_components):
        """Full pipeline runs without error for all disease types."""
        image = make_fn()
        comp = pipeline_components

        prep = comp["preprocessor"].process(image)
        import numpy as np
        features = RetinalPreprocessor.extract_image_features(np.array(prep.processed_image))
        cls = comp["classifier"].classify(prep.processed_image)
        sev = comp["grader"].grade(cls, features)
        risk = comp["scorer"].compute(cls, sev)
        report = comp["reporter"].generate(
            study_id=f"INTEG-{disease.upper()}",
            classification=cls,
            severity=sev,
            risk=risk,
        )

        assert isinstance(cls, ClassificationResult)
        assert 0.0 <= cls.confidence <= 1.0
        assert 0.0 <= risk.raw_score <= 1.0
        assert report.report_id
        assert len(report.findings_summary) > 20

    def test_all_synthetics_correctly_classified_end_to_end(self, pipeline_components):
        """Critical: heuristic must classify all synthetic images correctly."""
        expected = {
            "normal": (make_normal_fundus, DiseaseLabel.NORMAL),
            "dr": (make_diabetic_retinopathy_fundus, DiseaseLabel.DIABETIC_RETINOPATHY),
            "glaucoma": (make_glaucoma_fundus, DiseaseLabel.GLAUCOMA),
            "amd": (make_amd_fundus, DiseaseLabel.AMD),
            "cataracts": (make_cataracts_fundus, DiseaseLabel.CATARACTS),
        }
        comp = pipeline_components
        for name, (make_fn, expected_label) in expected.items():
            image = make_fn()
            prep = comp["preprocessor"].process(image)
            cls = comp["classifier"].classify(prep.processed_image)
            assert cls.predicted_label == expected_label, (
                f"FAILED: {name} → expected {expected_label.value}, "
                f"got {cls.predicted_label.value} (conf={cls.confidence:.2f})"
            )

    def test_report_generation_for_all_diseases(self, pipeline_components):
        """Reports generated for all disease/severity combinations."""
        comp = pipeline_components
        for label in DiseaseLabel:
            probs = {lbl.value: 0.0 for lbl in DiseaseLabel}
            probs[label.value] = 0.80
            cls = ClassificationResult(
                predicted_label=label, confidence=0.80, probabilities=probs
            )
            sev = comp["grader"].grade(cls)
            risk = comp["scorer"].compute(cls, sev)
            report = comp["reporter"].generate(
                study_id=f"ALL-{label.value}",
                classification=cls,
                severity=sev,
                risk=risk,
            )
            assert report.findings_summary
            assert report.clinical_impression
            assert report.disclaimer == DISCLAIMER


# ── HIPAA compliance ──────────────────────────────────────────────────────────

class TestHIPAACompliance:
    def test_no_pii_fields_in_classification_result(self):
        """ClassificationResult must not store any PII."""
        result = ClassificationResult(
            predicted_label=DiseaseLabel.NORMAL,
            confidence=0.95,
            probabilities={lbl.value: 0.2 for lbl in DiseaseLabel},
        )
        pii_fields = {"patient_name", "name", "dob", "ssn", "mrn", "address", "phone"}
        result_fields = set(vars(result).keys())
        assert pii_fields.isdisjoint(result_fields)

    def test_clinical_metadata_no_pii_identifiers(self):
        """ClinicalMetadata must not include direct patient identifiers."""
        meta = ClinicalMetadata()
        pii_fields = {"patient_name", "name", "dob", "date_of_birth", "ssn", "mrn"}
        meta_fields = set(vars(meta).keys())
        assert pii_fields.isdisjoint(meta_fields)

    def test_report_study_id_is_opaque(self):
        """Report stores study_id only — not patient name or DOB."""
        gen = ClinicalReportGenerator()
        grader = SeverityGrader()
        scorer = RiskScorer()
        probs = {lbl.value: 0.0 for lbl in DiseaseLabel}
        probs[DiseaseLabel.NORMAL.value] = 0.95
        cls = ClassificationResult(
            predicted_label=DiseaseLabel.NORMAL, confidence=0.95, probabilities=probs
        )
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        report = gen.generate(study_id="OPAQUE-XYZ-789", classification=cls, severity=sev, risk=risk)

        # Only opaque study_id, no personal data
        assert report.study_id == "OPAQUE-XYZ-789"
        assert not hasattr(report, "patient_name")
        assert not hasattr(report, "date_of_birth")

    def test_api_response_no_pii_in_report(self, client):
        img_bytes = image_to_bytes(make_normal_fundus())
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
        )
        body = str(resp.json())
        assert "patient_name" not in body.lower()
        assert "date_of_birth" not in body.lower()
        assert "social_security" not in body.lower()

    def test_audit_log_no_pii(self, caplog):
        """Verify no PII appears in audit logs during API calls."""
        with caplog.at_level(logging.INFO):
            with TestClient(app) as client:
                img_bytes = image_to_bytes(make_normal_fundus())
                client.post(
                    "/api/v1/analyze",
                    files={"file": ("patient_john_doe.jpg", img_bytes, "image/jpeg")},
                    data={"study_id": "AUDIT-TEST-001"},
                )
        # Log output must not contain any patient names
        log_text = caplog.text.lower()
        assert "john_doe" not in log_text
        assert "john doe" not in log_text


# ── Security headers ──────────────────────────────────────────────────────────

class TestSecurityHeaders:
    def test_x_content_type_options(self, client):
        resp = client.get("/health")
        header = resp.headers.get("x-content-type-options", "")
        assert header == "nosniff"

    def test_x_frame_options(self, client):
        resp = client.get("/health")
        header = resp.headers.get("x-frame-options", "")
        assert header == "DENY"

    def test_cache_control_no_store(self, client):
        resp = client.get("/health")
        cc = resp.headers.get("cache-control", "")
        assert "no-store" in cc

    def test_request_id_uuid_format(self, client):
        resp = client.get("/health")
        request_id = resp.headers.get("x-request-id", "")
        # Should be a valid UUID
        try:
            uuid.UUID(request_id)
            valid = True
        except ValueError:
            valid = False
        assert valid


# ── Error handling ────────────────────────────────────────────────────────────

class TestErrorHandling:
    def test_invalid_image_bytes_returns_422(self, client):
        resp = client.post(
            "/api/v1/classify",
            files={"file": ("broken.jpg", b"not an image at all xxxx", "image/jpeg")},
        )
        assert resp.status_code == 422

    def test_missing_file_returns_422(self, client):
        resp = client.post("/api/v1/analyze")
        assert resp.status_code == 422

    def test_wrong_content_type_rejected(self, client):
        resp = client.post(
            "/api/v1/classify",
            files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert resp.status_code == 415

    def test_oversized_image_rejected(self, client):
        """Image over 20MB should be rejected."""
        large_bytes = b"x" * (21 * 1024 * 1024)
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("huge.jpg", large_bytes, "image/jpeg")},
        )
        assert resp.status_code == 413


# ── Data integrity ────────────────────────────────────────────────────────────

class TestDataIntegrity:
    def test_probabilities_always_sum_to_one(self, pipeline_components):
        comp = pipeline_components
        for make_fn in [
            make_normal_fundus, make_diabetic_retinopathy_fundus,
            make_glaucoma_fundus, make_amd_fundus, make_cataracts_fundus,
        ]:
            cls = comp["classifier"].classify(make_fn())
            total = sum(cls.probabilities.values())
            assert abs(total - 1.0) < 0.01, f"Probabilities sum to {total} != 1.0"

    def test_risk_score_bounded(self, pipeline_components):
        comp = pipeline_components
        for make_fn in [
            make_normal_fundus, make_diabetic_retinopathy_fundus,
            make_glaucoma_fundus, make_amd_fundus, make_cataracts_fundus,
        ]:
            cls = comp["classifier"].classify(make_fn())
            sev = comp["grader"].grade(cls)
            risk = comp["scorer"].compute(cls, sev)
            assert 0.0 <= risk.raw_score <= 1.0

    def test_severity_score_bounded(self, pipeline_components):
        comp = pipeline_components
        for make_fn in [
            make_normal_fundus, make_diabetic_retinopathy_fundus,
            make_glaucoma_fundus, make_amd_fundus, make_cataracts_fundus,
        ]:
            cls = comp["classifier"].classify(make_fn())
            sev = comp["grader"].grade(cls)
            assert 0.0 <= sev.severity_score <= 1.0

    def test_report_ids_are_unique_across_batch(self, pipeline_components):
        """Each report in a batch should have a unique ID."""
        comp = pipeline_components
        report_ids = set()
        for _ in range(10):
            probs = {lbl.value: 0.0 for lbl in DiseaseLabel}
            probs[DiseaseLabel.NORMAL.value] = 0.95
            cls = ClassificationResult(
                predicted_label=DiseaseLabel.NORMAL, confidence=0.95, probabilities=probs
            )
            sev = comp["grader"].grade(cls)
            risk = comp["scorer"].compute(cls, sev)
            report = comp["reporter"].generate(
                study_id=str(uuid.uuid4()), classification=cls, severity=sev, risk=risk
            )
            report_ids.add(report.report_id)
        assert len(report_ids) == 10

    def test_api_response_classification_confidence_in_range(self, client):
        img_bytes = image_to_bytes(make_normal_fundus())
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
        )
        conf = resp.json()["classification"]["confidence"]
        assert 0.0 <= conf <= 1.0

    def test_preprocessed_image_correct_size(self, pipeline_components):
        comp = pipeline_components
        for make_fn in [make_normal_fundus, make_glaucoma_fundus]:
            prep = comp["preprocessor"].process(make_fn())
            assert prep.processed_image.size == (224, 224)
