"""API routes for retinal disease detection endpoints.

Endpoints:
- POST /analyze          — Full analysis pipeline (classify + grade + risk + report)
- POST /analyze/batch    — Batch screening for population health workflows
- POST /classify         — Classification only
- GET  /diseases         — List supported diseases
- GET  /model/info       — Model architecture information
- GET  /metrics          — Population health screening metrics
- GET  /ops/validation-summary — Synthetic engineering-validation artifact
- GET  /ops/monitoring   — Runtime monitoring snapshot
- GET  /ops/release-readiness — Portfolio-safe readiness gates
- POST /chat             — Chat with clinical AI assistant about a scan result
- POST /agent/screen     — Run screening agent on batch of images
- GET  /agent/status     — Get screening agent status

FHIR: Pass ?format=fhir to /analyze for FHIR R4 DiagnosticReport output.
"""

from __future__ import annotations

import io
import logging
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from PIL import Image
from pydantic import BaseModel

from app.models.classifier import DiseaseLabel, RetinalClassifier
from app.models.risk_scoring import ClinicalMetadata, RiskScorer
from app.models.severity import SeverityGrader
from app.monitoring.runtime import RuntimeMonitor
from app.preprocessing.pipeline import RetinalPreprocessor
from app.reporting.clinical_report import ClinicalReportGenerator, Laterality

logger = logging.getLogger(__name__)

router = APIRouter()

# Maximum image size: 20 MB
MAX_IMAGE_BYTES = 20 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/tiff", "image/bmp"}

# Rate limiting headers (informational — enforce at gateway/reverse proxy)
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW_SECONDS = 60

# In-memory screening metrics (reset on restart; use Redis in production)
_screening_metrics: dict = {
    "total_screens": 0,
    "disease_counts": {lbl.value: 0 for lbl in DiseaseLabel},
    "urgent_referrals": 0,
    "start_time": time.time(),
}
_runtime_monitor = RuntimeMonitor()


class AnalysisResponse(BaseModel):
    """Full analysis pipeline response."""

    request_id: str
    study_id: str
    classification: dict
    severity: dict
    risk: dict
    report: dict
    preprocessing: dict
    model_info: dict


class ClassifyResponse(BaseModel):
    """Classification-only response."""

    request_id: str
    study_id: str
    classification: dict
    model_info: dict


class BatchAnalysisItem(BaseModel):
    """Result for a single item in a batch screening response."""

    study_id: str
    status: str  # "success" | "error"
    classification: dict | None = None
    severity: dict | None = None
    risk: dict | None = None
    report: dict | None = None
    preprocessing: dict | None = None
    error: str | None = None


class BatchAnalysisResponse(BaseModel):
    """Batch screening response for population health."""

    request_id: str
    total: int
    succeeded: int
    failed: int
    results: list[BatchAnalysisItem]


class DiseaseInfo(BaseModel):
    """Information about a supported disease."""

    label: str
    display_name: str
    icd10_code: str
    description: str


def _get_components(request: Request) -> dict:
    """Retrieve initialized components from app state."""
    components = getattr(request.state, "components", {})
    if not components:
        raise HTTPException(
            status_code=503,
            detail="Service components not initialized. Please try again shortly.",
        )
    return components


def _validate_image_upload(file: UploadFile) -> None:
    """Validate uploaded image file content type."""
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported image format: {file.content_type}. "
            f"Supported: {', '.join(ALLOWED_CONTENT_TYPES)}",
        )


async def _read_image(file: UploadFile) -> tuple[bytes, Image.Image]:
    """Read and decode uploaded image, enforcing size limits."""
    image_bytes = await file.read()

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large. Maximum size: {MAX_IMAGE_BYTES // (1024 * 1024)} MB",
        )

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail="Cannot decode image. Ensure file is a valid image."
        ) from exc

    return image_bytes, image


def _add_rate_limit_headers(response_headers: dict) -> dict:
    """Add rate limiting informational headers to a response dict."""
    response_headers["X-RateLimit-Limit"] = str(RATE_LIMIT_REQUESTS)
    response_headers["X-RateLimit-Window"] = str(RATE_LIMIT_WINDOW_SECONDS)
    return response_headers


