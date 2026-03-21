"""Disease severity grading for retinal conditions.

Implements ETDRS-like severity scale for Diabetic Retinopathy and
severity grading for Glaucoma, AMD, and Cataracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.models.classifier import ClassificationResult, DiseaseLabel


class SeverityLevel(StrEnum):
    """Universal severity levels for retinal disease grading."""

    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    PROLIFERATIVE = "proliferative"  # DR-specific (PDR)
    ADVANCED = "advanced"            # Glaucoma/AMD advanced stage
    VISION_THREATENING = "vision_threatening"


# ETDRS-equivalent DR severity grading
DR_SEVERITY_THRESHOLDS = {
    # confidence -> severity mapping for DR
    0.0: SeverityLevel.MILD,
    0.4: SeverityLevel.MODERATE,
    0.65: SeverityLevel.SEVERE,
    0.85: SeverityLevel.PROLIFERATIVE,
}

# Clinical descriptions per disease/severity
SEVERITY_CLINICAL_DESCRIPTIONS: dict[DiseaseLabel, dict[SeverityLevel, str]] = {
    DiseaseLabel.DIABETIC_RETINOPATHY: {
        SeverityLevel.MILD: (
            "Mild non-proliferative diabetic retinopathy (NPDR). "
            "Microaneurysms only. Close monitoring recommended (annual review)."
        ),
        SeverityLevel.MODERATE: (
            "Moderate NPDR. Microaneurysms, dot-blot hemorrhages, and hard exudates "
            "present. Ophthalmology referral within 3 months."
        ),
        SeverityLevel.SEVERE: (
            "Severe NPDR. Extensive intraretinal hemorrhages in all four quadrants, "
            "venous beading, or intraretinal microvascular abnormalities (IRMA). "
            "Urgent ophthalmology referral within 4 weeks."
        ),
        SeverityLevel.PROLIFERATIVE: (
            "Proliferative diabetic retinopathy (PDR). Neovascularization of the disc "
            "(NVD) or elsewhere (NVE), vitreous/pre-retinal hemorrhage, or tractional "
            "retinal detachment. Emergency ophthalmology referral within 1 week. "
            "Anti-VEGF or panretinal photocoagulation indicated."
        ),
    },
    DiseaseLabel.GLAUCOMA: {
        SeverityLevel.MILD: (
            "Early glaucoma. Subtle optic nerve head changes with cup-to-disc ratio "
            "elevation. Visual field testing recommended."
        ),
        SeverityLevel.MODERATE: (
            "Moderate glaucoma. Significant optic nerve cupping (CDR > 0.7), "
            "retinal nerve fiber layer thinning. IOP management required."
        ),
        SeverityLevel.SEVERE: (
            "Severe glaucoma. Advanced optic nerve damage, significant visual field loss. "
            "Urgent specialist management required."
        ),
        SeverityLevel.ADVANCED: (
            "Advanced/end-stage glaucoma. Near-complete optic nerve cupping, "
            "tunnel vision. Surgical intervention may be indicated."
        ),
    },
    DiseaseLabel.AMD: {
        SeverityLevel.MILD: (
            "Early AMD. Small to medium drusen (< 125 μm) present. "
            "Annual monitoring, AREDS2 supplementation recommended."
        ),
        SeverityLevel.MODERATE: (
            "Intermediate AMD. Large drusen (≥ 125 μm) or geographic atrophy "
            "not involving the fovea. AREDS2 supplementation strongly recommended."
        ),
        SeverityLevel.SEVERE: (
            "Late AMD. Advanced geographic atrophy or neovascular (wet) AMD. "
            "Anti-VEGF therapy indicated for wet AMD. Urgent referral."
        ),
        SeverityLevel.ADVANCED: (
            "Advanced neovascular AMD with subretinal fibrosis or disciform scar. "
            "Significant central vision loss. Low-vision rehabilitation referral."
        ),
    },
    DiseaseLabel.CATARACTS: {
        SeverityLevel.MILD: (
            "Incipient cataract. Minimal lens opacity, minimal visual impact. "
            "Observation and refractive correction."
        ),
        SeverityLevel.MODERATE: (
            "Moderate cataract. Significant lens opacity causing visual impairment. "
            "Surgical evaluation recommended."
        ),
        SeverityLevel.SEVERE: (
            "Dense cataract. Significant visual impairment. "
            "Phacoemulsification with IOL implantation indicated."
        ),
    },
    DiseaseLabel.NORMAL: {
        SeverityLevel.NONE: (
            "No retinal pathology detected. Routine screening as per guidelines."
        ),
    },
}


@dataclass
class SeverityResult:
    """Result of disease severity grading."""

    disease: DiseaseLabel
    severity: SeverityLevel
    severity_score: float  # 0.0–1.0 continuous score
    clinical_description: str
    follow_up_urgency: str
    etdrs_level: int | None = None  # ETDRS level for DR (10/20/35/43/47/53/61/65/71/75/81/85)

    def to_dict(self) -> dict:
        return {
            "disease": self.disease.value,
            "severity": self.severity.value,
            "severity_score": round(self.severity_score, 4),
            "clinical_description": self.clinical_description,
            "follow_up_urgency": self.follow_up_urgency,
            "etdrs_level": self.etdrs_level,
        }


class SeverityGrader:
    """Grades disease severity from classification results and image features."""

    # Follow-up urgency labels
    URGENCY_MAP: dict[SeverityLevel, str] = {
        SeverityLevel.NONE: "routine",
        SeverityLevel.MILD: "routine (12 months)",
        SeverityLevel.MODERATE: "soon (3 months)",
        SeverityLevel.SEVERE: "urgent (4 weeks)",
        SeverityLevel.PROLIFERATIVE: "emergency (1 week)",
        SeverityLevel.ADVANCED: "urgent (4 weeks)",
        SeverityLevel.VISION_THREATENING: "emergency (same day)",
    }

    # ETDRS approximations for DR severity levels
    DR_ETDRS: dict[SeverityLevel, int] = {
        SeverityLevel.MILD: 20,        # ETDRS level 20: microaneurysms only
        SeverityLevel.MODERATE: 43,    # ETDRS level 43: moderate NPDR
        SeverityLevel.SEVERE: 53,      # ETDRS level 53: severe NPDR
        SeverityLevel.PROLIFERATIVE: 71,  # ETDRS level 71: PDR
    }

    def grade(
        self,
        classification: ClassificationResult,
        image_features: dict | None = None,
    ) -> SeverityResult:
        """Grade disease severity from classification result.

        Args:
            classification: Output from RetinalClassifier.classify()
            image_features: Optional dict of extracted image features for
                            enhanced severity grading.

        Returns:
            SeverityResult with severity level and clinical description.
        """
        disease = classification.predicted_label
        confidence = classification.confidence

        if disease == DiseaseLabel.NORMAL:
            return self._grade_normal()

        severity = self._compute_severity(disease, confidence, image_features)
        clinical_desc = self._get_clinical_description(disease, severity)
        urgency = self.URGENCY_MAP.get(severity, "routine")
        severity_score = self._severity_to_score(severity)
        etdrs = self.DR_ETDRS.get(severity) if disease == DiseaseLabel.DIABETIC_RETINOPATHY else None

        return SeverityResult(
            disease=disease,
            severity=severity,
            severity_score=severity_score,
            clinical_description=clinical_desc,
            follow_up_urgency=urgency,
            etdrs_level=etdrs,
        )

    def _grade_normal(self) -> SeverityResult:
        desc = SEVERITY_CLINICAL_DESCRIPTIONS[DiseaseLabel.NORMAL][SeverityLevel.NONE]
        return SeverityResult(
            disease=DiseaseLabel.NORMAL,
            severity=SeverityLevel.NONE,
            severity_score=0.0,
            clinical_description=desc,
            follow_up_urgency="routine",
            etdrs_level=None,
        )

    def _compute_severity(
        self,
        disease: DiseaseLabel,
        confidence: float,
        features: dict | None,
    ) -> SeverityLevel:
        """Map confidence and features to severity level."""

        if disease == DiseaseLabel.DIABETIC_RETINOPATHY:
            return self._grade_dr(confidence, features)
        elif disease == DiseaseLabel.GLAUCOMA:
            return self._grade_glaucoma(confidence, features)
        elif disease == DiseaseLabel.AMD:
            return self._grade_amd(confidence, features)
        elif disease == DiseaseLabel.CATARACTS:
            return self._grade_cataracts(confidence, features)
        return SeverityLevel.MILD

    def _grade_dr(self, confidence: float, features: dict | None) -> SeverityLevel:
        """ETDRS-like DR grading based on confidence and optional features."""
        # Check for neovascularization marker in features
        if features and features.get("neovascularization_detected"):
            return SeverityLevel.PROLIFERATIVE
        if features and features.get("extensive_hemorrhage"):
            return SeverityLevel.SEVERE

        if confidence >= 0.85:
            return SeverityLevel.PROLIFERATIVE
        elif confidence >= 0.65:
            return SeverityLevel.SEVERE
        elif confidence >= 0.40:
            return SeverityLevel.MODERATE
        else:
            return SeverityLevel.MILD

    def _grade_glaucoma(self, confidence: float, features: dict | None) -> SeverityLevel:
        """Glaucoma grading based on CDR and confidence."""
        cdr = features.get("cup_disc_ratio", 0.0) if features else 0.0

        if cdr > 0.85 or confidence >= 0.90:
            return SeverityLevel.ADVANCED
        elif cdr > 0.75 or confidence >= 0.70:
            return SeverityLevel.SEVERE
        elif cdr > 0.65 or confidence >= 0.50:
            return SeverityLevel.MODERATE
        else:
            return SeverityLevel.MILD

    def _grade_amd(self, confidence: float, features: dict | None) -> SeverityLevel:
        """AMD grading based on drusen characteristics."""
        if features and features.get("subretinal_fluid"):
            return SeverityLevel.ADVANCED
        if features and features.get("geographic_atrophy"):
            return SeverityLevel.SEVERE

        if confidence >= 0.85:
            return SeverityLevel.SEVERE
        elif confidence >= 0.60:
            return SeverityLevel.MODERATE
        else:
            return SeverityLevel.MILD

    def _grade_cataracts(self, confidence: float, features: dict | None) -> SeverityLevel:
        """Cataract grading based on lens opacity estimation."""
        opacity = features.get("lens_opacity_score", 0.0) if features else 0.0

        if opacity > 0.75 or confidence >= 0.85:
            return SeverityLevel.SEVERE
        elif opacity > 0.45 or confidence >= 0.55:
            return SeverityLevel.MODERATE
        else:
            return SeverityLevel.MILD

    def _get_clinical_description(
        self, disease: DiseaseLabel, severity: SeverityLevel
    ) -> str:
        """Retrieve clinical description for disease/severity combination."""
        disease_descs = SEVERITY_CLINICAL_DESCRIPTIONS.get(disease, {})
        if severity in disease_descs:
            return disease_descs[severity]
        # Fallback to closest available severity
        for lvl in [SeverityLevel.MILD, SeverityLevel.MODERATE, SeverityLevel.SEVERE]:
            if lvl in disease_descs:
                return disease_descs[lvl]
        return f"{disease.value} detected. Clinical review recommended."

    def _severity_to_score(self, severity: SeverityLevel) -> float:
        """Convert severity enum to 0–1 continuous score."""
        mapping = {
            SeverityLevel.NONE: 0.0,
            SeverityLevel.MILD: 0.25,
            SeverityLevel.MODERATE: 0.50,
            SeverityLevel.SEVERE: 0.75,
            SeverityLevel.PROLIFERATIVE: 0.90,
            SeverityLevel.ADVANCED: 0.85,
            SeverityLevel.VISION_THREATENING: 1.0,
        }
        return mapping.get(severity, 0.25)
