"""Tests for clinical report generation."""

from __future__ import annotations

import pytest

from app.models.classifier import ClassificationResult, DiseaseLabel
from app.models.risk_scoring import RiskScorer
from app.models.severity import SeverityGrader
from app.reporting.clinical_report import (
    CLINICAL_IMPRESSION_TEMPLATES,
    DISCLAIMER,
    FINDINGS_TEMPLATES,
    ClinicalReport,
    ClinicalReportGenerator,
)


def make_classification(label: DiseaseLabel, confidence: float = 0.80) -> ClassificationResult:
    probs = {lbl.value: 0.0 for lbl in DiseaseLabel}
    probs[label.value] = confidence
    return ClassificationResult(
        predicted_label=label,
        confidence=confidence,
        probabilities=probs,
    )


@pytest.fixture
def generator() -> ClinicalReportGenerator:
    return ClinicalReportGenerator()


@pytest.fixture
def grader() -> SeverityGrader:
    return SeverityGrader()


@pytest.fixture
def scorer() -> RiskScorer:
    return RiskScorer()


def make_full_report(
    generator, grader, scorer, label: DiseaseLabel, confidence: float = 0.80
) -> ClinicalReport:
    cls = make_classification(label, confidence)
    sev = grader.grade(cls)
    risk = scorer.compute(cls, sev)
    return generator.generate(
        study_id="TEST-STUDY-001",
        classification=cls,
        severity=sev,
        risk=risk,
    )


# ── Report structure ──────────────────────────────────────────────────────────

class TestReportStructure:
    def test_report_has_report_id(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.NORMAL)
        assert report.report_id
        assert len(report.report_id) > 0

    def test_report_id_is_unique(self, generator, grader, scorer):
        r1 = make_full_report(generator, grader, scorer, DiseaseLabel.NORMAL)
        r2 = make_full_report(generator, grader, scorer, DiseaseLabel.NORMAL)
        assert r1.report_id != r2.report_id

    def test_report_has_generated_at(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.NORMAL)
        assert report.generated_at
        assert "T" in report.generated_at  # ISO format

    def test_report_study_id_preserved(self, generator, grader, scorer):
        cls = make_classification(DiseaseLabel.NORMAL)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        report = generator.generate("MY-STUDY-XYZ", cls, sev, risk)
        assert report.study_id == "MY-STUDY-XYZ"

    def test_report_has_disclaimer(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.NORMAL)
        assert len(report.disclaimer) > 0
        assert "AI" in report.disclaimer or "automated" in report.disclaimer.lower()

    def test_disclaimer_text_matches_constant(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.NORMAL)
        assert report.disclaimer == DISCLAIMER

    def test_report_version(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.NORMAL)
        assert report.report_version == "1.0"

    def test_report_has_findings_summary(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.DIABETIC_RETINOPATHY)
        assert len(report.findings_summary) > 20

    def test_report_has_clinical_impression(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.GLAUCOMA)
        assert len(report.clinical_impression) > 20

    def test_report_has_recommendations(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.DIABETIC_RETINOPATHY)
        assert len(report.recommendations) > 0


# ── Disease-specific findings ─────────────────────────────────────────────────

class TestDiseaseFindings:
    def test_dr_findings_mention_microaneurysms(self, generator, grader, scorer):
        report = make_full_report(
            generator, grader, scorer, DiseaseLabel.DIABETIC_RETINOPATHY, 0.40
        )
        assert "microaneurysm" in report.findings_summary.lower()

    def test_glaucoma_findings_mention_optic_disc(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.GLAUCOMA)
        assert "optic" in report.findings_summary.lower()

    def test_amd_findings_mention_drusen(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.AMD, 0.40)
        assert "drusen" in report.findings_summary.lower()

    def test_cataracts_findings_mention_lens(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.CATARACTS)
        assert "lens" in report.findings_summary.lower() or "opaci" in report.findings_summary.lower()

    def test_normal_findings_mention_normal(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.NORMAL)
        assert "normal" in report.findings_summary.lower()

    def test_dr_proliferative_mentions_neovascularization(self, generator, grader, scorer):
        report = make_full_report(
            generator, grader, scorer, DiseaseLabel.DIABETIC_RETINOPATHY, 0.92
        )
        assert (
            "neovascular" in report.findings_summary.lower()
            or "proliferative" in report.findings_summary.lower()
        )


# ── to_dict ───────────────────────────────────────────────────────────────────

