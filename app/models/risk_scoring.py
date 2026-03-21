"""Patient risk score computation for retinal disease findings.

Computes a composite risk score integrating disease classification confidence,
severity grading, and optional clinical metadata (age, diabetes duration, HbA1c).
HIPAA-aware: no PII stored; all patient identifiers are de-identified.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.models.classifier import ClassificationResult, DiseaseLabel
from app.models.severity import SeverityLevel, SeverityResult


class RiskLevel(str, Enum):
    """Overall patient risk stratification."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


# Disease base risk weights (0–1 scale)
DISEASE_BASE_RISK: dict[DiseaseLabel, float] = {
    DiseaseLabel.NORMAL: 0.05,
    DiseaseLabel.CATARACTS: 0.30,
    DiseaseLabel.AMD: 0.55,
    DiseaseLabel.GLAUCOMA: 0.60,
    DiseaseLabel.DIABETIC_RETINOPATHY: 0.65,
}

# Severity multipliers
SEVERITY_MULTIPLIERS: dict[SeverityLevel, float] = {
    SeverityLevel.NONE: 1.0,
    SeverityLevel.MILD: 1.2,
    SeverityLevel.MODERATE: 1.6,
    SeverityLevel.SEVERE: 2.2,
    SeverityLevel.PROLIFERATIVE: 3.0,
    SeverityLevel.ADVANCED: 2.5,
    SeverityLevel.VISION_THREATENING: 4.0,
}


@dataclass
class ClinicalMetadata:
    """De-identified clinical metadata for enhanced risk scoring.

    No direct patient identifiers (name, DOB, MRN) stored here.
    Patient reference is an opaque study_id managed externally.
    """

    age: int | None = None                  # years
    diabetes_duration_years: int | None = None
    hba1c_percent: float | None = None      # e.g., 8.5
    systolic_bp: int | None = None          # mmHg
    has_hypertension: bool = False
    is_smoker: bool = False
    family_history_eye_disease: bool = False
    previous_laser_treatment: bool = False

    def validate(self) -> list[str]:
        """Return list of validation warnings."""
        warnings = []
        if self.age is not None and not (0 < self.age < 130):
            warnings.append(f"Implausible age value: {self.age}")
        if self.hba1c_percent is not None and not (3.0 < self.hba1c_percent < 20.0):
            warnings.append(f"Implausible HbA1c value: {self.hba1c_percent}")
        if self.systolic_bp is not None and not (60 < self.systolic_bp < 300):
            warnings.append(f"Implausible systolic BP: {self.systolic_bp}")
        return warnings


@dataclass
class RiskScore:
    """Composite patient risk score."""

    raw_score: float          # 0.0–1.0 continuous
    risk_level: RiskLevel
    contributing_factors: list[str]
    recommendations: list[str]
    screening_interval_months: int
    score_components: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "raw_score": round(self.raw_score, 4),
            "risk_level": self.risk_level.value,
            "contributing_factors": self.contributing_factors,
            "recommendations": self.recommendations,
            "screening_interval_months": self.screening_interval_months,
            "score_components": {k: round(v, 4) for k, v in self.score_components.items()},
        }


