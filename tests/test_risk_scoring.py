"""Tests for patient risk scoring module."""

from __future__ import annotations

import pytest

from app.models.classifier import ClassificationResult, DiseaseLabel
from app.models.risk_scoring import (
    DISEASE_BASE_RISK,
    SEVERITY_MULTIPLIERS,
    ClinicalMetadata,
    RiskLevel,
    RiskScorer,
)
from app.models.severity import SeverityGrader, SeverityLevel


def make_classification(label: DiseaseLabel, confidence: float) -> ClassificationResult:
    probs = {lbl.value: 0.0 for lbl in DiseaseLabel}
    probs[label.value] = confidence
    return ClassificationResult(
        predicted_label=label,
        confidence=confidence,
        probabilities=probs,
    )


@pytest.fixture
def scorer() -> RiskScorer:
    return RiskScorer()


@pytest.fixture
def grader() -> SeverityGrader:
    return SeverityGrader()


# ── ClinicalMetadata ──────────────────────────────────────────────────────────

class TestClinicalMetadata:
    def test_default_values(self):
        meta = ClinicalMetadata()
        assert meta.age is None
        assert meta.hba1c_percent is None
        assert meta.has_hypertension is False
        assert meta.is_smoker is False

    def test_validate_no_errors_for_valid_data(self):
        meta = ClinicalMetadata(age=55, hba1c_percent=7.5, systolic_bp=130)
        warnings = meta.validate()
        assert len(warnings) == 0

    def test_validate_flags_implausible_age(self):
        meta = ClinicalMetadata(age=200)
        warnings = meta.validate()
        assert any("age" in w.lower() for w in warnings)

    def test_validate_flags_implausible_hba1c(self):
        meta = ClinicalMetadata(hba1c_percent=25.0)
        warnings = meta.validate()
        assert any("hba1c" in w.lower() for w in warnings)

    def test_validate_flags_implausible_bp(self):
        meta = ClinicalMetadata(systolic_bp=400)
        warnings = meta.validate()
        assert any("bp" in w.lower() or "systolic" in w.lower() for w in warnings)

    def test_no_pii_fields(self):
        """Verify no PII fields exist on ClinicalMetadata."""
        meta = ClinicalMetadata()
        fields = vars(meta).keys()
        pii_fields = {"name", "patient_name", "mrn", "ssn", "dob", "date_of_birth", "address"}
        for pii in pii_fields:
            assert pii not in fields


# ── Risk scoring basics ───────────────────────────────────────────────────────

class TestRiskScorerBasics:
    def test_normal_gives_low_risk(self, scorer, grader):
        cls = make_classification(DiseaseLabel.NORMAL, 0.95)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        assert risk.risk_level == RiskLevel.LOW

    def test_normal_risk_score_low(self, scorer, grader):
        cls = make_classification(DiseaseLabel.NORMAL, 0.95)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        assert risk.raw_score < 0.25

    def test_dr_high_confidence_gives_high_risk(self, scorer, grader):
        cls = make_classification(DiseaseLabel.DIABETIC_RETINOPATHY, 0.90)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        assert risk.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_risk_score_between_0_and_1(self, scorer, grader):
        for label in DiseaseLabel:
            conf = 0.8 if label != DiseaseLabel.NORMAL else 0.95
            cls = make_classification(label, conf)
            sev = grader.grade(cls)
            risk = scorer.compute(cls, sev)
            assert 0.0 <= risk.raw_score <= 1.0, f"Score out of range for {label.value}"

    def test_recommendations_non_empty(self, scorer, grader):
        for label in DiseaseLabel:
            cls = make_classification(label, 0.8)
            sev = grader.grade(cls)
            risk = scorer.compute(cls, sev)
            assert len(risk.recommendations) > 0

    def test_screening_interval_positive(self, scorer, grader):
        for label in DiseaseLabel:
            cls = make_classification(label, 0.8)
            sev = grader.grade(cls)
            risk = scorer.compute(cls, sev)
            assert risk.screening_interval_months > 0


# ── Risk levels ───────────────────────────────────────────────────────────────

class TestRiskLevels:
    def test_all_risk_levels_present(self):
        levels = {lv.value for lv in RiskLevel}
        assert "low" in levels
        assert "moderate" in levels
        assert "high" in levels
        assert "critical" in levels

    def test_critical_risk_short_screening_interval(self, scorer, grader):
        cls = make_classification(DiseaseLabel.DIABETIC_RETINOPATHY, 0.95)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        if risk.risk_level == RiskLevel.CRITICAL:
            assert risk.screening_interval_months <= 3

    def test_low_risk_long_screening_interval(self, scorer, grader):
        cls = make_classification(DiseaseLabel.NORMAL, 0.95)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        assert risk.screening_interval_months >= 12


