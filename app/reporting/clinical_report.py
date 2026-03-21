"""Clinical report generation for retinal disease findings.

Generates structured, clinician-readable reports using medical terminology
consistent with ophthalmology clinical practice guidelines.

HIPAA-aware: no PII stored in reports; study_id is an opaque reference.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.models.classifier import ClassificationResult, DiseaseLabel
from app.models.risk_scoring import RiskScore
from app.models.severity import SeverityLevel, SeverityResult

logger = logging.getLogger(__name__)


@dataclass
class ClinicalReport:
    """Structured clinical report for a retinal fundus examination."""

    report_id: str
    study_id: str          # Opaque patient reference — no PII
    generated_at: str
    classification: dict
    severity: dict
    risk: dict
    findings_summary: str
    clinical_impression: str
    recommendations: list[str]
    image_quality: dict | None
    disclaimer: str
    report_version: str = "1.0"

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "study_id": self.study_id,
            "generated_at": self.generated_at,
            "report_version": self.report_version,
            "classification": self.classification,
            "severity": self.severity,
            "risk": self.risk,
            "findings_summary": self.findings_summary,
            "clinical_impression": self.clinical_impression,
            "recommendations": self.recommendations,
            "image_quality": self.image_quality,
            "disclaimer": self.disclaimer,
        }

    def to_text(self) -> str:
        """Render report as plain-text clinical document."""
        lines = [
            "=" * 70,
            "AUTOMATED RETINAL SCREENING REPORT",
            f"Report ID: {self.report_id}",
            f"Study ID:  {self.study_id}",
            f"Generated: {self.generated_at}",
            "=" * 70,
            "",
            "CLASSIFICATION",
            "-" * 40,
            f"Diagnosis:   {self.classification.get('display_name', 'N/A')}",
            f"ICD-10:      {self.classification.get('icd10_code', 'N/A')}",
            f"Confidence:  {self.classification.get('confidence', 0):.1%}",
            f"Urgent:      {'YES' if self.classification.get('requires_urgent_review') else 'No'}",
            "",
            "SEVERITY GRADING",
            "-" * 40,
            f"Severity:    {self.severity.get('severity', 'N/A').title()}",
            f"Score:       {self.severity.get('severity_score', 0):.2f} / 1.00",
            f"Follow-up:   {self.severity.get('follow_up_urgency', 'N/A')}",
        ]

        etdrs = self.severity.get("etdrs_level")
        if etdrs:
            lines.append(f"ETDRS Level: {etdrs}")

        lines += [
            "",
            "FINDINGS SUMMARY",
            "-" * 40,
            self.findings_summary,
            "",
            "CLINICAL IMPRESSION",
            "-" * 40,
            self.clinical_impression,
            "",
            "RISK ASSESSMENT",
            "-" * 40,
            f"Risk Level:  {self.risk.get('risk_level', 'N/A').upper()}",
            f"Risk Score:  {self.risk.get('raw_score', 0):.2f} / 1.00",
            f"Rescreening: {self.risk.get('screening_interval_months', 'N/A')} months",
        ]

        factors = self.risk.get("contributing_factors", [])
        if factors:
            lines.append("\nContributing Risk Factors:")
            for f in factors:
                lines.append(f"  • {f}")

        lines += [
            "",
            "RECOMMENDATIONS",
            "-" * 40,
        ]
        for i, rec in enumerate(self.recommendations, 1):
            lines.append(f"{i}. {rec}")

        if self.image_quality:
            lines += [
                "",
                "IMAGE QUALITY",
                "-" * 40,
                f"Quality Score: {self.image_quality.get('quality_score', 'N/A')}",
            ]
            flags = self.image_quality.get("quality_flags", [])
            if flags:
                lines.append(f"Quality Flags: {', '.join(flags)}")

        lines += [
            "",
            "=" * 70,
            "DISCLAIMER",
            self.disclaimer,
            "=" * 70,
        ]

        return "\n".join(lines)


# Clinical narrative templates by disease
FINDINGS_TEMPLATES: dict[DiseaseLabel, dict[SeverityLevel, str]] = {
    DiseaseLabel.NORMAL: {
        SeverityLevel.NONE: (
            "Fundus examination reveals a normal appearing retina. The optic disc "
            "demonstrates a healthy pink color with sharp margins and a normal "
            "cup-to-disc ratio (< 0.5). The macula is flat and even with a "
            "well-defined foveal reflex. Retinal vasculature shows normal "
            "caliber with an arterio-venous ratio of approximately 2:3. No "
            "microaneurysms, hemorrhages, exudates, or neovascularization detected."
        ),
    },
    DiseaseLabel.DIABETIC_RETINOPATHY: {
        SeverityLevel.MILD: (
            "Fundus examination reveals mild non-proliferative diabetic retinopathy "
            "(NPDR). Scattered microaneurysms detected predominantly in the temporal "
            "quadrant. No hard exudates, cotton-wool spots, or intraretinal "
            "hemorrhages identified at this time. Macular edema not apparent. "
            "Optic disc within normal limits."
        ),
        SeverityLevel.MODERATE: (
            "Fundus examination reveals moderate NPDR. Multiple microaneurysms and "
            "dot-blot hemorrhages present in multiple quadrants. Hard exudates "
            "noted in the temporal perimacular region. Cotton-wool spots identified "
            "superior temporal. No frank neovascularization detected. Early macular "
            "changes present; formal OCT evaluation recommended."
        ),
        SeverityLevel.SEVERE: (
            "Fundus examination reveals severe NPDR. Extensive intraretinal "
            "hemorrhages noted in all four quadrants (4-2-1 rule positive). Venous "
            "beading present in two or more quadrants. Intraretinal microvascular "
            "abnormalities (IRMA) identified. Clinically significant macular edema "
            "suspected. No definitive neovascularization identified, but proliferative "
            "disease cannot be excluded without fluorescein angiography."
        ),
        SeverityLevel.PROLIFERATIVE: (
            "Fundus examination reveals proliferative diabetic retinopathy (PDR). "
            "Neovascularization of the disc (NVD) and/or neovascularization elsewhere "
            "(NVE) identified. Pre-retinal or vitreous hemorrhage present. High-risk "
            "characteristics for severe visual loss are present. Immediate "
            "ophthalmological intervention required. Risk of tractional retinal "
            "detachment is significant."
        ),
    },
    DiseaseLabel.GLAUCOMA: {
        SeverityLevel.MILD: (
            "Fundus examination reveals early glaucomatous optic neuropathy. Optic "
            "disc demonstrates mild cup-to-disc ratio enlargement (estimated CDR "
            "0.6-0.65). Inferior and/or superior neuroretinal rim thinning present. "
            "Retinal nerve fiber layer (RNFL) changes subtle. Disc hemorrhage not "
            "identified. Macula and peripheral retina otherwise unremarkable."
        ),
        SeverityLevel.MODERATE: (
            "Fundus examination reveals moderate glaucomatous changes. Optic disc "
            "shows significant cupping (estimated CDR 0.7-0.75) with neuroretinal "
            "rim thinning, predominantly inferotemporal. RNFL defects visible. "
            "Bayoneting of vessels at disc margin noted. Corresponding visual field "
            "defects expected. Intraocular pressure assessment essential."
        ),
        SeverityLevel.SEVERE: (
            "Fundus examination reveals advanced glaucomatous optic atrophy. Optic "
            "disc demonstrates marked cupping (estimated CDR > 0.8) with near-complete "
            "neuroretinal rim loss. Pallor of remaining rim tissue present, consistent "
            "with significant axonal loss. Extensive RNFL defects noted. Severe visual "
            "field loss anticipated. Urgent glaucoma specialist referral required."
        ),
        SeverityLevel.ADVANCED: (
            "Fundus examination reveals end-stage glaucoma. Complete or near-complete "
            "optic nerve cupping with only a thin rim of residual neuroretinal tissue. "
            "Bean-pot cupping morphology. Baring of circumlinear vessels. Only central "
            "or temporal island of vision likely retained. Surgical management may be "
            "the only remaining option to prevent complete blindness."
        ),
    },
    DiseaseLabel.AMD: {
        SeverityLevel.MILD: (
            "Fundus examination reveals early age-related macular degeneration. "
            "Multiple small to medium drusen (< 125 μm) identified in the macular "
            "region bilaterally. Drusen distribution primarily concentrated within "
            "2 disc diameters of the fovea. Retinal pigment epithelium (RPE) "
            "changes minimal. No geographic atrophy or subretinal fluid identified. "
            "Foveal reflex intact."
        ),
        SeverityLevel.MODERATE: (
            "Fundus examination reveals intermediate AMD. Large drusen (≥ 125 μm) "
            "identified in the macula. Pigmentary abnormalities of the RPE present, "
            "including both hyperpigmentation and hypopigmentation. Early areas of "
            "geographic atrophy may be present but not involving the foveal center. "
            "Subretinal fluid not identified. OCT imaging strongly recommended for "
            "baseline assessment."
        ),
        SeverityLevel.SEVERE: (
            "Fundus examination reveals late AMD with evidence of neovascular (wet) "
            "AMD and/or geographic atrophy. Subretinal or intraretinal fluid "
            "suspected. Subretinal hemorrhage or lipid exudate present. Choroidal "
            "neovascular membrane (CNV) likely based on fundus appearance. Immediate "
            "OCT and fluorescein angiography required. Anti-VEGF therapy initiation "
            "urgently needed to prevent further central visual loss."
        ),
        SeverityLevel.ADVANCED: (
            "Fundus examination reveals advanced AMD with disciform scarring. "
            "Subretinal fibrosis/disciform scar in the macular region consistent "
            "with end-stage neovascular AMD. Overlying RPE and photoreceptor loss. "
            "Central vision severely compromised. Low-vision rehabilitation referral "
            "indicated. Fellow eye monitoring critical for early CNV detection."
        ),
    },
    DiseaseLabel.CATARACTS: {
        SeverityLevel.MILD: (
            "Fundus examination quality mildly reduced due to early lens opacity. "
            "Incipient nuclear or cortical lens changes noted. Posterior pole "
            "visualization adequate. No definitive retinal pathology identified "
            "through the media opacity. Slit-lamp biomicroscopy recommended for "
            "lens grading. Visual acuity likely minimally affected."
        ),
        SeverityLevel.MODERATE: (
            "Fundus examination quality moderately reduced secondary to significant "
            "lens opacity. Nuclear sclerosis and/or posterior subcapsular cataract "
            "changes reduce image clarity. Posterior pole partially obscured. Full "
            "retinal assessment may not be possible until lens opacity is addressed. "
            "Glare testing and contrast sensitivity assessment recommended. "
            "Surgical evaluation appropriate."
        ),
        SeverityLevel.SEVERE: (
            "Fundus examination significantly limited by dense lens opacity. Posterior "
            "pole detail markedly obscured. Meaningful retinal assessment not possible "
            "with current media opacity. B-scan ultrasonography recommended to exclude "
            "significant posterior segment pathology prior to cataract surgery. "
            "Phacoemulsification with IOL implantation indicated. Post-operative "
            "dilated fundus examination essential."
        ),
    },
}


CLINICAL_IMPRESSION_TEMPLATES: dict[DiseaseLabel, str] = {
    DiseaseLabel.NORMAL: (
        "No retinal pathology detected on automated screening analysis. "
        "Findings are consistent with a normal fundus examination."
    ),
    DiseaseLabel.DIABETIC_RETINOPATHY: (
        "Automated analysis identifies features consistent with diabetic retinopathy. "
        "Findings should be correlated with clinical history, duration of diabetes, "
        "and current glycemic control. Results require confirmation by a "
        "qualified ophthalmologist."
    ),
    DiseaseLabel.GLAUCOMA: (
        "Automated analysis identifies optic nerve head changes suspicious for "
        "glaucomatous neuropathy. Correlation with intraocular pressure, "
        "corneal thickness, gonioscopy, and automated visual field testing is "
        "essential for definitive diagnosis."
    ),
    DiseaseLabel.AMD: (
        "Automated analysis identifies macular changes consistent with age-related "
        "macular degeneration. Classification between dry and wet AMD requires "
        "OCT imaging. Clinical correlation and specialist evaluation are required."
    ),
    DiseaseLabel.CATARACTS: (
        "Automated analysis identifies lens opacity consistent with cataract formation. "
        "Image quality may be reduced. Findings should be confirmed by slit-lamp "
        "biomicroscopy by a qualified ophthalmologist."
    ),
}

DISCLAIMER = (
    "This report was generated by an automated AI screening system (Retina-Scan-AI v1.0) "
    "and is intended to assist clinicians in the screening process. It does NOT constitute "
    "a definitive medical diagnosis. All findings must be reviewed and confirmed by a "
    "qualified ophthalmologist or retinal specialist prior to clinical decision-making. "
    "This system is not FDA-cleared for diagnostic use and is for research/screening "
    "purposes only. Do not use this report as the sole basis for clinical treatment decisions."
)


class ClinicalReportGenerator:
    """Generates structured clinical reports from retinal analysis results."""

    def generate(
        self,
        study_id: str,
        classification: ClassificationResult,
        severity: SeverityResult,
        risk: RiskScore,
        image_quality: dict | None = None,
    ) -> ClinicalReport:
        """Generate a complete clinical report.

        Args:
            study_id: Opaque study/encounter reference (no PII).
            classification: Disease classification result.
            severity: Severity grading result.
            risk: Patient risk score.
            image_quality: Optional image quality metadata from preprocessor.

        Returns:
            ClinicalReport with full narrative and structured data.
        """
        report_id = str(uuid.uuid4())
        generated_at = datetime.now(tz=UTC).isoformat()

        findings = self._generate_findings(classification.predicted_label, severity.severity)
        impression = CLINICAL_IMPRESSION_TEMPLATES.get(
            classification.predicted_label,
            "Automated analysis complete. Clinical review recommended."
        )

        # Append severity description to impression
        if classification.predicted_label != DiseaseLabel.NORMAL:
            impression += f" {severity.clinical_description}"

        report = ClinicalReport(
            report_id=report_id,
            study_id=study_id,
            generated_at=generated_at,
            classification=classification.to_dict(),
            severity=severity.to_dict(),
            risk=risk.to_dict(),
            findings_summary=findings,
            clinical_impression=impression,
            recommendations=risk.recommendations,
            image_quality=image_quality,
            disclaimer=DISCLAIMER,
        )

        logger.info(
            "Clinical report generated",
            extra={
                "report_id": report_id,
                "study_id": study_id,  # opaque ID, not PII
                "disease": classification.predicted_label.value,
                "severity": severity.severity.value,
                "risk_level": risk.risk_level.value,
            },
        )

        return report

    def _generate_findings(
        self, disease: DiseaseLabel, severity: SeverityLevel
    ) -> str:
        """Get clinical findings narrative."""
        disease_templates = FINDINGS_TEMPLATES.get(disease, {})
        if severity in disease_templates:
            return disease_templates[severity]

        # Fallback: iterate through severity levels
        for lvl in [
            SeverityLevel.NONE,
            SeverityLevel.MILD,
            SeverityLevel.MODERATE,
            SeverityLevel.SEVERE,
        ]:
            if lvl in disease_templates:
                return disease_templates[lvl]

        return (
            f"Automated analysis detected findings consistent with "
            f"{disease.value.replace('_', ' ')}. "
            "Clinical review by a qualified ophthalmologist is recommended."
        )

    def generate_batch(
        self,
        studies: list[dict],
    ) -> list[ClinicalReport]:
        """Generate reports for a batch of studies.

        Each study dict must contain keys: study_id, classification,
        severity, risk. Optionally: image_quality.
        """
        reports = []
        for study in studies:
            try:
                report = self.generate(
                    study_id=study["study_id"],
                    classification=study["classification"],
                    severity=study["severity"],
                    risk=study["risk"],
                    image_quality=study.get("image_quality"),
                )
                reports.append(report)
            except Exception as exc:
                logger.error(
                    "Failed to generate report for study %s: %s",
                    study.get("study_id", "unknown"),
                    exc,
                )
        return reports
