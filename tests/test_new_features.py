"""Tests for all new production-grade features.

Covers:
- Preprocessing: optic disc detection, blur detection, enhanced quality flags
- Classifier: attention maps, confidence calibration, ensemble mode, new fields
- Reporting: laterality, FHIR format, follow-up scheduling, ICD-10 laterality
- API: batch endpoint, /metrics endpoint, FHIR format, rate limit headers, laterality
- Edge cases: corrupted images, extreme sizes, grayscale vs RGB
- Performance/benchmark: processing time bounds
"""

from __future__ import annotations

import io
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.models.classifier import (
    AttentionMap,
    ClassificationResult,
    DiseaseLabel,
    RetinalClassifier,
)
from app.models.risk_scoring import RiskScorer
from app.models.severity import SeverityGrader
from app.preprocessing.pipeline import (
    OpticDiscResult,
    RetinalPreprocessor,
)
from app.reporting.clinical_report import (
    ClinicalReportGenerator,
    Laterality,
)
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


def make_cls(label: DiseaseLabel, confidence: float = 0.80) -> ClassificationResult:
    probs = {lbl.value: 0.0 for lbl in DiseaseLabel}
    probs[label.value] = confidence
    return ClassificationResult(predicted_label=label, confidence=confidence, probabilities=probs)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def preprocessor() -> RetinalPreprocessor:
    return RetinalPreprocessor()


@pytest.fixture
def classifier() -> RetinalClassifier:
    return RetinalClassifier(demo_mode=True, generate_attention_maps=True)


@pytest.fixture
def classifier_no_attn() -> RetinalClassifier:
    return RetinalClassifier(demo_mode=True, generate_attention_maps=False)


@pytest.fixture
def generator() -> ClinicalReportGenerator:
    return ClinicalReportGenerator()


@pytest.fixture
def grader() -> SeverityGrader:
    return SeverityGrader()


@pytest.fixture
def scorer() -> RiskScorer:
    return RiskScorer()


# ── OpticDiscResult dataclass ─────────────────────────────────────────────────

class TestOpticDiscResult:
    def test_to_dict_keys(self):
        od = OpticDiscResult(detected=True, center_x=112, center_y=112, radius_estimate=30, confidence=0.8)
        d = od.to_dict()
        assert "detected" in d
        assert "center_x" in d
        assert "center_y" in d
        assert "radius_estimate" in d
        assert "confidence" in d

    def test_not_detected_serializes(self):
        od = OpticDiscResult(detected=False, confidence=0.0)
        d = od.to_dict()
        assert d["detected"] is False
        assert d["center_x"] is None

    def test_confidence_rounded(self):
        od = OpticDiscResult(detected=True, center_x=100, center_y=100, radius_estimate=20, confidence=0.12345)
        assert od.to_dict()["confidence"] == round(0.12345, 4)


# ── Optic disc detection ──────────────────────────────────────────────────────

class TestOpticDiscDetection:
    def test_glaucoma_image_detects_disc(self, preprocessor):
        """Glaucoma synthetic image has large bright disc — should detect."""
        result = preprocessor.process(make_glaucoma_fundus())
        assert result.optic_disc is not None
        assert result.optic_disc.detected is True

    def test_detected_disc_has_center(self, preprocessor):
        result = preprocessor.process(make_glaucoma_fundus())
        assert result.optic_disc.center_x is not None
        assert result.optic_disc.center_y is not None

    def test_detected_disc_has_radius(self, preprocessor):
        result = preprocessor.process(make_glaucoma_fundus())
        assert result.optic_disc.radius_estimate is not None
        assert result.optic_disc.radius_estimate > 0

    def test_disc_confidence_in_range(self, preprocessor):
        result = preprocessor.process(make_glaucoma_fundus())
        assert 0.0 <= result.optic_disc.confidence <= 1.0

    def test_optic_disc_in_to_dict(self, preprocessor):
        result = preprocessor.process(make_glaucoma_fundus())
        d = result.to_dict()
        assert "optic_disc" in d

    def test_no_optic_disc_detection_when_disabled(self):
        p = RetinalPreprocessor(detect_optic_disc=False)
        result = p.process(make_normal_fundus())
        assert result.optic_disc is None

    def test_underexposed_may_not_detect(self):
        """Very dark image should not produce high-confidence disc detection."""
        p = RetinalPreprocessor(detect_optic_disc=True)
        dark = Image.fromarray(np.full((256, 256, 3), 5, dtype=np.uint8), mode="RGB")
        result = p.process(dark)
        # Either not detected, or low confidence
        if result.optic_disc and result.optic_disc.detected:
            assert result.optic_disc.confidence < 0.8


