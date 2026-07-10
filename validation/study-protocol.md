# Study Protocol — Retina Scan AI Clinical Validation

**Protocol ID**: RETINA-VAL-2026-001 (draft; not IRB-approved)
**Version**: 0.3 (draft)
**Sponsor**: Research Software (example)
**Principal Investigator**: Site clinical lead (assigned before activation)
**Date**: 2026-04-17

> **Status**: This is a template document for a validation study. It has not been IRB-reviewed or approved. Before conducting any clinical study based on this protocol, obtain IRB approval, sponsor agreement, and site contracts.

## 1. Background and Rationale

Retinal disease screening is limited by specialist availability. Automated classification tools may expand screening capacity if they achieve sufficient diagnostic performance on real-world clinical populations. This study evaluates the Retina Scan AI model on prospectively-enrolled fundus images from multiple clinical sites to determine whether its performance meets predetermined thresholds for clinical utility.

## 2. Objectives

### Primary objective

To estimate the sensitivity (at specificity ≥ 0.90) of the Retina Scan AI model for detection of four retinal diseases (Diabetic Retinopathy, Glaucoma, Cataract, Age-related Macular Degeneration) in a multi-site prospective cohort.

### Secondary objectives

1. To estimate the per-class AUC.
2. To estimate agreement with a panel-adjudicated ground truth (Cohen's kappa).
3. To characterize performance differences across demographic subgroups (age, sex, ethnicity) and equipment (camera type).
4. To measure the additional clinician workload introduced by false positives.

## 3. Study Design

### 3.1 Type
Multi-site prospective diagnostic accuracy study with retrospective model inference.

### 3.2 Sites
Minimum 3 sites, representing at least 2 different geographic regions and 2 different camera manufacturers.

### 3.3 Population
**Inclusion criteria**:
- Adults ≥ 18 years old.
- Presenting for fundus imaging for any indication.
- Informed consent provided.

**Exclusion criteria**:
- Prior ophthalmic surgery within 90 days.
- Image quality below minimum acceptable standard (gradeability failure).
- Concurrent conditions out of scope (e.g., retinal detachment, endophthalmitis).

### 3.4 Sample size
See `sample-size-calculation.py`. Target: 2,000 eyes with disease prevalence between 15-25% per class.

### 3.5 Recruitment period
12 months or until target sample is reached.

## 4. Procedures

### 4.1 Fundus imaging

Standard of care: dilated fundus photography using site's existing equipment. No additional imaging required beyond routine care.

### 4.2 Ground truth adjudication

Each image is independently graded by 3 retina specialists using a standardized rubric. Graders are blinded to:
- Other graders' interpretations.
- Model predictions.
- Clinical context beyond demographics.

Disagreements are resolved by panel consensus in a meeting scheduled within 30 days.

### 4.3 Model inference

After ground truth is locked, images are run through the Retina Scan AI model. Model version (git SHA, weights hash) is recorded.

### 4.4 Data flow

```
Image captured → DICOM to local store → De-identification (DICOM PS3.15 Basic) →
    ↓
    ├→ Adjudicator panel (blinded) → Ground truth CSV
    ↓
    └→ Model inference (after ground truth locked) → Predictions CSV
    ↓
Merge → Analysis → Report
```

Neither the adjudicators nor the model see each other's output during grading or inference.

## 5. Statistical Analysis Plan

### 5.1 Primary analysis
Sensitivity is estimated at the model's operating threshold selected to achieve specificity ≥ 0.90 on a held-out reference set. 95% Wilson confidence interval reported.

**Decision rule**: pass if lower bound of 95% CI for sensitivity ≥ 0.85 for each disease class.

### 5.2 Secondary analyses
- Per-class ROC and AUC with 95% CI (DeLong method).
- Cohen's kappa between model and panel consensus.
- Subgroup sensitivity/specificity with Bonferroni-corrected between-group tests.

### 5.3 Missing data
Images that fail gradeability criteria are excluded from primary analysis; the rate is reported. Attempt all subgroup analyses on the same analysis set.

### 5.4 Interim analysis
One interim analysis after 50% enrollment to assess feasibility. No stopping rules except safety.

## 6. Ethical Considerations

### 6.1 Consent
Written informed consent obtained before participation. Consent form discloses:
- Images will be graded by specialists and analyzed by an experimental AI model.
- The model's predictions do not affect clinical care.
- Participation does not delay standard care.
- De-identified data may be used for future research.

### 6.2 Risk
Minimal risk. No additional imaging, no additional clinical procedures.

### 6.3 Privacy
De-identification per DICOM PS3.15 Basic Application Confidentiality Profile before any data leaves the site network.

### 6.4 IRB review
Required at each participating site. Central IRB acceptable where all sites agree.

## 7. Data Management

### 7.1 Capture
Per-subject CRF (see `case-report-form.md`). Data captured in a site-local REDCap or equivalent with standardized schema.

### 7.2 Transfer
Aggregated de-identified dataset transferred via SFTP / approved cloud bucket. Encryption in transit and at rest.

### 7.3 Retention
Per IRB and institutional policy, typically 7 years minimum. Long-term storage in compliance-grade repository.

### 7.4 Audit trail
All data modifications logged with timestamp and user. CRF revision history preserved.

## 8. Reporting

### 8.1 Primary report
Following CONSORT-AI 2020 reporting standard. Contents:
- Trial design and population.
- Per-class diagnostic accuracy.
- Subgroup performance.
- Adverse events (if any).
- Deviations from protocol.
- Model version and inference procedure details.

### 8.2 Publication
Target peer-reviewed journal within 6 months of study completion.

### 8.3 Data sharing
De-identified dataset available on request, subject to IRB and institutional review, for secondary research.

## 9. Deviations and Amendments

Protocol deviations are documented and reported to IRBs. Amendments require IRB approval and are versioned.

## 10. Timeline (indicative)

| Phase | Duration |
|-------|----------|
| Protocol finalization, IRB submission | Month 0-2 |
| Site activation | Month 2-3 |
| Enrollment | Month 3-15 |
| Ground truth adjudication | Month 3-16 |
| Model inference and analysis | Month 16-17 |
| Primary report drafting | Month 17-19 |
| Publication | Month 19-24 |

## 11. References

- CONSORT-AI 2020: Reporting guidelines for AI intervention trials.
- SPIRIT-AI 2020: Trial protocol standard for AI studies.
- FDA Guidance on CDSS (2022).
- DICOM PS3.15 Annex E: Basic Application Confidentiality Profile.
- STARD 2015: Standards for Reporting Diagnostic Accuracy Studies.
