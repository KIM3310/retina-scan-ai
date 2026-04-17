# Failure Mode and Effects Analysis (FMEA)

| # | Subsystem | Failure Mode | Cause | Effect | Severity (1-5) | Occurrence (1-5) | Detectability (1-5) | RPN | Mitigation | Residual RPN |
|---|-----------|--------------|-------|--------|----------------|------------------|---------------------|-----|-----------|--------------|
| 1 | Image preprocessing | Out-of-distribution image accepted (not fundus) | Missing gradeability check | False prediction, potential misdirection | 4 | 3 | 3 | 36 | Pre-inference gradeability classifier rejects non-fundus images with <0.60 confidence. Unit test covers 100 known non-fundus samples. | 8 |
| 2 | Model inference | False negative on Class-2+ Diabetic Retinopathy | Training data imbalance, subtle lesion | Delayed diagnosis, progressive vision loss | 5 | 3 | 2 | 30 | Second-reader workflow recommended for all DR-positive and DR-borderline predictions. Specificity held high to keep FN rate acceptable. Drift monitoring on sensitivity. | 10 |
| 3 | Model inference | False positive on Normal cases | Over-calling lesions | Unnecessary clinician review, anxiety | 2 | 3 | 3 | 18 | Operating threshold tuned for specificity ≥ 0.90. FP burden tracked in validation study. | 6 |
| 4 | Model inference | Subgroup performance gap (ethnicity, camera) | Training data not representative | Unequal diagnostic quality | 4 | 4 | 3 | 48 | Fairness audit in validation study with gap flag at >10pp. Model not deployed for subgroups where gap exceeds threshold. | 12 |
| 5 | Grad-CAM generation | Explanation misleading (attends to artifact) | Grad-CAM is approximate, can anchor on non-clinical features | Clinician misguided by explanation | 3 | 3 | 4 | 36 | Grad-CAM is opt-in (not always visible). UI disclaimer explains Grad-CAM limits. Physicians trained on Grad-CAM interpretation. | 12 |
| 6 | Authentication | Unauthorized access | Stolen session token, MFA bypass | PHI disclosure | 5 | 1 | 3 | 15 | OIDC federated auth, MFA required for all writes, session TTL 8h, anomaly detection on IP/UA changes. | 5 |
| 7 | Authentication | Break-glass misused | Clinician uses break-glass for convenience, not emergency | Inappropriate access to non-assigned patient records | 3 | 2 | 2 | 12 | Break-glass requires typed reason; compliance officer reviews all break-glass events within 72 hours; disciplinary policy enforced. | 6 |
| 8 | DICOM ingestion | PHI leakage via DICOM tags | Incomplete anonymization | Privacy breach | 5 | 2 | 3 | 30 | DICOM PS3.15 Basic Profile anonymization; re-verification after each DICOM schema update; quarterly penetration test of anonymizer. | 10 |
| 9 | Audit logging | Audit log tampering | Privileged user or attacker modifies audit records | Loss of compliance posture | 5 | 1 | 2 | 10 | Hash-chained audit log; append-only storage with Object Lock; quarterly chain verification; privileged mutate access eliminated. | 4 |
| 10 | Data retention | Audit records deleted early | Retention policy misconfiguration | HIPAA violation | 5 | 1 | 3 | 15 | Compliance-officer-approved purge only; legal hold freeze; 7-year retention policy documented. | 5 |
| 11 | Model drift | Silent performance degradation | Population shift, camera change | Increased errors over time | 4 | 4 | 3 | 48 | Drift monitoring dashboard (see docs/clinical/drift-monitoring.md); quarterly re-evaluation; alerting on confidence distribution shift. | 16 |
| 12 | Model version mismatch | Inference uses wrong model version | Deployment bug, rollback not propagated | Inconsistent predictions across clinicians | 3 | 2 | 2 | 12 | Model version captured in every inference record; version-pinned in config; deployment verification in smoke test. | 6 |
| 13 | Infrastructure | Service outage during urgent clinical use | Cloud provider issue, DoS, software bug | Delayed care | 3 | 3 | 2 | 18 | HA deployment with multi-AZ; graceful degradation to manual workflow with UI guidance; incident response runbook. | 9 |
| 14 | Clinical UI | Workflow confusion leading to wrong action | Poor UX, ambiguous button | Wrong decision recorded | 3 | 3 | 3 | 27 | Usability study (IEC 62366-1); confirm dialog on destructive actions; undo for non-destructive actions. | 9 |
| 15 | Training | Dataset contamination | Test data leaked into training | Overstated performance | 5 | 2 | 4 | 40 | Strict train/val/test split by patient ID; hash-based leakage check; external holdout set for final validation. | 10 |
| 16 | Model inference | Adversarial inputs cause misclassification | Deliberate attack on model | Incorrect diagnosis | 4 | 1 | 3 | 12 | Input normalization range checks; reject inputs outside expected pixel distribution; research on adversarial robustness tracked but not primary mitigation. | 8 |
| 17 | Governance | Bias-disparate treatment of disability status | Model trained on predominantly non-disabled population | Unequal diagnostic quality for disabled patients | 4 | 3 | 4 | 48 | Subgroup monitoring extended to include disability status where recorded. Bias audit quarterly. | 16 |
| 18 | Physician-in-the-loop | Automation bias (over-reliance on model) | Clinician accepts model without independent read | Missed clinical findings | 4 | 4 | 4 | 64 | Grad-CAM opt-in (not always visible); training materials emphasize "second reader, not first reader"; agreement rate monitored for anomalies. | 20 |
| 19 | Data pipeline | Scheduled retraining uses contaminated production data | PHI or incorrect-consent data flows into training | Model trained on data it shouldn't be | 5 | 2 | 3 | 30 | Retraining pipeline consumes only explicitly-consented de-identified data; consent-withdrawal propagation to training store. | 10 |
| 20 | Clinical integration | Incorrect patient ID linkage | HL7/FHIR mapping bug | Results attributed to wrong patient | 5 | 2 | 2 | 20 | Patient ID matching requires match on 2+ fields (ID + DOB); mismatch triggers alert; pre-production test on synthetic crossed-ID cases. | 8 |

## Scoring key

**Severity**: 1 (negligible) → 5 (catastrophic: death, irreversible severe harm).  
**Occurrence**: 1 (improbable) → 5 (frequent).  
**Detectability**: 1 (detected immediately) → 5 (undetectable until harm occurs). Lower is better.

**RPN** = severity × occurrence × detectability.

## Prioritization

Items with residual RPN > 15 are re-reviewed annually. The top three (rows 18, 17, 11, 4) receive quarterly attention in the risk review meeting.

## Change log

- v0.1 (2026-04-17): Initial FMEA. To be reviewed and validated by the risk management team and clinical advisor.
