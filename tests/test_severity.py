"""Tests for the disease severity grading module."""

from __future__ import annotations

import pytest

from app.models.classifier import ClassificationResult, DiseaseLabel
from app.models.severity import (
    SEVERITY_CLINICAL_DESCRIPTIONS,
    SeverityGrader,
    SeverityLevel,
)


def make_result(label: DiseaseLabel, confidence: float) -> ClassificationResult:
    probs = {lbl.value: 0.0 for lbl in DiseaseLabel}
    probs[label.value] = confidence
    return ClassificationResult(
        predicted_label=label,
        confidence=confidence,
        probabilities=probs,
    )


@pytest.fixture
def grader() -> SeverityGrader:
    return SeverityGrader()


# ── SeverityLevel enum ────────────────────────────────────────────────────────

class TestSeverityLevel:
    def test_all_levels_present(self):
        levels = {lv.value for lv in SeverityLevel}
        assert "none" in levels
        assert "mild" in levels
        assert "moderate" in levels
        assert "severe" in levels
        assert "proliferative" in levels
        assert "advanced" in levels

    def test_vision_threatening_level(self):
        assert SeverityLevel.VISION_THREATENING.value == "vision_threatening"


# ── Normal grading ────────────────────────────────────────────────────────────

class TestNormalGrading:
    def test_normal_gives_none_severity(self, grader):
        result = grader.grade(make_result(DiseaseLabel.NORMAL, 0.95))
        assert result.severity == SeverityLevel.NONE

    def test_normal_severity_score_is_zero(self, grader):
        result = grader.grade(make_result(DiseaseLabel.NORMAL, 0.95))
        assert result.severity_score == 0.0

    def test_normal_urgency_is_routine(self, grader):
        result = grader.grade(make_result(DiseaseLabel.NORMAL, 0.95))
        assert result.follow_up_urgency == "routine"

    def test_normal_no_etdrs(self, grader):
        result = grader.grade(make_result(DiseaseLabel.NORMAL, 0.95))
        assert result.etdrs_level is None


# ── Diabetic Retinopathy grading ──────────────────────────────────────────────

class TestDRGrading:
    def test_low_confidence_dr_is_mild(self, grader):
        result = grader.grade(make_result(DiseaseLabel.DIABETIC_RETINOPATHY, 0.30))
        assert result.severity == SeverityLevel.MILD

    def test_moderate_confidence_dr_is_moderate(self, grader):
        result = grader.grade(make_result(DiseaseLabel.DIABETIC_RETINOPATHY, 0.55))
        assert result.severity == SeverityLevel.MODERATE

    def test_high_confidence_dr_is_severe(self, grader):
        result = grader.grade(make_result(DiseaseLabel.DIABETIC_RETINOPATHY, 0.70))
        assert result.severity == SeverityLevel.SEVERE

    def test_very_high_confidence_dr_is_proliferative(self, grader):
        result = grader.grade(make_result(DiseaseLabel.DIABETIC_RETINOPATHY, 0.90))
        assert result.severity == SeverityLevel.PROLIFERATIVE

    def test_dr_has_etdrs_level(self, grader):
        result = grader.grade(make_result(DiseaseLabel.DIABETIC_RETINOPATHY, 0.90))
        assert result.etdrs_level is not None
        assert result.etdrs_level > 0

    def test_dr_mild_etdrs_is_20(self, grader):
        result = grader.grade(make_result(DiseaseLabel.DIABETIC_RETINOPATHY, 0.30))
        assert result.etdrs_level == 20

    def test_dr_proliferative_etdrs_is_71(self, grader):
        result = grader.grade(make_result(DiseaseLabel.DIABETIC_RETINOPATHY, 0.90))
        assert result.etdrs_level == 71

    def test_dr_neovascularization_feature_causes_proliferative(self, grader):
        features = {"neovascularization_detected": True}
        result = grader.grade(
            make_result(DiseaseLabel.DIABETIC_RETINOPATHY, 0.40),
            image_features=features,
        )
        assert result.severity == SeverityLevel.PROLIFERATIVE

    def test_dr_extensive_hemorrhage_feature_causes_severe(self, grader):
        features = {"extensive_hemorrhage": True}
        result = grader.grade(
            make_result(DiseaseLabel.DIABETIC_RETINOPATHY, 0.40),
            image_features=features,
        )
        assert result.severity == SeverityLevel.SEVERE

    def test_proliferative_urgency_is_emergency(self, grader):
        result = grader.grade(make_result(DiseaseLabel.DIABETIC_RETINOPATHY, 0.90))
        assert "emergency" in result.follow_up_urgency.lower() or "week" in result.follow_up_urgency.lower()


