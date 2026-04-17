# Model Change Control

## 1. Scope

This document describes the governance applied to any change in Retina Scan AI that materially affects model behaviour. It covers:

- Retraining on new data
- Hyperparameter changes
- Architecture changes
- Threshold calibration
- Changes to pre- or post-processing
- Changes to the class taxonomy

It does **not** cover:
- Bug fixes with no behavioural change (standard SDLC)
- Infrastructure changes (covered by hospital ITIL)
- Documentation-only changes

Change control aligns with:
- FDA *Marketing Submission Recommendations for a Predetermined Change Control Plan for AI-Enabled Device Software Functions* (Dec 2024)
- IEC 62304 § 6 (software maintenance process)
- ISO 13485 § 7.3.9 (design changes)

## 2. Change classification

Every proposed change is classified at the start of the change process into one of the following tiers.

### Tier A — Covered by PCCP (pre-approved)

Changes within scope of the Predetermined Change Control Plan as filed with the FDA (or equivalent in other jurisdictions). Examples:

- Retraining on additional labelled data from already-onboarded sites, architecture and class list held fixed
- Threshold calibration within defined bounds per site
- New camera model acceptance where the input distribution lies within the defined acceptance envelope

Tier A changes follow the **Modification Protocol** documented in the PCCP and are approved internally without new FDA submission.

### Tier B — Significant, requires re-submission

Changes outside the PCCP that alter intended use, performance, or risk profile. Examples:

- Adding a new disease class
- Removing a class
- Changing backbone architecture (e.g. ResNet18 → ViT)
- Extending indication to paediatric patients
- New modality (e.g. OCT input)
- Change in clinical decision supported

Tier B changes require a new 510(k) (or De Novo) submission and a new notified body assessment in the EU. Cannot proceed to production without clearance.

### Tier C — Emergency fix

Change required to mitigate active safety risk. Examples:

- Disabling a class that is producing unsafe output
- Raising a confidence threshold to suppress output below a safety floor

Tier C fixes bypass standard change control timelines but still require:
- Change Control Board (CCB) notification within 24 hours
- Full documentation within 7 days
- Retrospective validation within 30 days

## 3. Change lifecycle

```
Proposal ── Impact assessment ── Tier classification ── Planning
    │                                                      │
    │                                                      ▼
    │                                        ┌─── Tier A ────┐
    │                                        │                │
    │                                        ▼                │
    │                              Modification Protocol      │
    │                                        │                │
    │                                        ▼                │
    │                          Shadow deploy ─► A/B ─► Rollout
    │
    ├─── Tier B ──► Regulatory submission ──► Clearance ──► Rollout
    │
    └─── Tier C ──► CCB emergency approval ──► Rollout ──► Retrospective validation
```

## 4. Validation gates

Before any change reaches production, it passes the gates below. Passing criteria are pre-specified in the Modification Protocol.

### Gate 1 — Bench testing

- All existing regression tests pass
- Performance on held-out validation set meets or exceeds baseline on primary endpoints
- Fairness metrics on defined subgroups do not regress below thresholds
- Calibration (expected calibration error) within defined bounds

Primary endpoints for a diagnostic model:
- Per-class AUC (area under ROC)
- Sensitivity at specified specificity operating point
- Specificity at specified sensitivity operating point

Typical thresholds (illustrative):
- Per-class AUC ≥ 0.85
- Sensitivity at specificity = 0.90 ≥ 0.80 for referral-eligible classes (DR, AMD, glaucoma)
- Expected calibration error ≤ 0.05

### Gate 2 — Shadow deployment

- New model runs alongside current production model; outputs compared, differences logged
- Duration: minimum 30 days, minimum 5000 studies (site-dependent)
- No production routing to new model
- Review of disagreement cases by clinical-lead panel
- Drift metrics tracked

Pass criteria for Shadow:
- Disagreement rate with current production on top-1 class < 5%
- No cluster of disagreement concentrated in any single subgroup
- No unexplained latency regression
- No clinical review finding catastrophic disagreement (see §6 stopping rules)