# ── Blur detection in quality ─────────────────────────────────────────────────

class TestBlurDetection:
    def test_blurry_image_flagged(self, preprocessor):
        """A heavily blurred image should receive the 'blurry' quality flag."""
        arr = np.random.randint(50, 200, (256, 256, 3), dtype=np.uint8)
        import cv2
        blurred_arr = cv2.GaussianBlur(arr, (51, 51), 20)
        blurry_img = Image.fromarray(blurred_arr, mode="RGB")
        result = preprocessor.process(blurry_img)
        assert "blurry" in result.quality_flags

    def test_sharp_normal_image_not_blurry(self, preprocessor):
        result = preprocessor.process(make_glaucoma_fundus())
        # Glaucoma image has high contrast edges — should not be flagged blurry
        assert "blurry" not in result.quality_flags

    def test_blurry_flag_lowers_quality_score(self, preprocessor):
        """Blurry image should score lower than sharp equivalent."""
        import cv2
        arr = np.random.randint(80, 180, (256, 256, 3), dtype=np.uint8)
        sharp_img = Image.fromarray(arr, mode="RGB")

        blurred_arr = cv2.GaussianBlur(arr, (51, 51), 30)
        blurry_img = Image.fromarray(blurred_arr, mode="RGB")

        sharp_result = preprocessor.process(sharp_img)
        blurry_result = preprocessor.process(blurry_img)
        assert blurry_result.quality_score <= sharp_result.quality_score

    def test_quality_penalty_map_includes_blurry(self, preprocessor):
        """Blurry flag must reduce the quality score below 1.0."""
        import cv2
        arr = np.full((256, 256, 3), 128, dtype=np.uint8)
        blurred = cv2.GaussianBlur(arr, (61, 61), 40)
        img = Image.fromarray(blurred, mode="RGB")
        result = preprocessor.process(img)
        assert result.quality_score < 1.0


# ── AttentionMap ──────────────────────────────────────────────────────────────

class TestAttentionMap:
    def test_attention_map_generated(self, classifier):
        result = classifier.classify(make_normal_fundus())
        assert result.attention_map is not None

    def test_attention_map_is_correct_type(self, classifier):
        result = classifier.classify(make_normal_fundus())
        assert isinstance(result.attention_map, AttentionMap)

    def test_attention_map_shape(self, classifier):
        result = classifier.classify(make_normal_fundus())
        h, w = result.attention_map.heatmap.shape
        assert h == 224 and w == 224

    def test_attention_map_values_in_range(self, classifier):
        result = classifier.classify(make_glaucoma_fundus())
        heatmap = result.attention_map.heatmap
        assert heatmap.min() >= 0.0
        assert heatmap.max() <= 1.0

    def test_attention_map_to_dict_keys(self, classifier):
        result = classifier.classify(make_normal_fundus())
        d = result.attention_map.to_dict()
        assert "method" in d
        assert "predicted_label" in d
        assert "shape" in d
        assert "max_activation" in d
        assert "mean_activation" in d

    def test_attention_map_method_is_gradcam_heuristic(self, classifier):
        result = classifier.classify(make_diabetic_retinopathy_fundus())
        assert result.attention_map.method == "gradcam_heuristic"

    def test_attention_map_none_when_disabled(self, classifier_no_attn):
        result = classifier_no_attn.classify(make_normal_fundus())
        assert result.attention_map is None

    def test_attention_map_in_to_dict_when_present(self, classifier):
        result = classifier.classify(make_amd_fundus())
        d = result.to_dict()
        assert "attention_map" in d

    def test_attention_map_not_in_dict_when_none(self, classifier_no_attn):
        result = classifier_no_attn.classify(make_normal_fundus())
        d = result.to_dict()
        assert "attention_map" not in d

    def test_all_disease_attention_maps_generated(self, classifier):
        for make_fn in [make_normal_fundus, make_diabetic_retinopathy_fundus,
                        make_glaucoma_fundus, make_amd_fundus, make_cataracts_fundus]:
            result = classifier.classify(make_fn())
            assert result.attention_map is not None
            assert result.attention_map.heatmap.max() >= 0.0


