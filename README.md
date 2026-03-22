# Retina-Scan-AI

**Automated retinal disease detection system for clinical screening**

A production-style computer vision system for detecting and grading retinal diseases from fundus photographs, designed to demonstrate how ophthalmology AI workflows can be packaged into reviewable backend, reporting, and operational surfaces.

---

## Overview

Retina-Scan-AI is a CNN-based retinal screening platform built with healthcare AI engineering practices. It classifies fundus images across five categories, grades disease severity using ETDRS-aligned criteria, computes patient risk scores, and generates structured clinical reports — all through a FastAPI backend and Streamlit clinician dashboard.

This repository now also includes lightweight **medical AI operations / validation / MLOps** surfaces:

- synthetic engineering-validation artifacts
- runtime monitoring for latency and image-quality drift signals
- portfolio-safe release readiness gates
- model card, risk register, and validation plan docs

> **Important:** the evaluation artifacts in this repo are for **engineering review only**. They are **not clinical validation claims** and should not be interpreted as regulatory or diagnostic evidence.

---

## Supported Conditions

| Disease | ICD-10 | Severity Scale |
|---|---|---|
| Normal | Z01.01 | — |
| Diabetic Retinopathy | E11.319 | Mild NPDR → Moderate NPDR → Severe NPDR → PDR (ETDRS-aligned) |
| Glaucoma | H40.10X0 | Mild → Moderate → Severe → Advanced |
| Age-related Macular Degeneration | H35.30 | Early → Intermediate → Late → Advanced |
| Cataracts | H26.9 | Incipient → Moderate → Dense |

---

## Architecture

```
retina-scan-ai/
├── app/
│   ├── main.py                    # FastAPI application with HIPAA audit logging
│   ├── monitoring/
│   │   └── runtime.py             # Runtime monitoring + release-readiness helpers
│   ├── models/
│   │   ├── classifier.py          # ResNet18-based disease classifier (demo + production modes)
│   │   ├── severity.py            # ETDRS-aligned severity grading
│   │   └── risk_scoring.py        # Composite patient risk score computation
│   ├── preprocessing/
│   │   └── pipeline.py            # CLAHE, vessel enhancement, FOV masking
│   ├── reporting/
│   │   └── clinical_report.py     # Structured clinical report generation
│   └── api/
│       └── routes.py              # REST API endpoints
├── dashboard/
│   └── app.py                     # Streamlit clinician review dashboard
├── docs/
│   ├── model-card.md              # Intended use, limitations, safeguards
│   ├── validation-plan.md         # Engineering validation ladder + gaps
│   ├── risk-register.md           # Medical-AI-specific risk framing
│   └── deployment.md              # Production-style deployment notes
├── evals/
│   ├── generate_validation_artifacts.py  # Synthetic engineering-validation builder
│   └── artifacts/                 # Generated JSON/Markdown validation summaries
├── .github/workflows/
│   └── ci.yml                     # Lint + compile + tests + artifact generation
└── tests/                         # pytest suite including ops/validation surfaces
```

### Model Architecture

- **Backbone**: ResNet18 (ImageNet pretrained weights for transfer learning)
- **Head**: Dropout(0.3) → Linear(512→256) → ReLU → Linear(256→5)
- **Classes**: Normal, Diabetic Retinopathy, Glaucoma, AMD, Cataracts
- **Input**: 224×224 RGB, normalized to ImageNet statistics
- **Demo mode**: Rule-based heuristics on synthetic images for testing without GPU/weights

### Preprocessing Pipeline

1. Green channel enhancement (sharpened via unsharp mask — vessels most visible in green)
2. CLAHE in LAB color space (clip limit 2.0, 8×8 tile grid)
3. Circular FOV masking (removes non-retinal border)
4. Resize to 224×224 (Lanczos interpolation)
5. Image quality assessment (exposure, contrast, sharpness scoring)

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | System health check |
| GET | `/api/v1/diseases` | List supported diseases + ICD-10 codes |
| GET | `/api/v1/model/info` | Model architecture metadata |
| POST | `/api/v1/classify` | Classification only |
| POST | `/api/v1/analyze` | Full pipeline (classify + grade + risk + report) |
| GET | `/api/v1/ops/validation-summary` | Synthetic engineering-validation artifact |
| GET | `/api/v1/ops/monitoring` | Runtime monitoring snapshot |
| GET | `/api/v1/ops/release-readiness` | Portfolio-safe readiness gates |

### Example: Full Analysis

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "file=@fundus.jpg" \
  -F "study_id=STUDY-001" \
  -F "patient_age=65" \
  -F "hba1c=8.5" \
  -F "has_hypertension=true"
