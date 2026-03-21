"""Screening workflow agent for batch retinal image processing.

Orchestrates the full screening pipeline:
1. Receives batch of retinal images
2. Runs preprocessing + classification + severity grading
3. Prioritizes patients by risk (critical first)
4. Generates natural language screening summary via OpenAI
5. Returns structured output with action items

DISCLAIMER: This is an AI-assisted tool. All findings must be confirmed by a
qualified ophthalmologist.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "This is an AI-assisted tool. All findings must be confirmed by a qualified ophthalmologist."
)

# Risk level ordering for prioritization (higher index = higher priority)
_RISK_PRIORITY: dict[str, int] = {
    "minimal": 0,
    "low": 1,
    "moderate": 2,
    "high": 3,
    "critical": 4,
}


class AgentStatus(StrEnum):
    """Agent execution status."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PatientRecord:
    """Input record for a single patient in the screening batch."""

    image: Image.Image
    patient_ref: str = ""  # opaque reference, no PII
    laterality: str = "unspecified"
    patient_age: int | None = None
    diabetes_duration: int | None = None
    hba1c: float | None = None
    has_hypertension: bool = False


@dataclass
class ScreeningResult:
    """Result for a single patient in the batch."""

    patient_ref: str
    study_id: str
    status: str  # "success" | "error" | "needs_rescan"
    classification: dict[str, Any] | None = None
    severity: dict[str, Any] | None = None
    risk: dict[str, Any] | None = None
    risk_priority: int = 0
    action_items: list[str] = field(default_factory=list)
    error: str | None = None
    flagged_urgent: bool = False
    needs_rescan: bool = False


@dataclass
class ScreeningSession:
    """Full output of a screening agent run."""

    session_id: str
    status: AgentStatus
    total_patients: int
    succeeded: int
    failed: int
    urgent_cases: int
    results: list[ScreeningResult] = field(default_factory=list)
    summary: str = ""
    action_items: list[str] = field(default_factory=list)
    disclaimer: str = DISCLAIMER


def _extract_image_quality_score(prep_result: Any) -> float:
    """Extract a 0-1 quality score from preprocessing result."""
    try:
        prep_dict = prep_result.to_dict() if hasattr(prep_result, "to_dict") else {}
        quality = prep_dict.get("quality_score", prep_dict.get("quality", 1.0))
        return float(quality)
    except Exception:
        return 1.0


def _determine_action_items(
    classification: dict[str, Any],
    risk: dict[str, Any],
) -> list[str]:
    """Determine action items based on classification and risk level."""
    actions: list[str] = []
    risk_level = risk.get("risk_level", "").lower()
    label = classification.get("predicted_label", "").lower()
    urgent = classification.get("requires_urgent_review", False)

    if urgent or risk_level in ("critical", "high"):
        actions.append("URGENT: Immediate ophthalmologist referral required")
    if risk_level == "critical":
        actions.append("Schedule same-day or next-day specialist appointment")
    elif risk_level == "high":
        actions.append("Schedule specialist appointment within 1 week")
    elif risk_level == "moderate":
        actions.append("Schedule specialist appointment within 1 month")
    elif risk_level in ("low", "minimal"):
        actions.append("Routine follow-up at next scheduled screening")

    if label == "diabetic_retinopathy":
        actions.append("Optimize glycemic control — discuss HbA1c targets")
        actions.append("Screen for diabetic nephropathy and neuropathy")
    elif label == "glaucoma":
        actions.append("Measure intraocular pressure")
        actions.append("Visual field testing recommended")
    elif label == "amd":
        actions.append("Assess for anti-VEGF therapy eligibility")
        actions.append("Low-vision aids assessment if advanced")
    elif label == "cataracts":
        actions.append("Assess visual acuity impact for surgical candidacy")

    return actions


