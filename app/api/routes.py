"""API routes for retinal disease detection endpoints.

Endpoints:
- POST /analyze        — Full analysis pipeline (classify + grade + risk + report)
- POST /classify       — Classification only
- GET  /diseases       — List supported diseases
- GET  /model/info     — Model architecture information
"""

from __future__ import annotations

import io
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from PIL import Image
from pydantic import BaseModel

from app.models.classifier import DiseaseLabel, RetinalClassifier
from app.models.risk_scoring import ClinicalMetadata, RiskScorer
from app.models.severity import SeverityGrader
from app.preprocessing.pipeline import RetinalPreprocessor
from app.reporting.clinical_report import ClinicalReportGenerator

logger = logging.getLogger(__name__)

router = APIRouter()

# Maximum image size: 20 MB
MAX_IMAGE_BYTES = 20 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/tiff", "image/bmp"}


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
    """Validate uploaded image file."""
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
            detail=f"Image too large. Maximum size: {MAX_IMAGE_BYTES // (1024*1024)} MB",
        )

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=422, detail="Cannot decode image. Ensure file is a valid image.")

    return image_bytes, image


@router.post("/analyze", response_model=AnalysisResponse, tags=["inference"])
async def analyze_fundus(
    request: Request,
    file: Annotated[UploadFile, File(description="Retinal fundus image (JPEG/PNG)")],
    study_id: Annotated[str | None, Form(description="Opaque study reference ID")] = None,
    patient_age: Annotated[int | None, Form(description="Patient age in years")] = None,
    diabetes_duration: Annotated[int | None, Form(description="Diabetes duration in years")] = None,
    hba1c: Annotated[float | None, Form(description="HbA1c percentage")] = None,
    has_hypertension: Annotated[bool, Form()] = False,
) -> AnalysisResponse:
    """Full retinal analysis pipeline.

    Runs preprocessing, disease classification, severity grading,
    risk scoring, and clinical report generation.

    HIPAA note: study_id must be an opaque reference with no PII embedded.
    Do not submit patient names, DOB, or MRN in any field.
    """
    _validate_image_upload(file)
    components = _get_components(request)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    sid = study_id or str(uuid.uuid4())

    _, image = await _read_image(file)

    preprocessor: RetinalPreprocessor = components["preprocessor"]
    classifier: RetinalClassifier = components["classifier"]
    grader: SeverityGrader = components["severity_grader"]
    scorer: RiskScorer = components["risk_scorer"]
    reporter: ClinicalReportGenerator = components["report_generator"]

    # 1. Preprocessing
    prep_result = preprocessor.process(image)
    image_features = RetinalPreprocessor.extract_image_features(
        __import__("numpy").array(prep_result.processed_image)
    )

    # 2. Classification
    classification = classifier.classify(prep_result.processed_image)

    # 3. Severity grading
    severity = grader.grade(classification, image_features)

    # 4. Risk scoring — build metadata from optional clinical params
    metadata = ClinicalMetadata(
        age=patient_age,
        diabetes_duration_years=diabetes_duration,
        hba1c_percent=hba1c,
        has_hypertension=has_hypertension,
    )
    risk = scorer.compute(classification, severity, metadata)

    # 5. Report generation
    report = reporter.generate(
        study_id=sid,
        classification=classification,
        severity=severity,
        risk=risk,
        image_quality=prep_result.to_dict(),
    )

    logger.info(
        "analysis_complete",
        extra={
            "request_id": request_id,
            "study_id": sid,
            "disease": classification.predicted_label.value,
            "risk_level": risk.risk_level.value,
        },
    )

    return AnalysisResponse(
        request_id=request_id,
        study_id=sid,
        classification=classification.to_dict(),
        severity=severity.to_dict(),
        risk=risk.to_dict(),
        report=report.to_dict(),
        preprocessing=prep_result.to_dict(),
        model_info=classifier.get_model_architecture_summary(),
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
    """List all supported retinal disease categories."""
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