# ── Confidence calibration ─────────────────────────────────────────────────────

class TestConfidenceCalibration:
    def test_probabilities_sum_to_one_after_calibration(self, classifier):
        result = classifier.classify(make_normal_fundus())
        total = sum(result.probabilities.values())
        assert abs(total - 1.0) < 0.01

    def test_calibration_temperature_stored(self):
        c = RetinalClassifier(demo_mode=True, calibration_temperature=2.0)
        assert c.calibration_temperature == 2.0

    def test_higher_temperature_softens_distribution(self):
        """Higher temperature should produce lower max probability (softer dist)."""
        c_sharp = RetinalClassifier(demo_mode=True, calibration_temperature=0.5, generate_attention_maps=False)
        c_soft = RetinalClassifier(demo_mode=True, calibration_temperature=3.0, generate_attention_maps=False)
        img = make_glaucoma_fundus()
        r_sharp = c_sharp.classify(img)
        r_soft = c_soft.classify(img)
        # Softer temperature → lower max probability
        assert r_soft.confidence <= r_sharp.confidence

    def test_calibration_temperature_in_architecture_summary(self):
        c = RetinalClassifier(demo_mode=True, calibration_temperature=1.5)
        summary = c.get_model_architecture_summary()
        assert "calibration_temperature" in summary
        assert summary["calibration_temperature"] == 1.5


# ── Ensemble mode ─────────────────────────────────────────────────────────────

class TestEnsembleMode:
    def test_ensemble_mode_flag_stored(self):
        c = RetinalClassifier(demo_mode=True, ensemble_mode=True)
        assert c.ensemble_mode is True

    def test_ensemble_in_architecture_summary(self):
        c = RetinalClassifier(demo_mode=True, ensemble_mode=True)
        summary = c.get_model_architecture_summary()
        assert "ensemble_mode" in summary

    def test_attention_maps_enabled_in_summary(self):
        c = RetinalClassifier(demo_mode=True, generate_attention_maps=True)
        summary = c.get_model_architecture_summary()
        assert summary["attention_maps_enabled"] is True

    def test_ensemble_used_false_in_demo_mode(self, classifier):
        """In demo-only mode, ensemble_used should be False."""
        result = classifier.classify(make_normal_fundus())
        assert result.ensemble_used is False

    def test_ensemble_used_in_to_dict(self, classifier):
        result = classifier.classify(make_normal_fundus())
        d = result.to_dict()
        assert "ensemble_used" in d


# ── Laterality tracking ───────────────────────────────────────────────────────

class TestLaterality:
    def test_laterality_enum_values(self):
        assert Laterality.RIGHT.value == "OD"
        assert Laterality.LEFT.value == "OS"
        assert Laterality.BOTH.value == "OU"
        assert Laterality.UNSPECIFIED.value == "unspecified"

    def test_report_stores_laterality(self, generator, grader, scorer):
        cls = make_cls(DiseaseLabel.DIABETIC_RETINOPATHY, 0.80)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        report = generator.generate("LAT-001", cls, sev, risk, laterality=Laterality.RIGHT)
        assert report.laterality == "OD"

    def test_report_default_laterality_unspecified(self, generator, grader, scorer):
        cls = make_cls(DiseaseLabel.NORMAL)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        report = generator.generate("LAT-002", cls, sev, risk)
        assert report.laterality == "unspecified"

    def test_laterality_in_to_dict(self, generator, grader, scorer):
        cls = make_cls(DiseaseLabel.GLAUCOMA, 0.75)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        report = generator.generate("LAT-003", cls, sev, risk, laterality=Laterality.LEFT)
        d = report.to_dict()
        assert "laterality" in d
        assert d["laterality"] == "OS"

    def test_laterality_in_text_report(self, generator, grader, scorer):
        cls = make_cls(DiseaseLabel.DIABETIC_RETINOPATHY, 0.80)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        report = generator.generate("LAT-004", cls, sev, risk, laterality=Laterality.RIGHT)
        text = report.to_text()
        assert "OD" in text

    def test_icd10_with_laterality_right_eye(self, generator, grader, scorer):
        """DR ICD-10 code (E11.319) should get laterality suffix 1 for OD."""
        cls = make_cls(DiseaseLabel.DIABETIC_RETINOPATHY, 0.80)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        report = generator.generate("LAT-005", cls, sev, risk, laterality=Laterality.RIGHT)
        # E11.319 + "1" = E11.3191
        assert report.icd10_with_laterality.endswith("1")

    def test_icd10_no_laterality_for_normal(self, generator, grader, scorer):
        """Z-codes (normal) should not receive laterality suffix."""
        cls = make_cls(DiseaseLabel.NORMAL, 0.95)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        report = generator.generate("LAT-006", cls, sev, risk, laterality=Laterality.RIGHT)
        # Z01.01 should remain unchanged
        assert report.icd10_with_laterality == cls.icd10_code

    def test_icd10_with_laterality_in_to_dict(self, generator, grader, scorer):
        cls = make_cls(DiseaseLabel.GLAUCOMA, 0.75)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        report = generator.generate("LAT-007", cls, sev, risk, laterality=Laterality.BOTH)
        d = report.to_dict()
        assert "icd10_with_laterality" in d


