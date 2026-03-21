"""FastAPI application for Retina-Scan-AI retinal disease detection.

HIPAA-aware design:
- Audit logging for all inference requests (no PII in logs)
- Access control headers on all responses
- Structured JSON logging with correlation IDs
- No patient identifiers stored beyond opaque study_id
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.models.classifier import RetinalClassifier
from app.models.risk_scoring import RiskScorer
from app.models.severity import SeverityGrader
from app.preprocessing.pipeline import RetinalPreprocessor
from app.reporting.clinical_report import ClinicalReportGenerator

# Configure structured logging (HIPAA-aware: no PII in log fields)
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Application state container
_app_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize and teardown application resources."""
    logger.info("Retina-Scan-AI starting up", version="0.1.0")

    # Initialize all components (demo mode — no model file required)
    _app_state["classifier"] = RetinalClassifier(demo_mode=True)
    _app_state["severity_grader"] = SeverityGrader()
    _app_state["risk_scorer"] = RiskScorer()
    _app_state["preprocessor"] = RetinalPreprocessor()
    _app_state["report_generator"] = ClinicalReportGenerator()

    logger.info("All components initialized successfully")
    yield

    logger.info("Retina-Scan-AI shutting down")
    _app_state.clear()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Retina-Scan-AI",
        description=(
            "Automated retinal disease detection and severity grading for clinical screening. "
            "Detects Diabetic Retinopathy, Glaucoma, AMD, and Cataracts from fundus images."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS — restrict to clinical portal origins in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8501", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(router, prefix="/api/v1")

    # HIPAA audit logging middleware
    @app.middleware("http")
    async def audit_log_middleware(request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        start_time = time.monotonic()

        # Attach request_id for downstream use
        request.state.request_id = request_id
        request.state.components = _app_state

        response = await call_next(request)
        elapsed_ms = (time.monotonic() - start_time) * 1000

        # HIPAA audit log — NO PII (no IP, no user agent details beyond method/path)
        logger.info(
            "api_request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(elapsed_ms, 2),
        )

        # Security headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Cache-Control"] = "no-store"

        return response

    @app.get("/health", tags=["system"])
    async def health_check() -> dict:
        """System health check endpoint."""
        return {
            "status": "healthy",
            "version": "0.1.0",
            "components": {
                "classifier": "ready" if "classifier" in _app_state else "not_initialized",
                "preprocessor": "ready" if "preprocessor" in _app_state else "not_initialized",
                "report_generator": "ready" if "report_generator" in _app_state else "not_initialized",
            },
        }

    @app.get("/", tags=["system"])
    async def root() -> dict:
        """Root endpoint with API information."""
        return {
            "name": "Retina-Scan-AI",
            "version": "0.1.0",
            "description": "Retinal disease detection AI for clinical screening",
            "docs": "/docs",
            "health": "/health",
        }

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            "unhandled_exception",
            request_id=request_id,
            error_type=type(exc).__name__,
            # Note: error message may be logged but NOT patient data
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "request_id": request_id,
                "message": "An unexpected error occurred. Please try again.",
            },
        )

    return app


app = create_app()
