# Retina-Scan-AI

**Automated retinal disease detection system for clinical screening**

A production-quality computer vision system for detecting and grading retinal diseases from fundus photographs, designed for integration into ophthalmology clinical workflows.

---

## Overview

Retina-Scan-AI is a CNN-based retinal screening platform built with healthcare AI best practices. It classifies fundus images across five categories, grades disease severity using ETDRS-aligned criteria, computes patient risk scores, and generates structured clinical reports — all through a FastAPI backend and Streamlit clinician dashboard.

This project was developed to demonstrate applied AI engineering in the medical imaging domain, with specific relevance to **Johnson & Johnson Vision**'s mission of advancing eye care technology through innovation in diagnostics and clinical decision support.

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
└── tests/                         # 100+ pytest tests
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

## J&J Vision Alignment

This project is directly relevant to Johnson & Johnson Vision's mission in several ways:

- **VERITAS platform alignment**: Demonstrates the kind of AI-assisted diagnostic tools J&J Vision deploys in clinical practice
- **Diabetic retinopathy screening**: DR is a leading cause of blindness and a core focus area for J&J Vision's retinal imaging programs
- **Clinical workflow integration**: FastAPI backend + Streamlit dashboard mirrors the architecture needed for real-world EHR integration
- **HIPAA-aware engineering**: Healthcare AI requires privacy-by-design; this codebase demonstrates that discipline from day one
- **Explainability**: Severity grading with ETDRS levels and structured clinical narratives supports clinician trust and regulatory review

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

---

## License

MIT License — for research and educational purposes.
Not FDA-cleared. Not for clinical diagnostic use without appropriate regulatory approval.