# ── Follow-up scheduling ──────────────────────────────────────────────────────

class TestFollowUpScheduling:
    def test_follow_up_schedule_present_in_report(self, generator, grader, scorer):
        cls = make_cls(DiseaseLabel.DIABETIC_RETINOPATHY, 0.80)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        report = generator.generate("FU-001", cls, sev, risk)
        assert report.follow_up_schedule
        assert len(report.follow_up_schedule) > 10

    def test_follow_up_in_to_dict(self, generator, grader, scorer):
        cls = make_cls(DiseaseLabel.NORMAL, 0.95)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        report = generator.generate("FU-002", cls, sev, risk)
        d = report.to_dict()
        assert "follow_up_schedule" in d

    def test_follow_up_in_text_report(self, generator, grader, scorer):
        cls = make_cls(DiseaseLabel.DIABETIC_RETINOPATHY, 0.90)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        report = generator.generate("FU-003", cls, sev, risk)
        text = report.to_text()
        assert "FOLLOW-UP" in text

    def test_urgent_disease_has_urgent_follow_up(self, generator, grader, scorer):
        """Proliferative DR should mention urgent/emergency follow-up."""
        cls = make_cls(DiseaseLabel.DIABETIC_RETINOPATHY, 0.92)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        report = generator.generate("FU-004", cls, sev, risk)
        schedule_lower = report.follow_up_schedule.lower()
        assert any(word in schedule_lower for word in ["urgent", "emergency", "week", "immediate"])


# ── FHIR format ───────────────────────────────────────────────────────────────