# ── Metadata boosting ─────────────────────────────────────────────────────────

class TestMetadataBoosting:
    def test_high_hba1c_increases_risk(self, scorer, grader):
        cls = make_classification(DiseaseLabel.DIABETIC_RETINOPATHY, 0.60)
        sev = grader.grade(cls)

        risk_no_meta = scorer.compute(cls, sev)
        meta_high = ClinicalMetadata(hba1c_percent=9.5)
        risk_with_meta = scorer.compute(cls, sev, meta_high)

        assert risk_with_meta.raw_score >= risk_no_meta.raw_score

    def test_old_age_boosts_risk(self, scorer, grader):
        cls = make_classification(DiseaseLabel.AMD, 0.70)
        sev = grader.grade(cls)

        risk_young = scorer.compute(cls, sev, ClinicalMetadata(age=40))
        risk_old = scorer.compute(cls, sev, ClinicalMetadata(age=75))

        assert risk_old.raw_score >= risk_young.raw_score

    def test_hypertension_boosts_risk(self, scorer, grader):
        cls = make_classification(DiseaseLabel.DIABETIC_RETINOPATHY, 0.60)
        sev = grader.grade(cls)

        risk_no_htn = scorer.compute(cls, sev, ClinicalMetadata(has_hypertension=False))
        risk_htn = scorer.compute(cls, sev, ClinicalMetadata(has_hypertension=True))

        assert risk_htn.raw_score >= risk_no_htn.raw_score

    def test_long_diabetes_duration_boosts_risk(self, scorer, grader):
        cls = make_classification(DiseaseLabel.DIABETIC_RETINOPATHY, 0.60)
        sev = grader.grade(cls)

        risk_short = scorer.compute(cls, sev, ClinicalMetadata(diabetes_duration_years=2))
        risk_long = scorer.compute(cls, sev, ClinicalMetadata(diabetes_duration_years=20))

        assert risk_long.raw_score >= risk_short.raw_score

    def test_contributing_factors_listed_for_high_hba1c(self, scorer, grader):
        cls = make_classification(DiseaseLabel.DIABETIC_RETINOPATHY, 0.70)
        sev = grader.grade(cls)
        meta = ClinicalMetadata(hba1c_percent=9.0)
        risk = scorer.compute(cls, sev, meta)
        factors_text = " ".join(risk.contributing_factors).lower()
        assert "hba1c" in factors_text or "glycemic" in factors_text or "9.0" in factors_text

    def test_smoker_factor_listed(self, scorer, grader):
        cls = make_classification(DiseaseLabel.AMD, 0.70)
        sev = grader.grade(cls)
        meta = ClinicalMetadata(is_smoker=True)
        risk = scorer.compute(cls, sev, meta)
        factors_text = " ".join(risk.contributing_factors).lower()
        assert "smok" in factors_text


# ── RiskScore dataclass ───────────────────────────────────────────────────────

class TestRiskScoreDataclass:
    def test_to_dict_structure(self, scorer, grader):
        cls = make_classification(DiseaseLabel.GLAUCOMA, 0.75)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        d = risk.to_dict()
        assert "raw_score" in d
        assert "risk_level" in d
        assert "contributing_factors" in d
        assert "recommendations" in d
        assert "screening_interval_months" in d
        assert "score_components" in d

    def test_score_components_non_empty(self, scorer, grader):
        cls = make_classification(DiseaseLabel.DIABETIC_RETINOPATHY, 0.80)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        assert len(risk.score_components) > 0

    def test_disease_base_risks_defined(self):
        for label in DiseaseLabel:
            assert label in DISEASE_BASE_RISK
            assert 0.0 <= DISEASE_BASE_RISK[label] <= 1.0

    def test_severity_multipliers_defined(self):
        for level in SeverityLevel:
            assert level in SEVERITY_MULTIPLIERS
            assert SEVERITY_MULTIPLIERS[level] >= 1.0 or level == SeverityLevel.NONE

    def test_disease_in_contributing_factors_when_not_normal(self, scorer, grader):
        cls = make_classification(DiseaseLabel.GLAUCOMA, 0.80)
        sev = grader.grade(cls)
        risk = scorer.compute(cls, sev)
        assert len(risk.contributing_factors) > 0