def _run_full_pipeline(
    image: Image.Image,
    components: dict,
    study_id: str,
    patient_age: int | None = None,
    diabetes_duration: int | None = None,
    hba1c: float | None = None,
    has_hypertension: bool = False,
    laterality: Laterality = Laterality.UNSPECIFIED,
) -> dict:
    """Run the complete analysis pipeline and return structured results.

    Args:
        image: Decoded PIL Image.
        components: Initialized app components dict.
        study_id: Opaque study reference.
        patient_age: Optional patient age for risk scoring.
        diabetes_duration: Optional diabetes duration in years.
        hba1c: Optional HbA1c percentage.
        has_hypertension: Whether hypertension is present.
        laterality: Eye laterality for the image.

    Returns:
        Dict with classification, severity, risk, report, preprocessing keys.
    """
    import numpy as np

    started_at = time.monotonic()

    preprocessor: RetinalPreprocessor = components["preprocessor"]
    classifier: RetinalClassifier = components["classifier"]
    grader: SeverityGrader = components["severity_grader"]
    scorer: RiskScorer = components["risk_scorer"]
    reporter: ClinicalReportGenerator = components["report_generator"]

    # 1. Preprocessing
    prep_result = preprocessor.process(image)
    image_features = RetinalPreprocessor.extract_image_features(
        np.array(prep_result.processed_image)
    )

    # 2. Classification
    classification = classifier.classify(prep_result.processed_image)

    # 3. Severity grading
    severity = grader.grade(classification, image_features)

    # 4. Risk scoring
    metadata = ClinicalMetadata(
        age=patient_age,
        diabetes_duration_years=diabetes_duration,
        hba1c_percent=hba1c,
        has_hypertension=has_hypertension,
    )
    risk = scorer.compute(classification, severity, metadata)

    # 5. Report generation
    report = reporter.generate(
        study_id=study_id,
        classification=classification,
        severity=severity,
        risk=risk,
        image_quality=prep_result.to_dict(),
        laterality=laterality,
    )

    # Update screening metrics
    _screening_metrics["total_screens"] += 1
    _screening_metrics["disease_counts"][classification.predicted_label.value] += 1
    if classification.requires_urgent_review:
        _screening_metrics["urgent_referrals"] += 1

    elapsed_ms = (time.monotonic() - started_at) * 1000
    _runtime_monitor.record_inference(
        preprocessing=prep_result.to_dict(),
        model_info=classifier.get_model_architecture_summary(),
        elapsed_ms=elapsed_ms,
    )

    return {
        "classification": classification.to_dict(),
        "severity": severity.to_dict(),
        "risk": risk.to_dict(),
        "report": report.to_dict(),
        "preprocessing": prep_result.to_dict(),
        "model_info": classifier.get_model_architecture_summary(),
        "_report_obj": report,  # kept for FHIR rendering
    }


@router.post("/analyze", response_model=AnalysisResponse, tags=["inference"])
async def analyze_fundus(
    request: Request,
    file: Annotated[UploadFile, File(description="Retinal fundus image (JPEG/PNG)")],
    study_id: Annotated[str | None, Form(description="Opaque study reference ID")] = None,
    patient_age: Annotated[int | None, Form(description="Patient age in years")] = None,
    diabetes_duration: Annotated[int | None, Form(description="Diabetes duration in years")] = None,
    hba1c: Annotated[float | None, Form(description="HbA1c percentage")] = None,
    has_hypertension: Annotated[bool, Form()] = False,
    laterality: Annotated[
        str, Form(description="Eye laterality: OD, OS, OU, or unspecified")
    ] = "unspecified",
    format: Annotated[str, Form(description="Response format: json (default) or fhir")] = "json",
) -> AnalysisResponse:
    """Full retinal analysis pipeline.

    Runs preprocessing, disease classification, severity grading,
    risk scoring, and clinical report generation.

    Supports FHIR R4 output via format=fhir parameter.

    HIPAA note: study_id must be an opaque reference with no PII embedded.
    Do not submit patient names, DOB, or MRN in any field.
    """
    _validate_image_upload(file)
    components = _get_components(request)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    sid = study_id or str(uuid.uuid4())

    _, image = await _read_image(file)

    # Resolve laterality enum
    lat = _parse_laterality(laterality)

    pipeline_result = _run_full_pipeline(
        image=image,
        components=components,
        study_id=sid,
        patient_age=patient_age,
        diabetes_duration=diabetes_duration,
        hba1c=hba1c,
        has_hypertension=has_hypertension,
        laterality=lat,
    )

    # FHIR format override
    report_output = pipeline_result["report"]
    if format.lower() == "fhir":
        report_obj = pipeline_result["_report_obj"]
        report_output = report_obj.to_fhir()

    logger.info(
        "analysis_complete",
        extra={
            "request_id": request_id,
            "study_id": sid,
            "disease": pipeline_result["classification"]["predicted_label"],
            "risk_level": pipeline_result["risk"]["risk_level"],
        },
    )

    return AnalysisResponse(
        request_id=request_id,
        study_id=sid,
        classification=pipeline_result["classification"],
        severity=pipeline_result["severity"],
        risk=pipeline_result["risk"],
        report=report_output,
        preprocessing=pipeline_result["preprocessing"],
        model_info=pipeline_result["model_info"],
    )