class TestFHIRFormat:
    def _make_report(self, generator, grader, scorer, label=DiseaseLabel.DIABETIC_RETINOPATHY):
        cls = make_cls(label, 0.80)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        return generator.generate("FHIR-001", cls, sev, risk, laterality=Laterality.RIGHT)

    def test_fhir_resource_type(self, generator, grader, scorer):
        report = self._make_report(generator, grader, scorer)
        fhir = report.to_fhir()
        assert fhir["resourceType"] == "DiagnosticReport"

    def test_fhir_status_final(self, generator, grader, scorer):
        report = self._make_report(generator, grader, scorer)
        fhir = report.to_fhir()
        assert fhir["status"] == "final"

    def test_fhir_has_id(self, generator, grader, scorer):
        report = self._make_report(generator, grader, scorer)
        fhir = report.to_fhir()
        assert fhir["id"] == report.report_id

    def test_fhir_has_conclusion(self, generator, grader, scorer):
        report = self._make_report(generator, grader, scorer)
        fhir = report.to_fhir()
        assert "conclusion" in fhir
        assert len(fhir["conclusion"]) > 10

    def test_fhir_has_conclusion_code_with_icd10(self, generator, grader, scorer):
        report = self._make_report(generator, grader, scorer)
        fhir = report.to_fhir()
        codes = fhir["conclusionCode"]
        assert len(codes) > 0
        coding = codes[0]["coding"][0]
        assert "system" in coding
        assert "icd-10" in coding["system"].lower()

    def test_fhir_has_subject_with_study_id(self, generator, grader, scorer):
        report = self._make_report(generator, grader, scorer)
        fhir = report.to_fhir()
        assert fhir["subject"]["identifier"]["value"] == report.study_id

    def test_fhir_extensions_include_confidence(self, generator, grader, scorer):
        report = self._make_report(generator, grader, scorer)
        fhir = report.to_fhir()
        ext_urls = [e["url"] for e in fhir["extension"]]
        assert any("confidence" in url for url in ext_urls)

    def test_fhir_extensions_include_laterality(self, generator, grader, scorer):
        report = self._make_report(generator, grader, scorer)
        fhir = report.to_fhir()
        ext_urls = [e["url"] for e in fhir["extension"]]
        assert any("laterality" in url for url in ext_urls)

    def test_fhir_has_ophthalmology_category(self, generator, grader, scorer):
        report = self._make_report(generator, grader, scorer)
        fhir = report.to_fhir()
        categories = fhir["category"]
        oph_found = any(
            c["coding"][0]["code"] == "OPH"
            for c in categories
            if c.get("coding")
        )
        assert oph_found

    def test_fhir_api_endpoint(self, client):
        img_bytes = image_to_bytes(make_normal_fundus())
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
            data={"format": "fhir"},
        )
        assert resp.status_code == 200
        report = resp.json()["report"]
        assert report.get("resourceType") == "DiagnosticReport"


# ── Batch screening endpoint ──────────────────────────────────────────────────