```

Response includes:
- Disease classification with confidence and ICD-10 code
- ETDRS-aligned severity grading with clinical description
- Composite risk score with contributing factors
- Full clinical report with findings narrative and recommendations

---

## HIPAA-Aware Design

- **No PII stored**: Only opaque `study_id` references; no patient names, DOB, or MRN
- **Audit logging**: All API requests logged with `request_id`, method, path, status, duration — no patient data
- **Security headers**: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, `Cache-Control: no-store`
- **Structured logging**: JSON-formatted logs via `structlog` for SIEM integration
- **Access control**: CORS restricted to clinical portal origins

---

## Quick Start

```bash
# Create virtual environment and install dependencies
make install

# Run tests
make test

# Start FastAPI backend (http://localhost:8000)
make run-api

# Start Streamlit dashboard (http://localhost:8501)
make run-dashboard

# Lint check
make lint

# Generate engineering-validation artifacts
make eval

# Runtime smoke
make smoke

# Full verification
make verify
```

---

## Testing

```bash
# Run full test suite
make test

# With coverage report
make test-cov
```

Test suite includes 100+ tests covering:
- Heuristic classifier correctness for all 5 synthetic disease categories
- Preprocessing pipeline (CLAHE, vessel enhancement, FOV masking, quality detection)
- Severity grading (DR ETDRS levels, glaucoma CDR, AMD drusen, cataract opacity)
- Risk score computation (metadata boosting, score bounds, recommendations)
- Clinical report generation (findings narrative, clinical impression, to_text/to_dict)
- FastAPI endpoints (all routes, error handling, security headers)
- Production quality (HIPAA compliance, data integrity, end-to-end pipeline)

## Engineering validation & MLOps surfaces

This repository includes a lightweight operations layer intended for **medical AI engineering review**:

- `GET /api/v1/ops/validation-summary`
  - exposes the bundled synthetic/offline evaluation artifact
- `GET /api/v1/ops/monitoring`
  - summarizes runtime latency, image quality signals, and documentation presence
- `GET /api/v1/ops/release-readiness`
  - reports **portfolio review readiness**, not clinical or regulatory readiness
- `docs/model-card.md`
  - intended use, out-of-scope boundaries, and limitations
- `docs/validation-plan.md`
  - what has and has not been validated
- `evals/generate_validation_artifacts.py`
  - regenerates JSON / Markdown engineering-validation artifacts

### Validation framing

- **Current tier:** engineering / synthetic validation
- **Not claimed:** sensitivity, specificity, AUROC, external validation, prospective study results
- **Current runtime default:** `demo_heuristic`

This framing is deliberate so the repository stays useful for healthcare AI engineering discussion without overstating medical evidence.

### Reviewer fast path

1. `GET /health` — verify service boot and proof routes
2. `GET /api/v1/ops/validation-summary` — inspect the bundled engineering artifact
3. `GET /api/v1/ops/monitoring` — confirm runtime / image-quality snapshot
4. `GET /api/v1/ops/release-readiness` — read the portfolio-safe release gate

The same path is now exposed directly from `/` and `/health`, so a reviewer can discover the strongest proof route without reading the repo first.

---

## Severity Grading: Diabetic Retinopathy

Aligned with the **ETDRS (Early Treatment Diabetic Retinopathy Study)** severity scale:

| Level | ETDRS | Description |
|---|---|---|
| Mild NPDR | 20 | Microaneurysms only |
| Moderate NPDR | 43 | Dot-blot hemorrhages, hard exudates |
| Severe NPDR | 53 | 4-2-1 rule: extensive hemorrhages, venous beading, IRMA |
| PDR | 71 | Neovascularization (NVD/NVE), vitreous hemorrhage |

---

## Healthcare AI engineering alignment

This project is relevant to healthcare / MedTech AI engineering roles because it demonstrates:

- **Ophthalmology workflow modeling**: fundus-image classification, severity grading, risk scoring, and structured reporting
- **Operational framing**: runtime monitoring, synthetic validation artifacts, and release-readiness gates
- **Privacy-aware backend design**: opaque identifiers, audit-style logs, and security headers
- **Clinical communication surfaces**: structured reports, explainability metadata, and explicit disclaimers
- **Interview-ready engineering maturity**: CI, tests, documentation, and a clear statement of what is **not** clinically validated

---

## Technology Stack

- **Python 3.12** with full type annotations
- **PyTorch / torchvision** — ResNet18 transfer learning
- **OpenCV** — CLAHE, vessel enhancement, FOV masking
- **Pillow** — Image I/O and format handling
- **FastAPI** — Async REST API with Pydantic v2 validation
- **Streamlit** — Clinician dashboard
- **structlog** — Structured JSON audit logging
- **pytest** — 100+ tests with fixtures and parametrize
- **ruff** — Linting and formatting
- **GitHub Actions** — CI verification

---

## License

MIT License — for research and educational purposes.
Not FDA-cleared. Not for clinical diagnostic use without appropriate regulatory approval.
