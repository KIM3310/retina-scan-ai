# ISO 14971:2019 Mapping

How the risk management artifacts in this repository map to the clauses of ISO 14971:2019.

> Disclaimer: This mapping is educational. Claiming ISO 14971 compliance requires a formal quality management system (ISO 13485), regulator engagement (FDA 510(k) or CE marking), and a full risk management file. This document shows the *shape* of that mapping.

## Clause 4 — General Requirements

### 4.1 Risk management process
**This repo**: `risk/README.md` describes the process. `risk/fmea.md` is the primary risk inventory. Per-clause evidence listed below.

### 4.2 Management responsibilities
**This repo**: risk management team composition documented in `risk/README.md`. Review cadence quarterly.

### 4.3 Competence of personnel
**This repo**: not applicable at prototype stage. Production requires documented competency records.

### 4.4 Risk management plan
**This repo**: inventoried items, acceptance criteria, review process in `risk/README.md` and `risk/fmea.md`. A formal RMP would be a separate controlled document under a QMS.

### 4.5 Risk management file (RMF)
**This repo**: the `risk/` directory is the beginning of an RMF. Production requires tracking every change with revision control and review approval.

## Clause 5 — Risk Analysis

### 5.1 Risk analysis process
**This repo**: FMEA is the primary analysis technique (`risk/fmea.md`). Supplementary analyses (hazard tree, STPA) should be added for production.

### 5.2 Intended use and characteristics related to safety
**This repo**: `governance/model-card.md` (intended use, indications, contraindications), `compliance/fda-samd-considerations.md` (regulatory classification context).

### 5.3 Identification of hazards
**This repo**: 20 hazards identified in `risk/fmea.md`. Categories covered:
- Image quality / OOD input.
- Model errors (FN, FP, subgroup disparities).
- Cybersecurity (unauthorized access, token theft).
- Privacy (PHI disclosure, audit tampering).
- Model lifecycle (drift, version mismatch, contamination).
- Clinical workflow (automation bias, UI confusion).
- Infrastructure (outage).
- Governance (disability-status bias, consent propagation).
- Integration (patient ID linkage).

### 5.4 Estimation of risks
**This repo**: severity, occurrence, detectability on 1-5 scales. RPN computed. Acceptance matrix in `risk/README.md`.

### 5.5 Risk evaluation
**This repo**: acceptability determined against matrix in `risk/README.md`.

## Clause 6 — Risk Control

### 6.1 Risk control option analysis
**This repo**: ISO 14971 specifies the hierarchy: (a) inherent safety by design, (b) protective measures, (c) information for safety. FMEA mitigations use all three, documented per row.

### 6.2 Implementation of risk control measures
**This repo**: every mitigation maps to a code path, configuration, test, or documented operational procedure:
- Gradeability check → `src/dataset.py` (referenced in future work).
- Drift monitoring → `docs/clinical/drift-monitoring.md` + `audit/search_tools.py`.
- OIDC + MFA → `access/oidc_integration.py`, `access/mfa-policy.md`.
- Audit log integrity → `audit/logger.py` hash chain, `audit/search_tools.py verify-chain`.
- Break-glass review → `access/mfa-policy.md` post-hoc review.
- Fairness audit → `validation/study-protocol.md` subgroup analysis plan.

### 6.3 Residual risk evaluation
**This repo**: residual RPN computed after mitigation in `risk/fmea.md`. All items meet acceptance criteria post-mitigation.

### 6.4 Benefit-risk analysis
**This repo**: not addressed explicitly at prototype stage. Production would include a clinical benefit-risk memorandum referencing validation-study outcomes.

### 6.5 Risks arising from risk control measures
**This repo**: evaluated in FMEA. Example: opt-in Grad-CAM (mitigation for automation bias) could delay clinical decision in emergency — residual risk acceptable given break-glass + optionality.

### 6.6 Completeness of risk control
**This repo**: 20 items in FMEA with residual RPN computed. Periodic review captures new risks.

## Clause 7 — Evaluation of Overall Residual Risk

**This repo**: aggregate residual risk assessment is a management review artifact, not part of this repo. Production would include a statement signed by the risk management team.

## Clause 8 — Risk Management Review

**This repo**: quarterly review cadence in `risk/README.md`. Records of reviews are a separate controlled document.

## Clause 9 — Production and Post-production Activities

### 9.1 Establish and maintain production and post-production activities
**This repo**:
- `docs/clinical/drift-monitoring.md` — production monitoring.
- `audit/` — ongoing audit capture.
- `docs/clinical/incident-response.md` — incident handling.

### 9.2 Information collection
**This repo**: incident tracking, audit analytics, drift metrics. A real QMS would add customer-feedback channels, regulatory reports, and external post-market safety signals.

### 9.3 Information review
**This repo**: implied via quarterly risk review. Production requires documented decision records.

### 9.4 Actions
**This repo**: implicit. Production requires a change-control process (IEC 62304 §8).

## Coverage summary

| Clause | Coverage | Gap for production |
|--------|----------|---------------------|
| 4.1 – 4.5 Process | Partial | Need formal RMP document, QMS integration |
| 5.1 – 5.5 Analysis | Good | Supplementary techniques (STPA) recommended for production |
| 6.1 – 6.6 Control | Good | Need explicit benefit-risk memo |
| 7 Overall residual | Partial | Need management review signoff |
| 8 Management review | Partial | Need meeting records, signoffs |
| 9.1 – 9.4 Post-market | Partial | Need customer feedback channels, regulatory reporting links |

## What this mapping does NOT cover

- Cybersecurity-specific process per IEC 81001-5-1 / FDA Premarket Cybersecurity Guidance.
- Software life cycle per IEC 62304.
- Usability engineering per IEC 62366-1.
- Clinical evaluation per ISO 14155.

Those are adjacent frameworks; a production device needs them in addition.