class TestBatchEndpoint:
    def test_batch_single_image(self, client):
        img_bytes = image_to_bytes(make_normal_fundus())
        resp = client.post(
            "/api/v1/analyze/batch",
            files=[("files", ("img1.jpg", img_bytes, "image/jpeg"))],
        )
        assert resp.status_code == 200

    def test_batch_response_structure(self, client):
        img_bytes = image_to_bytes(make_normal_fundus())
        resp = client.post(
            "/api/v1/analyze/batch",
            files=[("files", ("img1.jpg", img_bytes, "image/jpeg"))],
        )
        data = resp.json()
        assert "total" in data
        assert "succeeded" in data
        assert "failed" in data
        assert "results" in data
        assert "request_id" in data

    def test_batch_multiple_images(self, client):
        files = [
            ("files", ("img1.jpg", image_to_bytes(make_normal_fundus()), "image/jpeg")),
            ("files", ("img2.jpg", image_to_bytes(make_diabetic_retinopathy_fundus()), "image/jpeg")),
            ("files", ("img3.jpg", image_to_bytes(make_glaucoma_fundus()), "image/jpeg")),
        ]
        resp = client.post("/api/v1/analyze/batch", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["succeeded"] == 3
        assert data["failed"] == 0

    def test_batch_results_count_matches_input(self, client):
        files = [
            ("files", (f"img{i}.jpg", image_to_bytes(make_normal_fundus()), "image/jpeg"))
            for i in range(5)
        ]
        resp = client.post("/api/v1/analyze/batch", files=files)
        data = resp.json()
        assert len(data["results"]) == 5

    def test_batch_each_result_has_study_id(self, client):
        files = [("files", ("img.jpg", image_to_bytes(make_normal_fundus()), "image/jpeg"))]
        resp = client.post("/api/v1/analyze/batch", files=files)
        for result in resp.json()["results"]:
            assert "study_id" in result
            assert result["study_id"]

    def test_batch_each_result_has_status(self, client):
        files = [("files", ("img.jpg", image_to_bytes(make_normal_fundus()), "image/jpeg"))]
        resp = client.post("/api/v1/analyze/batch", files=files)
        for result in resp.json()["results"]:
            assert result["status"] in ("success", "error")

    def test_batch_success_has_classification(self, client):
        files = [("files", ("img.jpg", image_to_bytes(make_normal_fundus()), "image/jpeg"))]
        resp = client.post("/api/v1/analyze/batch", files=files)
        result = resp.json()["results"][0]
        assert result["status"] == "success"
        assert result["classification"] is not None
        assert "predicted_label" in result["classification"]

    def test_batch_exceeded_limit_returns_400(self, client):
        files = [
            ("files", (f"img{i}.jpg", image_to_bytes(make_normal_fundus()), "image/jpeg"))
            for i in range(51)
        ]
        resp = client.post("/api/v1/analyze/batch", files=files)
        assert resp.status_code == 400

    def test_batch_with_invalid_image_partial_failure(self, client):
        files = [
            ("files", ("good.jpg", image_to_bytes(make_normal_fundus()), "image/jpeg")),
            ("files", ("bad.jpg", b"not an image", "image/jpeg")),
        ]
        resp = client.post("/api/v1/analyze/batch", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["succeeded"] == 1
        assert data["failed"] == 1


# ── /metrics endpoint ─────────────────────────────────────────────────────────

class TestMetricsEndpoint:
    def test_metrics_returns_200(self, client):
        resp = client.get("/api/v1/metrics")
        assert resp.status_code == 200

    def test_metrics_has_total_screens(self, client):
        resp = client.get("/api/v1/metrics")
        assert "total_screens" in resp.json()

    def test_metrics_has_urgent_referrals(self, client):
        resp = client.get("/api/v1/metrics")
        assert "urgent_referrals" in resp.json()

    def test_metrics_has_disease_distribution(self, client):
        resp = client.get("/api/v1/metrics")
        assert "disease_distribution" in resp.json()

    def test_metrics_has_uptime(self, client):
        resp = client.get("/api/v1/metrics")
        assert "uptime_seconds" in resp.json()

    def test_metrics_disease_distribution_has_all_labels(self, client):
        resp = client.get("/api/v1/metrics")
        dist = resp.json()["disease_distribution"]
        for label in DiseaseLabel:
            assert label.value in dist

    def test_metrics_increments_after_analysis(self, client):
        resp_before = client.get("/api/v1/metrics")
        before = resp_before.json()["total_screens"]
        img_bytes = image_to_bytes(make_normal_fundus())
        client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
        )
        resp_after = client.get("/api/v1/metrics")
        after = resp_after.json()["total_screens"]
        assert after == before + 1

    def test_metrics_screens_per_hour_non_negative(self, client):
        resp = client.get("/api/v1/metrics")
        assert resp.json()["screens_per_hour"] >= 0.0


# ── Rate limiting headers ─────────────────────────────────────────────────────

class TestRateLimitHeaders:
    def test_analyze_has_rate_limit_header(self, client):
        img_bytes = image_to_bytes(make_normal_fundus())
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
        )
        assert "x-ratelimit-limit" in resp.headers or "X-RateLimit-Limit" in resp.headers

    def test_rate_limit_value_is_numeric(self, client):
        img_bytes = image_to_bytes(make_normal_fundus())
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
        )
        limit = resp.headers.get("x-ratelimit-limit") or resp.headers.get("X-RateLimit-Limit")
        assert limit is not None
        assert int(limit) > 0

    def test_rate_limit_window_header_present(self, client):
        img_bytes = image_to_bytes(make_normal_fundus())
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
        )
        window = resp.headers.get("x-ratelimit-window") or resp.headers.get("X-RateLimit-Window")
        assert window is not None


# ── Edge cases: corrupted / extreme images ────────────────────────────────────

