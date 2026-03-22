# Validation plan

## Goal

Provide a reviewable **engineering validation plan** for Retina-Scan-AI without overstating clinical evidence.

## Current validation tier

`engineering_synthetic`

The current repository validates:

- deterministic preprocessing behavior
- route contract stability
- synthetic disease classification behavior
- structured report generation
- operational documentation presence

## Current gaps

- no real-world training or evaluation dataset is bundled
- no external validation
- no subgroup analysis
- no clinically derived operating threshold study
- no prospective workflow study

## Recommended validation ladder

1. **Engineering validation**
   - keep deterministic synthetic suite
   - verify schema contracts, latency, and monitoring surfaces
2. **Offline model validation**
   - held-out retinal dataset
   - confusion matrix, sensitivity, specificity, AUROC
   - threshold trade-off analysis
3. **Robustness validation**
   - image quality stress cases
   - device/site shift checks
   - subgroup and fairness review
4. **Clinical / regulatory validation**
   - governed study protocol
   - documented intended use
   - post-market monitoring plan

## Repo policy

Until steps 2-4 exist, all evaluation language in this repository should remain framed as:

> engineering validation / portfolio demonstration

and not:

> clinically validated diagnostic system
