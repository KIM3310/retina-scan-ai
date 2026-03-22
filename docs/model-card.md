# Retina-Scan-AI model card

## Intended use

Retina-Scan-AI is a **portfolio / engineering demonstration** of a retinal screening workflow. It shows how model inference, structured reporting, audit-aware APIs, and lightweight operational validation can fit together in a medical-AI-shaped service.

## Intended users

- AI engineers
- platform / MLOps reviewers
- hiring teams evaluating healthcare-oriented systems thinking

## Out of scope

- clinical diagnosis
- autonomous treatment decisions
- regulatory submission evidence
- patient-facing medical advice

## Model summary

- **Architecture:** ResNet18-style classifier surface
- **Runtime default:** `demo_heuristic`
- **Classes:** normal, diabetic_retinopathy, glaucoma, amd, cataracts
- **Input:** 224x224 RGB fundus image
- **Outputs:** class probabilities, severity estimate, risk score, structured report

## Evaluation stance

The repository includes **synthetic engineering-validation artifacts only**. These artifacts help reviewers inspect runtime quality gates and failure framing, but they are **not** substitutes for clinical validation.

## Key limitations

- Synthetic images are not representative of real clinical image distributions.
- Demo heuristics are useful for deterministic testing, not clinical performance claims.
- No sensitivity, specificity, AUROC, external validation, or subgroup safety claims are made.

## Operational safeguards in this repo

- opaque `study_id` usage instead of direct patient identifiers
- audit-aware request logging
- structured reporting with explicit disclaimers
- portfolio-safe release-readiness gates that avoid clinical-readiness claims

## Required next steps before any real-world discussion

1. Train and lock model weights on representative retinal datasets.
2. Perform held-out and external validation with documented dataset lineage.
3. Add threshold analysis, subgroup review, and post-deployment monitoring plans.
4. Complete regulatory, privacy, security, and clinical governance review.