class TestEdgeCases:
    def test_corrupted_bytes_returns_422(self, client):
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("corrupt.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")},
        )
        assert resp.status_code == 422

    def test_empty_bytes_returns_422(self, client):
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("empty.jpg", b"", "image/jpeg")},
        )
        assert resp.status_code == 422

    def test_tiny_1x1_image(self, preprocessor):
        """1x1 image should be handled without crash."""
        tiny = Image.fromarray(np.array([[[128, 64, 32]]], dtype=np.uint8), mode="RGB")
        result = preprocessor.process(tiny)
        assert isinstance(result.processed_image, Image.Image)
        assert "low_resolution" in result.quality_flags

    def test_very_large_image(self, preprocessor):
        """2048x2048 image should be downsized correctly."""
        large = Image.fromarray(
            np.random.randint(50, 200, (2048, 2048, 3), dtype=np.uint8), mode="RGB"
        )
        result = preprocessor.process(large)
        assert result.processed_image.size == (224, 224)

    def test_grayscale_input_processed(self, preprocessor):
        gray = Image.fromarray(np.full((256, 256), 100, dtype=np.uint8), mode="L")
        result = preprocessor.process(gray)
        assert result.processed_image.mode == "RGB"

    def test_rgba_input_processed(self, preprocessor):
        rgba = Image.fromarray(np.full((256, 256, 4), 128, dtype=np.uint8), mode="RGBA")
        result = preprocessor.process(rgba)
        assert result.processed_image.mode == "RGB"

    def test_all_black_image(self, preprocessor):
        black = Image.fromarray(np.zeros((256, 256, 3), dtype=np.uint8), mode="RGB")
        result = preprocessor.process(black)
        assert "underexposed" in result.quality_flags
        assert result.quality_score < 0.8

    def test_all_white_image(self, preprocessor):
        white = Image.fromarray(np.full((256, 256, 3), 255, dtype=np.uint8), mode="RGB")
        result = preprocessor.process(white)
        assert "overexposed" in result.quality_flags

    def test_non_square_image(self, preprocessor):
        """Wide rectangular image should resize to 224x224 correctly."""
        wide = Image.fromarray(np.random.randint(50, 200, (128, 512, 3), dtype=np.uint8), mode="RGB")
        result = preprocessor.process(wide)
        assert result.processed_image.size == (224, 224)

    def test_classifier_handles_1x1_image(self):
        c = RetinalClassifier(demo_mode=True, generate_attention_maps=False)
        tiny = Image.fromarray(np.array([[[128, 64, 32]]], dtype=np.uint8), mode="RGB")
        result = c.classify(tiny)
        assert isinstance(result, ClassificationResult)

    def test_png_image_accepted(self, client):
        img_bytes = image_to_bytes(make_amd_fundus(), fmt="PNG")
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.png", img_bytes, "image/png")},
        )
        assert resp.status_code == 200


# ── Laterality via API ────────────────────────────────────────────────────────

class TestLateralityAPI:
    def test_analyze_accepts_od_laterality(self, client):
        img_bytes = image_to_bytes(make_normal_fundus())
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
            data={"laterality": "OD"},
        )
        assert resp.status_code == 200
        assert resp.json()["report"]["laterality"] == "OD"

    def test_analyze_accepts_os_laterality(self, client):
        img_bytes = image_to_bytes(make_normal_fundus())
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
            data={"laterality": "OS"},
        )
        assert resp.status_code == 200
        assert resp.json()["report"]["laterality"] == "OS"

    def test_analyze_default_laterality_unspecified(self, client):
        img_bytes = image_to_bytes(make_normal_fundus())
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
        )
        assert resp.status_code == 200
        assert resp.json()["report"]["laterality"] == "unspecified"


# ── Performance / benchmark tests ────────────────────────────────────────────

class TestPerformance:
    def test_single_image_analysis_under_5_seconds(self, client):
        """Full pipeline including HTTP overhead should complete in <5s."""
        img_bytes = image_to_bytes(make_normal_fundus())
        start = time.time()
        resp = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
        )
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 5.0, f"Analysis took {elapsed:.2f}s (limit: 5s)"

    def test_preprocessing_under_1_second(self):
        """Preprocessing pipeline for a standard image should be <1s."""
        p = RetinalPreprocessor()
        img = make_normal_fundus()
        start = time.time()
        p.process(img)
        elapsed = time.time() - start
        assert elapsed < 1.0, f"Preprocessing took {elapsed:.2f}s (limit: 1s)"

    def test_classifier_under_500ms(self):
        """Heuristic classification should complete in <500ms."""
        c = RetinalClassifier(demo_mode=True, generate_attention_maps=True)
        img = make_glaucoma_fundus()
        start = time.time()
        c.classify(img)
        elapsed = time.time() - start
        assert elapsed < 0.5, f"Classification took {elapsed:.2f}s (limit: 0.5s)"

    def test_batch_5_images_under_15_seconds(self, client):
        """Batch of 5 images should complete in <15s."""
        files = [
            ("files", (f"img{i}.jpg", image_to_bytes(make_normal_fundus()), "image/jpeg"))
            for i in range(5)
        ]
        start = time.time()
        resp = client.post("/api/v1/analyze/batch", files=files)
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 15.0, f"Batch took {elapsed:.2f}s (limit: 15s)"