class RiskScorer:
    """Computes composite patient risk scores from retinal analysis results."""

    # Risk level thresholds (raw_score)
    RISK_THRESHOLDS = {
        RiskLevel.LOW: 0.0,
        RiskLevel.MODERATE: 0.25,
        RiskLevel.HIGH: 0.55,
        RiskLevel.CRITICAL: 0.80,
    }

    # Screening intervals by risk level (months)
    SCREENING_INTERVALS: dict[RiskLevel, int] = {
        RiskLevel.LOW: 24,
        RiskLevel.MODERATE: 12,
        RiskLevel.HIGH: 6,
        RiskLevel.CRITICAL: 1,
    }

    def compute(
        self,
        classification: ClassificationResult,
        severity: SeverityResult,
        metadata: ClinicalMetadata | None = None,
    ) -> RiskScore:
        """Compute composite risk score.

        Args:
            classification: Disease classification result.
            severity: Severity grading result.
            metadata: Optional de-identified clinical metadata.

        Returns:
            RiskScore with composite score and recommendations.
        """
        components: dict[str, float] = {}
        factors: list[str] = []

        # 1. Base disease risk
        base = DISEASE_BASE_RISK[classification.predicted_label]
        components["disease_base"] = base

        # 2. Severity multiplier (capped at 1.0)
        multiplier = SEVERITY_MULTIPLIERS.get(severity.severity, 1.0)
        severity_component = min(base * multiplier, 1.0)
        components["severity_adjusted"] = severity_component

        # 3. Confidence penalty — low confidence means less certain finding
        conf_weight = classification.confidence
        weighted = severity_component * (0.5 + 0.5 * conf_weight)
        components["confidence_weighted"] = weighted

        # 4. Clinical metadata modifiers
        meta_boost = 0.0
        if metadata:
            meta_boost, meta_factors = self._compute_metadata_boost(
                classification.predicted_label, metadata
            )
            factors.extend(meta_factors)
        components["metadata_boost"] = meta_boost

        raw_score = min(weighted + meta_boost, 1.0)
        components["raw_score"] = raw_score

        if classification.predicted_label != DiseaseLabel.NORMAL:
            disease_factor = (
                f"{classification.predicted_label.value.replace('_', ' ').title()} "
                f"({severity.severity.value} severity, "
                f"{classification.confidence:.0%} confidence)"
            )
            factors.insert(0, disease_factor)

        risk_level = self._score_to_risk_level(raw_score)
        recommendations = self._generate_recommendations(
            classification.predicted_label, severity, risk_level, metadata
        )
        interval = self.SCREENING_INTERVALS[risk_level]

        return RiskScore(
            raw_score=raw_score,
            risk_level=risk_level,
            contributing_factors=factors,
            recommendations=recommendations,
            screening_interval_months=interval,
            score_components=components,
        )

    def _compute_metadata_boost(
        self, disease: DiseaseLabel, meta: ClinicalMetadata
    ) -> tuple[float, list[str]]:
        """Compute risk boost from clinical metadata."""
        boost = 0.0
        factors = []

        if meta.age is not None and meta.age > 65:
            boost += 0.05
            factors.append(f"Age > 65 years ({meta.age})")

        if meta.hba1c_percent is not None and meta.hba1c_percent > 8.0:
            boost += 0.10
            factors.append(f"Elevated HbA1c: {meta.hba1c_percent:.1f}%")
        elif meta.hba1c_percent is not None and meta.hba1c_percent > 7.0:
            boost += 0.05
            factors.append(f"Suboptimal glycemic control HbA1c: {meta.hba1c_percent:.1f}%")

        if meta.diabetes_duration_years is not None and meta.diabetes_duration_years > 10:
            boost += 0.08
            factors.append(f"Long diabetes duration: {meta.diabetes_duration_years} years")

        if meta.has_hypertension:
            boost += 0.05
            factors.append("Hypertension present")

        if meta.systolic_bp is not None and meta.systolic_bp > 160:
            boost += 0.05
            factors.append(f"Elevated systolic BP: {meta.systolic_bp} mmHg")

        if meta.is_smoker:
            boost += 0.04
            factors.append("Active smoker")

        if meta.family_history_eye_disease:
            boost += 0.03
            factors.append("Family history of eye disease")

        if meta.previous_laser_treatment:
            boost += 0.06
            factors.append("Previous retinal laser treatment")

        return boost, factors

    def _score_to_risk_level(self, score: float) -> RiskLevel:
        """Map continuous score to risk level."""
        if score >= self.RISK_THRESHOLDS[RiskLevel.CRITICAL]:
            return RiskLevel.CRITICAL
        elif score >= self.RISK_THRESHOLDS[RiskLevel.HIGH]:
            return RiskLevel.HIGH
        elif score >= self.RISK_THRESHOLDS[RiskLevel.MODERATE]:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.LOW

    def _generate_recommendations(
        self,
        disease: DiseaseLabel,
        severity: SeverityResult,
        risk: RiskLevel,
        metadata: ClinicalMetadata | None,
    ) -> list[str]:
        """Generate clinical recommendations."""
        recs: list[str] = []

        if disease == DiseaseLabel.NORMAL:
            recs.append("Continue routine diabetic eye screening program.")
            recs.append("Maintain optimal glycemic and blood pressure control.")
            return recs

        recs.append(f"Follow-up urgency: {severity.follow_up_urgency}.")

        if disease == DiseaseLabel.DIABETIC_RETINOPATHY:
            recs.append("Optimize glycemic control (target HbA1c < 7.0%).")
            recs.append("Blood pressure management (target < 130/80 mmHg).")
            if severity.severity in (SeverityLevel.SEVERE, SeverityLevel.PROLIFERATIVE):
                recs.append("Urgent referral for anti-VEGF therapy or laser photocoagulation.")
            if metadata and metadata.hba1c_percent and metadata.hba1c_percent > 8.0:
                recs.append("Urgent endocrinology referral for glycemic optimization.")

        elif disease == DiseaseLabel.GLAUCOMA:
            recs.append("Intraocular pressure measurement and visual field testing.")
            recs.append("Consider initiating IOP-lowering therapy.")
            recs.append("Regular RNFL OCT monitoring.")

        elif disease == DiseaseLabel.AMD:
            recs.append("AREDS2 vitamin supplementation recommended.")
            recs.append("Amsler grid self-monitoring for metamorphopsia.")
            if severity.severity in (SeverityLevel.SEVERE, SeverityLevel.ADVANCED):
                recs.append("Urgent intravitreal anti-VEGF therapy evaluation.")

        elif disease == DiseaseLabel.CATARACTS:
            recs.append("Visual acuity and contrast sensitivity assessment.")
            if severity.severity == SeverityLevel.SEVERE:
                recs.append("Surgical evaluation for phacoemulsification.")

        if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            recs.append("Multidisciplinary team review recommended.")

        return recs