# ── Glaucoma grading ──────────────────────────────────────────────────────────

class TestGlaucomaGrading:
    def test_low_confidence_glaucoma_is_mild(self, grader):
        result = grader.grade(make_result(DiseaseLabel.GLAUCOMA, 0.40))
        assert result.severity == SeverityLevel.MILD

    def test_high_confidence_glaucoma_is_severe_or_advanced(self, grader):
        result = grader.grade(make_result(DiseaseLabel.GLAUCOMA, 0.92))
        assert result.severity in (SeverityLevel.SEVERE, SeverityLevel.ADVANCED)

    def test_glaucoma_high_cdr_is_advanced(self, grader):
        result = grader.grade(
            make_result(DiseaseLabel.GLAUCOMA, 0.75),
            image_features={"cup_disc_ratio": 0.90},
        )
        assert result.severity == SeverityLevel.ADVANCED

    def test_glaucoma_no_etdrs(self, grader):
        result = grader.grade(make_result(DiseaseLabel.GLAUCOMA, 0.75))
        assert result.etdrs_level is None


# ── AMD grading ───────────────────────────────────────────────────────────────

class TestAMDGrading:
    def test_low_confidence_amd_is_mild(self, grader):
        result = grader.grade(make_result(DiseaseLabel.AMD, 0.40))
        assert result.severity == SeverityLevel.MILD

    def test_high_confidence_amd_is_severe(self, grader):
        result = grader.grade(make_result(DiseaseLabel.AMD, 0.90))
        assert result.severity == SeverityLevel.SEVERE

    def test_amd_with_geographic_atrophy_feature(self, grader):
        result = grader.grade(
            make_result(DiseaseLabel.AMD, 0.60),
            image_features={"geographic_atrophy": True},
        )
        assert result.severity == SeverityLevel.SEVERE

    def test_amd_with_subretinal_fluid_feature(self, grader):
        result = grader.grade(
            make_result(DiseaseLabel.AMD, 0.60),
            image_features={"subretinal_fluid": True},
        )
        assert result.severity == SeverityLevel.ADVANCED


# ── Cataracts grading ─────────────────────────────────────────────────────────

class TestCataractsGrading:
    def test_low_confidence_cataracts_is_mild(self, grader):
        result = grader.grade(make_result(DiseaseLabel.CATARACTS, 0.40))
        assert result.severity == SeverityLevel.MILD

    def test_high_confidence_cataracts_is_severe(self, grader):
        result = grader.grade(make_result(DiseaseLabel.CATARACTS, 0.90))
        assert result.severity == SeverityLevel.SEVERE

    def test_cataracts_with_high_opacity(self, grader):
        result = grader.grade(
            make_result(DiseaseLabel.CATARACTS, 0.60),
            image_features={"lens_opacity_score": 0.80},
        )
        assert result.severity == SeverityLevel.SEVERE


# ── SeverityResult structure ──────────────────────────────────────────────────

class TestSeverityResult:
    def test_to_dict_keys(self, grader):
        result = grader.grade(make_result(DiseaseLabel.DIABETIC_RETINOPATHY, 0.75))
        d = result.to_dict()
        assert "disease" in d
        assert "severity" in d
        assert "severity_score" in d
        assert "clinical_description" in d
        assert "follow_up_urgency" in d
        assert "etdrs_level" in d

    def test_severity_score_in_range(self, grader):
        for label in DiseaseLabel:
            conf = 0.8 if label != DiseaseLabel.NORMAL else 0.9
            result = grader.grade(make_result(label, conf))
            assert 0.0 <= result.severity_score <= 1.0, (
                f"severity_score out of range for {label.value}"
            )

    def test_clinical_description_non_empty(self, grader):
        for label in DiseaseLabel:
            result = grader.grade(make_result(label, 0.8))
            assert len(result.clinical_description) > 0

    def test_follow_up_urgency_non_empty(self, grader):
        for label in DiseaseLabel:
            result = grader.grade(make_result(label, 0.8))
            assert len(result.follow_up_urgency) > 0

    def test_proliferative_has_highest_score(self, grader):
        prolif = grader.grade(make_result(DiseaseLabel.DIABETIC_RETINOPATHY, 0.90))
        mild = grader.grade(make_result(DiseaseLabel.DIABETIC_RETINOPATHY, 0.30))
        assert prolif.severity_score > mild.severity_score

    def test_clinical_descriptions_complete(self):
        """All diseases have at least one severity description."""
        for disease in DiseaseLabel:
            assert disease in SEVERITY_CLINICAL_DESCRIPTIONS
            assert len(SEVERITY_CLINICAL_DESCRIPTIONS[disease]) > 0