@router.post("/analyze/batch", response_model=BatchAnalysisResponse, tags=["inference"])
async def analyze_fundus_batch(
    request: Request,
    files: Annotated[list[UploadFile], File(description="List of retinal fundus images")],
    laterality: Annotated[
        str, Form(description="Eye laterality applied to all images")
    ] = "unspecified",
) -> BatchAnalysisResponse:
    """Batch screening endpoint for population health workflows.

    Accepts multiple fundus images and runs the full analysis pipeline on each.
    Designed for high-throughput diabetic retinopathy screening programs.

    Returns per-image results with individual success/error status.
    Maximum batch size: 50 images.

    HIPAA note: No patient identifiers should be embedded in filenames.
    """
    if len(files) > 50:
        raise HTTPException(
            status_code=400,
            detail="Batch size exceeds maximum of 50 images.",
        )

    components = _get_components(request)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    lat = _parse_laterality(laterality)

    results: list[BatchAnalysisItem] = []
    succeeded = 0
    failed = 0

    for upload_file in files:
        study_id = str(uuid.uuid4())
        try:
            _validate_image_upload(upload_file)
            _, image = await _read_image(upload_file)

            pipeline_result = _run_full_pipeline(
                image=image,
                components=components,
                study_id=study_id,
                laterality=lat,
            )

            results.append(
                BatchAnalysisItem(
                    study_id=study_id,
                    status="success",
                    classification=pipeline_result["classification"],
                    severity=pipeline_result["severity"],
                    risk=pipeline_result["risk"],
                    report=pipeline_result["report"],
                    preprocessing=pipeline_result["preprocessing"],
                )
            )
            succeeded += 1

        except HTTPException as exc:
            results.append(
                BatchAnalysisItem(
                    study_id=study_id,
                    status="error",
                    error=exc.detail,
                )
            )
            failed += 1
        except Exception as exc:
            logger.error("Batch item processing failed: %s", exc)
            results.append(
                BatchAnalysisItem(
                    study_id=study_id,
                    status="error",
                    error="Internal processing error.",
                )
            )
            failed += 1

    logger.info(
        "batch_screening_complete",
        extra={
            "request_id": request_id,
            "total": len(files),
            "succeeded": succeeded,
            "failed": failed,
        },
    )

    return BatchAnalysisResponse(
        request_id=request_id,
        total=len(files),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )


@router.post("/classify", response_model=ClassifyResponse, tags=["inference"])
async def classify_fundus(
    request: Request,
    file: Annotated[UploadFile, File(description="Retinal fundus image (JPEG/PNG)")],
    study_id: Annotated[str | None, Form(description="Opaque study reference ID")] = None,
) -> ClassifyResponse:
    """Classify a retinal fundus image (classification only, no full report)."""
    _validate_image_upload(file)
    components = _get_components(request)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    sid = study_id or str(uuid.uuid4())

    _, image = await _read_image(file)

    preprocessor: RetinalPreprocessor = components["preprocessor"]
    classifier: RetinalClassifier = components["classifier"]

    prep_result = preprocessor.process(image)
    classification = classifier.classify(prep_result.processed_image)

    return ClassifyResponse(
        request_id=request_id,
        study_id=sid,
        classification=classification.to_dict(),
        model_info=classifier.get_model_architecture_summary(),
    )