class ScreeningAgent:
    """AI agent orchestrating the full retinal screening workflow.

    Processes batches of retinal images through the full analysis pipeline,
    prioritizes by risk, flags urgent cases, and generates a natural language
    summary using OpenAI.

    Raises:
        EnvironmentError: If OPENAI_API_KEY is not set.
    """

    def __init__(
        self,
        api_key: str | None = None,
        components: dict[str, Any] | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise OSError(
                "OPENAI_API_KEY environment variable is not set. "
                "Please set it before using the ScreeningAgent."
            )
        self._components = components or {}
        self._status = AgentStatus.IDLE
        self._openai_client: Any = None  # lazy-initialized

    @property
    def status(self) -> AgentStatus:
        return self._status

    def _get_openai_client(self) -> Any:
        """Lazy-initialize OpenAI client."""
        if self._openai_client is None:
            try:
                from openai import OpenAI  # noqa: PLC0415
                self._openai_client = OpenAI(api_key=self._api_key)
            except ImportError as exc:
                raise ImportError(
                    "openai package is required. Install with: pip install openai"
                ) from exc
        return self._openai_client

    def _get_components(self) -> dict[str, Any]:
        """Get pipeline components, initializing defaults if needed."""
        if self._components:
            return self._components

        # Lazy-init default components
        from app.models.classifier import RetinalClassifier  # noqa: PLC0415
        from app.models.risk_scoring import RiskScorer  # noqa: PLC0415
        from app.models.severity import SeverityGrader  # noqa: PLC0415
        from app.preprocessing.pipeline import RetinalPreprocessor  # noqa: PLC0415
        from app.reporting.clinical_report import ClinicalReportGenerator  # noqa: PLC0415

        self._components = {
            "preprocessor": RetinalPreprocessor(),
            "classifier": RetinalClassifier(demo_mode=True),
            "severity_grader": SeverityGrader(),
            "risk_scorer": RiskScorer(),
            "report_generator": ClinicalReportGenerator(),
        }
        return self._components

    def _process_single(self, record: PatientRecord) -> ScreeningResult:
        """Run full analysis pipeline on a single patient record."""
        import numpy as np  # noqa: PLC0415

        from app.models.risk_scoring import ClinicalMetadata  # noqa: PLC0415
        from app.reporting.clinical_report import Laterality  # noqa: PLC0415

        study_id = str(uuid.uuid4())
        patient_ref = record.patient_ref or study_id

        components = self._get_components()
        preprocessor = components["preprocessor"]
        classifier = components["classifier"]
        grader = components["severity_grader"]
        scorer = components["risk_scorer"]

        # Preprocessing
        prep_result = preprocessor.process(record.image)
        quality_score = _extract_image_quality_score(prep_result)

        # Flag low-quality images for rescan
        if quality_score < 0.3:
            return ScreeningResult(
                patient_ref=patient_ref,
                study_id=study_id,
                status="needs_rescan",
                needs_rescan=True,
                action_items=["Low image quality detected — rescan recommended"],
            )

        image_features = preprocessor.extract_image_features(np.array(prep_result.processed_image))
        classification = classifier.classify(prep_result.processed_image)

        # Laterality mapping
        lat_map = {
            "od": Laterality.RIGHT, "right": Laterality.RIGHT,
            "os": Laterality.LEFT, "left": Laterality.LEFT,
            "ou": Laterality.BOTH, "both": Laterality.BOTH,
        }
        lat_map.get(record.laterality.lower(), Laterality.UNSPECIFIED)

        severity = grader.grade(classification, image_features)

        metadata = ClinicalMetadata(
            age=record.patient_age,
            diabetes_duration_years=record.diabetes_duration,
            hba1c_percent=record.hba1c,
            has_hypertension=record.has_hypertension,
        )
        risk = scorer.compute(classification, severity, metadata)

        class_dict = classification.to_dict()
        risk_dict = risk.to_dict()
        sev_dict = severity.to_dict()

        risk_level = risk_dict.get("risk_level", "low")
        priority = _RISK_PRIORITY.get(risk_level.lower(), 0)
        flagged = classification.requires_urgent_review or risk_level.lower() in ("critical", "high")
        action_items = _determine_action_items(class_dict, risk_dict)

        return ScreeningResult(
            patient_ref=patient_ref,
            study_id=study_id,
            status="success",
            classification=class_dict,
            severity=sev_dict,
            risk=risk_dict,
            risk_priority=priority,
            action_items=action_items,
            flagged_urgent=flagged,
        )

    def _generate_summary(self, session: ScreeningSession) -> str:
        """Generate a natural language screening summary via OpenAI."""
        urgent_refs = [r.patient_ref for r in session.results if r.flagged_urgent]
        rescan_refs = [r.patient_ref for r in session.results if r.needs_rescan]

        # Build stats
        disease_counts: dict[str, int] = {}
        for r in session.results:
            if r.classification:
                label = r.classification.get("predicted_label", "unknown")
                disease_counts[label] = disease_counts.get(label, 0) + 1

        prompt = (
            f"You are a clinical AI assistant summarizing a retinal screening session.\n\n"
            f"Screening session statistics:\n"
            f"- Total patients screened: {session.total_patients}\n"
            f"- Successfully processed: {session.succeeded}\n"
            f"- Failed/errors: {session.failed}\n"
            f"- Urgent cases requiring immediate referral: {session.urgent_cases}\n"
            f"- Cases needing rescan: {len(rescan_refs)}\n"
            f"- Disease distribution: {disease_counts}\n"
            f"- Urgent patient references: {urgent_refs[:5]}\n\n"
            f"Write a concise 2-3 paragraph clinical summary of this screening session "
            f"for the supervising ophthalmologist. Include key findings, urgent action items, "
            f"and overall population health observations. "
            f"End with: '{DISCLAIMER}'"
        )

        try:
            client = self._get_openai_client()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.3,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.error("Failed to generate OpenAI summary: %s", exc)
            # Fallback: structured summary without AI narrative
            return (
                f"Screening session completed. "
                f"{session.total_patients} patients processed, "
                f"{session.urgent_cases} urgent referrals identified. "
                f"Disease distribution: {disease_counts}. "
                f"{DISCLAIMER}"
            )

    def run_screening(self, records: list[PatientRecord]) -> ScreeningSession:
        """Run the full screening workflow on a batch of patient records.

        Args:
            records: List of PatientRecord objects with images and metadata.

        Returns:
            ScreeningSession with prioritized results, summary, and action items.
        """
        self._status = AgentStatus.RUNNING
        session_id = str(uuid.uuid4())

        results: list[ScreeningResult] = []
        succeeded = 0
        failed = 0
        urgent_cases = 0

        for record in records:
            try:
                result = self._process_single(record)
                results.append(result)
                if result.status == "success":
                    succeeded += 1
                    if result.flagged_urgent:
                        urgent_cases += 1
                elif result.status == "needs_rescan":
                    succeeded += 1  # processed, just needs rescan
                else:
                    failed += 1
            except Exception as exc:
                logger.error("Failed to process patient %s: %s", record.patient_ref, exc)
                results.append(ScreeningResult(
                    patient_ref=record.patient_ref or "unknown",
                    study_id=str(uuid.uuid4()),
                    status="error",
                    error=str(exc),
                ))
                failed += 1

        # Prioritize: urgent/high-risk first
        results.sort(key=lambda r: r.risk_priority, reverse=True)

        # Aggregate action items
        aggregate_actions: list[str] = []
        if urgent_cases > 0:
            aggregate_actions.append(
                f"{urgent_cases} patient(s) require urgent ophthalmologist referral"
            )
        rescan_count = sum(1 for r in results if r.needs_rescan)
        if rescan_count > 0:
            aggregate_actions.append(f"{rescan_count} patient(s) require image rescan")

        session = ScreeningSession(
            session_id=session_id,
            status=AgentStatus.COMPLETED,
            total_patients=len(records),
            succeeded=succeeded,
            failed=failed,
            urgent_cases=urgent_cases,
            results=results,
            action_items=aggregate_actions,
        )

        # Generate AI narrative summary
        session.summary = self._generate_summary(session)

        self._status = AgentStatus.COMPLETED
        return session

    def get_status(self) -> dict[str, Any]:
        """Return current agent status."""
        return {
            "status": self._status.value,
            "disclaimer": DISCLAIMER,
        }