### Gate 3 — A/B deployment

- New model routed to a fraction of incoming studies (e.g. 10%)
- Pre-registered statistical test with stopping rules
- Primary outcome: clinician disagreement rate
- Secondary outcome: time-to-read, overrride reason distribution
- Minimum exposure before any rollout decision: 2000 studies per arm
- Duration: maximum 90 days; stopping allowed earlier if stopping rule triggered

Pass criteria for A/B:
- Clinician disagreement rate in new model arm ≤ 1.2× control arm (pre-specified margin)
- No statistically significant safety signal
- No deterioration in time-to-read (> 10%)

### Gate 4 — Full rollout

- Monotonic ramp: 10% → 25% → 50% → 100% with minimum 7 days at each step
- Continuous drift monitoring (see `drift-monitoring.md`) checks each step
- Rollback plan executable within 15 minutes
- Sites notified of version change with release notes

## 5. Stopping rules for A/B

Pre-specified in the Modification Protocol. The trial is stopped immediately if any of:

- **Catastrophic disagreement**: Clinician rules model's top prediction as "frankly wrong" in ≥ 3 cases within the new-model arm within any 7-day window
- **Subgroup regression**: Any of the monitored subgroups (age band, sex, camera model) shows > 10% relative regression in AUC vs. baseline
- **Calibration drift**: Expected calibration error > 0.08
- **Confidence distribution shift**: KL divergence > pre-specified threshold
- **Clinical sponsor's discretion**: Qualitative concern raised and escalated

Stopping triggers a Tier C classification and an incident response (see `incident-response.md`).

## 6. Change Control Board (CCB)

Every material change requires CCB review. CCB membership:

| Role | Typical position |
|------|------------------|
| Clinical Lead | Senior ophthalmologist or radiologist |
| Regulatory Affairs | RA manager |
| Quality | Quality Assurance lead |
| Engineering Lead | ML or software engineering manager |
| Security | Information Security Officer |
| DPO | Data Protection Officer (for any change affecting data flow) |

Quorum: four members, must include Clinical and Regulatory.

## 7. Artefact set per change

Every change completes a change record containing:

- Change ID (UUID)
- Tier classification
- Rationale
- Impact assessment (clinical, regulatory, security, privacy, performance)
- Modification Protocol reference (if Tier A)
- Submission identifier (if Tier B)
- Validation results (gate by gate)
- Approval signatures (CCB quorum)
- Rollout plan
- Rollback plan
- Monitoring plan

Change records are retained per the audit retention policy.

## 8. Version identification

The model artefact is version-stamped:

| Component | Example |
|-----------|---------|
| Semantic version | 1.4.0 |
| Commit hash | `a1b2c3d4` |
| Training data snapshot ID | `odir5k-2025-q4` |
| Training run ID | `run-20250912-0930` |
| Tier classification of most recent change | A |

This identifier appears in:
- API `/health` endpoint
- Every audit log entry for inference
- GSPS ContentCreatorName
- Release notes

## 9. Interaction with drift monitoring

Drift monitoring provides the signal that triggers a change cycle. The typical sequence:

1. Drift monitor detects statistically significant degradation
2. Clinical-lead review determines whether intervention is warranted
3. If yes, a change proposal is filed; Tier is classified based on the intervention needed
4. Change proceeds through the above lifecycle

See [`drift-monitoring.md`](drift-monitoring.md).

## 10. External audit

Once a year, an external audit validates that:

- Change records are complete
- Approval signatures are from qualified, appointed persons
- Validation gates were actually executed (evidence checked)
- Modification Protocol was followed for Tier A changes
- Submissions were filed for Tier B changes before deployment

## 11. References

- FDA PCCP Guidance (Dec 2024 final)
- IEC 62304 § 6 Software Maintenance Process
- IEC 62304 § 5.8 Software Release Process
- ISO 13485 § 7.3.9 Control of Design and Development Changes
- Annex IV AI Act — post-market monitoring plan interaction
