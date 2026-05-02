# Technical Review Pack

## System Boundary

This repository models a retinal-image classification workflow with interpretability, validation templates, access controls, audit logging, and risk documentation. It is not a clinical decision system; it is a technical pipeline with explicit limitations and governance artifacts.

## Architecture Notes

```mermaid
flowchart LR
    Image["Fundus image"] --> Preprocess["Dataset and transforms"]
    Preprocess --> Model["Classifier"]
    Model --> Explain["Grad-CAM explainability"]
    Explain --> API["Inference API"]
    API --> Audit["Audit and access controls"]
    Audit --> Validation["Validation templates"]
```

The repository separates model behavior from governance and validation notes so risk controls can be reviewed without running a training job.

## Demo Path

```bash
pytest -q
uvicorn api.main:app --reload
```

Useful entry points:

- `src/model.py`
- `src/gradcam.py`
- `api/main.py`
- `governance/model-card.md`
- `risk/iso14971-mapping.md`
- `validation/study-protocol.md`

## Validation Evidence

- Tests cover model construction, dataset behavior, training components, and API schemas.
- Governance notes cover limitations, explainability, fairness, and data handling.
- Risk and validation directories keep operational claims bounded.

## Threat Model

| Risk | Control |
|---|---|
| Overstated medical claim | explicit limitations and validation templates |
| Data sensitivity | DICOM anonymization and PHI handling notes |
| Unexplainable prediction | Grad-CAM workflow and explainability design |
| Access misuse | role and audit modules |

## Maintenance Notes

- Keep clinical wording conservative and evidence-bound.
- Do not treat sample outputs as clinical validation.
- Add tests before changing class labels or API schema.
- Keep anonymization behavior separate from model inference.
