# Retina Scan AI

Retinal disease classification system using **ResNet18 transfer learning** with **Grad-CAM interpretability**. Classifies fundus images into 5 categories: Normal, Diabetic Retinopathy, Glaucoma, Cataract, and Age-related Macular Degeneration (AMD).

## Architecture

```
Input Image (224x224)
    │
    ▼
┌──────────────────────┐
│  ResNet18 Backbone    │  ← ImageNet pretrained weights
│  (Feature Extractor)  │
└──────────┬───────────┘
           │ 512-dim features
           ▼
┌──────────────────────┐
│  Classification Head  │
│  Dropout(0.3) →       │
│  Linear(512→256) →    │
│  ReLU → Dropout(0.2)  │
│  → Linear(256→5)      │
└──────────┬───────────┘
           │
           ▼
    5-class prediction
```

## Key Features

- **Transfer Learning**: ResNet18 pretrained on ImageNet, fine-tuned for retinal classification
- **Data Augmentation**: Random flip, rotation, color jitter, affine transforms
- **Training Pipeline**: Early stopping, LR scheduling, checkpointing, metric logging
- **Evaluation**: Confusion matrix, per-class precision/recall/F1, ROC-AUC curves
- **Grad-CAM**: Visual explanations showing which retinal regions drive each prediction
- **Inference API**: FastAPI REST endpoint for real-time classification
- **Docker**: Containerized training and serving

## Project Structure

```
retina-scan-ai/
├── src/
│   ├── config.py        # Hyperparameters and class labels
│   ├── dataset.py       # Custom dataset with augmentation pipeline
│   ├── model.py         # ResNet18 transfer learning architecture
│   ├── train.py         # Training loop with early stopping
│   ├── evaluate.py      # Confusion matrix, ROC curves, classification report
│   ├── gradcam.py       # Grad-CAM visualization for interpretability
│   └── inference.py     # Single-image prediction wrapper
├── api/
│   ├── main.py          # FastAPI inference server
│   └── schemas.py       # Request/response models
├── tests/
│   ├── test_model.py    # Model architecture tests
│   ├── test_dataset.py  # Dataset and transform tests
│   ├── test_train.py    # Training component tests
│   └── test_api.py      # API endpoint tests
├── scripts/
│   └── download_data.py # Dataset preparation utility
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── requirements.txt
```

## Quick Start

### Setup

```bash
pip install -r requirements.txt
```

### Prepare Dataset

```bash
# Option 1: Use ODIR-5K dataset from Kaggle
python scripts/download_data.py <csv_path> <images_dir>

# Option 2: Generate synthetic data for pipeline testing
python scripts/download_data.py --synthetic 100
```

Expected directory structure:
```
data/retina/
├── Normal/
├── Diabetic_Retinopathy/
├── Glaucoma/
├── Cataract/
└── AMD/
```

### Train

```bash
python -m src.train
```

Outputs:
- `checkpoints/best_model.pth` — Best model weights
- `outputs/training_history.json` — Epoch-level metrics

### Evaluate

```bash
python -m src.evaluate checkpoints/best_model.pth
```

Outputs:
- `outputs/confusion_matrix.png` — Confusion matrix heatmap
- `outputs/roc_curves.png` — Per-class ROC curves with AUC
- `outputs/evaluation_results.json` — Full metrics report

### Grad-CAM Visualization

```bash
python -m src.gradcam <image_path> checkpoints/best_model.pth
```

### Inference API

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000

# Predict
curl -X POST http://localhost:8000/predict -F "file=@retina_image.jpg"

# Grad-CAM
curl -X POST http://localhost:8000/gradcam -F "file=@retina_image.jpg" -o gradcam.png
```

### Docker

```bash
# Inference server
docker compose up api