@router.get("/diseases", response_model=list[DiseaseInfo], tags=["reference"])
async def list_diseases() -> list[DiseaseInfo]:
    """List all supported retinal disease categories with ICD-10 codes."""
    from app.models.classifier import DISEASE_DISPLAY_NAMES, ICD10_CODES

    descriptions = {
        DiseaseLabel.NORMAL: "No retinal pathology detected.",
        DiseaseLabel.DIABETIC_RETINOPATHY: (
            "Microvascular complication of diabetes affecting the retina. "
            "Graded using ETDRS-like scale: mild/moderate/severe NPDR and PDR."
        ),
        DiseaseLabel.GLAUCOMA: (
            "Progressive optic neuropathy with characteristic optic disc cupping "
            "and corresponding visual field loss."
        ),
        DiseaseLabel.AMD: (
            "Age-related degeneration of the macula leading to central vision loss. "
            "Classified as dry (geographic atrophy) or wet (neovascular)."
        ),
        DiseaseLabel.CATARACTS: (
            "Opacification of the crystalline lens causing progressive visual impairment."
        ),
    }

    return [
        DiseaseInfo(
            label=disease.value,
            display_name=DISEASE_DISPLAY_NAMES[disease],
            icd10_code=ICD10_CODES[disease],
            description=descriptions[disease],
        )
        for disease in DiseaseLabel
    ]


@router.get("/model/info", tags=["reference"])
async def model_info(request: Request) -> dict:
    """Return model architecture and configuration information."""
    components = _get_components(request)
    classifier: RetinalClassifier = components["classifier"]
    return classifier.get_model_architecture_summary()


@router.get("/metrics", tags=["system"])
async def screening_metrics() -> dict:
    """Population health screening metrics.

    Returns aggregate screening statistics since last service restart.
    No patient-identifiable data is included in these metrics.
    """
    uptime_seconds = time.time() - _screening_metrics["start_time"]
    total = _screening_metrics["total_screens"]
    disease_counts = _screening_metrics["disease_counts"]

    # Compute disease distribution percentages
    distribution = {}
    for disease, count in disease_counts.items():
        distribution[disease] = {
            "count": count,
            "percentage": round((count / total * 100) if total > 0 else 0.0, 2),
        }

    return {
        "total_screens": total,
        "urgent_referrals": _screening_metrics["urgent_referrals"],
        "urgent_referral_rate": round(
            (_screening_metrics["urgent_referrals"] / total * 100) if total > 0 else 0.0, 2
        ),
        "disease_distribution": distribution,
        "uptime_seconds": round(uptime_seconds, 1),
        "screens_per_hour": round(
            (total / uptime_seconds * 3600) if uptime_seconds > 0 else 0.0, 2
        ),
    }


@router.get("/ops/validation-summary", tags=["ops"])
async def ops_validation_summary() -> dict:
    """Return the bundled engineering-validation summary.

    This repository ships synthetic/offline evaluation artifacts to support
    engineering review. The response must not be interpreted as clinical
    validation.
    """
    return _runtime_monitor.get_validation_summary()


@router.get("/ops/monitoring", tags=["ops"])
async def ops_monitoring() -> dict:
    """Return compact runtime monitoring information for portfolio review."""
    return _runtime_monitor.get_monitoring_snapshot()


@router.get("/ops/release-readiness", tags=["ops"])
async def ops_release_readiness() -> dict:
    """Return portfolio-safe release readiness gates.

    The status here is intentionally framed as portfolio review readiness,
    not regulatory or clinical readiness.
    """
    return _runtime_monitor.get_release_readiness()


def _parse_laterality(value: str) -> Laterality:
    """Parse laterality string to enum, defaulting to UNSPECIFIED."""
    mapping = {
        "od": Laterality.RIGHT,
        "right": Laterality.RIGHT,
        "os": Laterality.LEFT,
        "left": Laterality.LEFT,
        "ou": Laterality.BOTH,
        "both": Laterality.BOTH,
        "bilateral": Laterality.BOTH,
    }
    return mapping.get(value.lower().strip(), Laterality.UNSPECIFIED)


# ── Clinical AI Chatbot ───────────────────────────────────────────────────────

# In-memory chat sessions (use Redis in production for persistence)
_chat_sessions: dict[str, object] = {}


class ChatRequest(BaseModel):
    """Request body for POST /chat."""

    session_id: str | None = None
    message: str
    classification: str = "unknown"
    severity: str = "unknown"
    risk_score: float | str = 0.0
    risk_level: str = "unknown"


class ChatResponse(BaseModel):
    """Response from POST /chat."""

    session_id: str
    reply: str
    disclaimer: str