class TestReportToDict:
    def test_to_dict_keys(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.NORMAL)
        d = report.to_dict()
        expected_keys = {
            "report_id", "study_id", "generated_at", "report_version",
            "classification", "severity", "risk", "findings_summary",
            "clinical_impression", "recommendations", "image_quality",
            "disclaimer",
        }
        assert expected_keys.issubset(set(d.keys()))

    def test_to_dict_classification_dict(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.DIABETIC_RETINOPATHY)
        d = report.to_dict()
        assert isinstance(d["classification"], dict)
        assert "predicted_label" in d["classification"]

    def test_to_dict_risk_dict(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.GLAUCOMA)
        d = report.to_dict()
        assert isinstance(d["risk"], dict)
        assert "risk_level" in d["risk"]


# ── to_text ───────────────────────────────────────────────────────────────────

class TestReportToText:
    def test_to_text_non_empty(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.NORMAL)
        text = report.to_text()
        assert len(text) > 200

    def test_to_text_contains_report_id(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.NORMAL)
        assert report.report_id[:8] in report.to_text()

    def test_to_text_contains_study_id(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.NORMAL)
        assert "TEST-STUDY-001" in report.to_text()

    def test_to_text_contains_sections(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.DIABETIC_RETINOPATHY)
        text = report.to_text()
        assert "CLASSIFICATION" in text
        assert "SEVERITY" in text
        assert "FINDINGS" in text
        assert "DISCLAIMER" in text
        assert "RECOMMENDATIONS" in text

    def test_to_text_contains_icd10(self, generator, grader, scorer):
        report = make_full_report(generator, grader, scorer, DiseaseLabel.DIABETIC_RETINOPATHY)
        text = report.to_text()
        assert "E11.319" in text

    def test_to_text_contains_etdrs_for_dr(self, generator, grader, scorer):
        report = make_full_report(
            generator, grader, scorer, DiseaseLabel.DIABETIC_RETINOPATHY, 0.90
        )
        text = report.to_text()
        assert "ETDRS" in text or "71" in text


# ── With image quality ────────────────────────────────────────────────────────

class TestReportWithImageQuality:
    def test_report_with_quality_metadata(self, generator, grader, scorer):
        cls = make_classification(DiseaseLabel.NORMAL)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        quality = {
            "quality_score": 0.85,
            "quality_flags": [],
            "clahe_applied": True,
        }
        report = generator.generate("STUDY-Q", cls, sev, risk, image_quality=quality)
        assert report.image_quality is not None
        assert report.image_quality["quality_score"] == 0.85

    def test_to_text_includes_quality_section(self, generator, grader, scorer):
        cls = make_classification(DiseaseLabel.NORMAL)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        quality = {"quality_score": 0.75, "quality_flags": ["low_contrast"]}
        report = generator.generate("STUDY-Q2", cls, sev, risk, image_quality=quality)
        text = report.to_text()
        assert "IMAGE QUALITY" in text


# ── Template completeness ─────────────────────────────────────────────────────

class TestTemplateCompleteness:
    def test_all_diseases_have_findings_templates(self):
        for disease in DiseaseLabel:
            assert disease in FINDINGS_TEMPLATES
            assert len(FINDINGS_TEMPLATES[disease]) > 0

    def test_all_diseases_have_impression_templates(self):
        for disease in DiseaseLabel:
            assert disease in CLINICAL_IMPRESSION_TEMPLATES
            assert len(CLINICAL_IMPRESSION_TEMPLATES[disease]) > 20

    def test_batch_generate(self, generator, grader, scorer):
        studies = []
        for label in DiseaseLabel:
            cls = make_classification(label, 0.80)
            sev = grader.grade(cls)
            risk = scorer.compute(cls, sev)
            studies.append({
                "study_id": f"BATCH-{label.value}",
                "classification": cls,
                "severity": sev,
                "risk": risk,
            })
        reports = generator.generate_batch(studies)
        assert len(reports) == len(DiseaseLabel)

    def test_no_pii_in_report_text(self, generator, grader, scorer):
        """Report text must not contain common PII patterns."""
        report = make_full_report(generator, grader, scorer, DiseaseLabel.NORMAL)
        text = report.to_text()
        # No field called patient_name, DOB, SSN etc.
        assert "patient_name" not in text.lower()
        assert "date_of_birth" not in text.lower()
        assert "social_security" not in text.lower()