# Training
docker compose --profile training run train
```

### Tests

```bash
pytest -v
```

## Dataset

Designed for the [ODIR-5K](https://www.kaggle.com/datasets/andrewmvd/ocular-disease-recognition-odir5k) (Ocular Disease Intelligent Recognition) dataset containing 5,000 retinal fundus photographs across 8 disease categories, filtered to 5 primary classes.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Deep Learning | PyTorch, torchvision |
| Model | ResNet18 (transfer learning) |
| Interpretability | Grad-CAM |
| Evaluation | scikit-learn, matplotlib, seaborn |
| API | FastAPI, Uvicorn |
| Container | Docker, Docker Compose |
| Testing | pytest |
| DICOM | pydicom, pynetdicom (via `dicom/`) |
| Identity Federation | OIDC (Keycloak/Okta/Azure AD via `access/`) |
| Audit | Hash-chained event log (via `audit/`) |

## Not a Medical Device

This repository is research code. It has not been FDA-cleared, CE-marked, or approved by any regulatory body for clinical use. Any deployment for clinical care requires regulatory clearance, IRB review, and integration with a quality management system. See `compliance/fda-samd-considerations.md` and `risk/known-limitations.md` for details.

## Compliance & Governance

This service includes compliance and governance artifacts that align with typical healthcare-AI deployment requirements. Refer to the relevant directory for details.

| Area | Directory | Notes |
|------|-----------|-------|
| HIPAA | `compliance/hipaa-mapping.md` | Each Security Rule safeguard → this repo's approach |
| FDA SaMD | `compliance/fda-samd-considerations.md` | Educational framing; not legal advice |
| EU MDR | `compliance/mdr-ce-considerations.md` | CE marking considerations |
| GDPR | `compliance/gdpr-dpia.md` | DPIA template |
| PHI handling | `compliance/phi-handling.md` | Storage, transmission, anonymization |
| Model card | `governance/model-card.md` | Google-style Model Card |
| Datasheet | `governance/datasheet.md` | Gebru-style Datasheet for ODIR-5K |
| Fairness | `governance/fairness-evaluation.md` | Per-subgroup metrics, disparity detection |
| Explainability | `governance/explainability-design.md` | Grad-CAM rationale and limits |
| Biases and limits | `governance/bias-and-limitations.md` | Documented biases, unsupported populations |

## Clinical Integration

`docs/clinical/` documents how the service integrates with hospital workflows:

- [deployment-architecture.md](docs/clinical/deployment-architecture.md) — DMZ placement, OIDC federation, DICOM routing.
- [dicom-integration.md](docs/clinical/dicom-integration.md) — PACS C-STORE SCP, anonymization, GSPS overlays.
- [clinician-in-the-loop.md](docs/clinical/clinician-in-the-loop.md) — Second-reader / triage UX; disagreement handling.
- [change-control.md](docs/clinical/change-control.md) — Model retraining governance.
- [drift-monitoring.md](docs/clinical/drift-monitoring.md) — Input distribution, calibration, population drift.
- [incident-response.md](docs/clinical/incident-response.md) — Clinical workflow fallback, recall procedure.

`dicom/` has the DICOM integration code (C-STORE SCP listener, anonymizer, GSPS generator, audit logger).

`access/` has the RBAC + OIDC layer with clinical roles (Radiologist, Ophthalmologist, etc.).

`audit/` has the HIPAA-aligned hash-chained audit logger and compliance officer search tooling.

`clinical_ui/` has a static HTML mockup of the clinician triage view.

## Validation

`validation/` contains templates for running a multi-site clinical validation study:

- [study-protocol.md](validation/study-protocol.md) — Protocol following CONSORT-AI / SPIRIT-AI standards.
- [sample-size-calculation.py](validation/sample-size-calculation.py) — Runnable sample size calculator.
- [case-report-form.md](validation/case-report-form.md) — Per-subject CRF template.
- [results-template.json](validation/results-template.json) — JSON schema of the validation-study output.

## Risk Management

`risk/` follows ISO 14971:2019:

- [fmea.md](risk/fmea.md) — Failure Mode and Effects Analysis (20 items).
- [iso14971-mapping.md](risk/iso14971-mapping.md) — Clause-by-clause coverage of ISO 14971.
- [known-limitations.md](risk/known-limitations.md) — Cataloged constraints and edge cases.

## Related Projects

| Project | Relationship |
|---------|-------------|
| [weld-defect-vision](https://github.com/KIM3310/weld-defect-vision) | Sibling vision project — industrial defect detection with YOLOv8 |
| [enterprise-llm-adoption-kit](https://github.com/KIM3310/enterprise-llm-adoption-kit) | Shared governance patterns (RBAC, audit, RAG) |
| [AegisOps](https://github.com/KIM3310/AegisOps) | Operator handoff and incident analysis — clinical incident-response patterns |