@router.post("/chat", response_model=ChatResponse, tags=["ai-assistant"])
async def chat_with_assistant(body: ChatRequest) -> ChatResponse:
    """Chat with the clinical AI assistant about a retinal scan result.

    Maintains multi-turn conversation history per session_id.
    Requires OPENAI_API_KEY environment variable to be set.

    DISCLAIMER: This is an AI-assisted tool. All findings must be confirmed
    by a qualified ophthalmologist.
    """
    from app.chatbot.assistant import ClinicalAssistant  # noqa: PLC0415

    try:
        assistant = ClinicalAssistant()
    except OSError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Retrieve or create session
    session_id = body.session_id or str(uuid.uuid4())
    if session_id in _chat_sessions:
        session = _chat_sessions[session_id]
    else:
        session = assistant.create_session(
            classification=body.classification,
            severity=body.severity,
            risk_score=body.risk_score,
            risk_level=body.risk_level,
            session_id=session_id,
        )
        _chat_sessions[session_id] = session

    try:
        reply = assistant.chat(session, body.message)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        disclaimer=assistant.get_disclaimer(),
    )


# ── Screening Workflow Agent ──────────────────────────────────────────────────

# Singleton agent (stateless between runs; status tracked per-process)
_screening_agent: object | None = None


def _get_screening_agent() -> object:
    """Get or create the screening agent singleton."""
    global _screening_agent  # noqa: PLW0603
    if _screening_agent is None:
        from app.agent.orchestrator import ScreeningAgent  # noqa: PLC0415

        try:
            _screening_agent = ScreeningAgent()
        except OSError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _screening_agent


@router.post("/agent/screen", tags=["ai-agent"])
async def run_screening_agent(
    request: Request,
    files: Annotated[list[UploadFile], File(description="Batch of retinal fundus images")],
    laterality: Annotated[
        str, Form(description="Eye laterality applied to all images")
    ] = "unspecified",
) -> dict:
    """Run the AI screening agent on a batch of retinal images.

    Orchestrates the full screening workflow:
    - Preprocesses and classifies each image
    - Prioritizes patients by risk level (critical first)
    - Flags urgent cases requiring immediate referral
    - Suggests re-scans for low-quality images
    - Generates a natural language summary via OpenAI

    Requires OPENAI_API_KEY environment variable to be set.
    Maximum batch size: 50 images.

    DISCLAIMER: This is an AI-assisted tool. All findings must be confirmed
    by a qualified ophthalmologist.
    """
    if len(files) > 50:
        raise HTTPException(
            status_code=400,
            detail="Batch size exceeds maximum of 50 images.",
        )

    from app.agent.orchestrator import PatientRecord, ScreeningAgent  # noqa: PLC0415

    components = getattr(request.state, "components", {})

    try:
        agent = ScreeningAgent(components=components)
    except OSError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    records = []
    for upload_file in files:
        try:
            _validate_image_upload(upload_file)
            _, image = await _read_image(upload_file)
            records.append(
                PatientRecord(
                    image=image,
                    patient_ref=str(uuid.uuid4()),
                    laterality=laterality,
                )
            )
        except HTTPException:
            # Skip invalid images — they'll be counted as failed
            records.append(
                PatientRecord(
                    image=Image.new("RGB", (256, 256), color=(128, 128, 128)),
                    patient_ref="invalid_image",
                )
            )

    session = agent.run_screening(records)

    # Serialize results
    results_out = []
    for r in session.results:
        results_out.append(
            {
                "patient_ref": r.patient_ref,
                "study_id": r.study_id,
                "status": r.status,
                "classification": r.classification,
                "severity": r.severity,
                "risk": r.risk,
                "flagged_urgent": r.flagged_urgent,
                "needs_rescan": r.needs_rescan,
                "action_items": r.action_items,
                "error": r.error,
            }
        )

    return {
        "session_id": session.session_id,
        "status": session.status.value,
        "total_patients": session.total_patients,
        "succeeded": session.succeeded,
        "failed": session.failed,
        "urgent_cases": session.urgent_cases,
        "summary": session.summary,
        "action_items": session.action_items,
        "results": results_out,
        "disclaimer": session.disclaimer,
    }


@router.get("/agent/status", tags=["ai-agent"])
async def agent_status() -> dict:
    """Get the current status of the screening agent.

    Returns agent readiness and disclaimer information.
    Requires OPENAI_API_KEY environment variable to be set.
    """
    import os  # noqa: PLC0415

    from app.agent.orchestrator import DISCLAIMER  # noqa: PLC0415

    api_key_set = bool(os.environ.get("OPENAI_API_KEY"))
    return {
        "agent": "screening_agent",
        "api_key_configured": api_key_set,
        "status": "ready" if api_key_set else "unavailable",
        "disclaimer": DISCLAIMER,
    }
