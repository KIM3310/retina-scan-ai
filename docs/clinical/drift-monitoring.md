# Drift Monitoring

## 1. Overview

Model performance in production can degrade over time due to changes in:

- **Population drift** — the patient population being imaged differs from the training distribution (age, demographics, disease prevalence)
- **Data drift** — the images themselves differ (new camera models, firmware updates, illumination, acquisition protocols)
- **Label drift** — clinician labelling behaviour evolves (new grading guidelines, new clinicians with different thresholds)
- **Concept drift** — the underlying mapping from image to disease evolves (rare but possible with new clinical guidelines)
- **Calibration drift** — even when accuracy is stable, the confidence scores stop matching empirical frequencies

Drift monitoring is a required post-market obligation under:
- FDA PCCP (Real-World Performance Monitoring)
- EU MDR Article 83 (post-market surveillance)
- EU AI Act Article 72 (post-market monitoring)

## 2. Signals monitored

### 2.1 Input distribution drift

| Signal | Method | Alert threshold |
|--------|--------|----------------|
| Image intensity distribution | Kolmogorov-Smirnov per pixel-intensity histogram vs. rolling baseline | p < 0.001 with large effect |
| Image sharpness | Laplacian variance distribution | 2σ shift vs. baseline |
| Average luminance | Mean per channel | 3σ shift |
| Fraction of low-quality images | Rule-based + learned quality score | > 5 percentage point increase |
| Camera model distribution (from DICOM 0008,1090) | Categorical chi-squared | p < 0.01 |
| Patient age distribution (from 0010,1010) | KS test | p < 0.01 |
| Patient sex distribution (from 0010,0040) | Categorical chi-squared | p < 0.01 |
| Fraction of out-of-distribution images | Feature-space distance to training distribution (Mahalanobis on ResNet18 penultimate features) | > 10% OOD rate |

### 2.2 Output distribution drift

| Signal | Method | Alert threshold |
|--------|--------|----------------|
| Predicted class proportion | Per-class rate over rolling window | 2× absolute change or > 2σ vs. baseline |
| Calibration (expected calibration error) | ECE on prospectively-labelled subset | ECE > 0.05 |
| Prediction entropy | Mean entropy over rolling window | 2σ shift |
| High-confidence prediction rate | Fraction with calibrated confidence > 0.8 | 2σ shift |

### 2.3 Performance drift — ground-truth-requiring

Ground truth comes from two sources:
- **Primary**: the final clinician reading at report sign-off
- **Secondary**: a periodic labelled reference set read by a panel of ophthalmologists, quarterly

| Signal | Method | Alert threshold |
|--------|--------|----------------|
| Per-class sensitivity | Compared to validation-study baseline | > 5 percentage point drop |
| Per-class specificity | Compared to baseline | > 5 percentage point drop |
| Per-class AUC | Compared to baseline | > 0.03 drop |
| Clinician override rate | Compared to baseline | > 5 percentage point rise |
| Subgroup performance gap | Sensitivity gap across subgroups | > 10 percentage point gap |
| Time-to-read | Median minutes per study | > 10% rise |

### 2.4 Operational drift

| Signal | Method | Alert threshold |
|--------|--------|----------------|
| Inference latency p99 | Rolling | > 2× baseline |
| Inference failure rate | Rolling | > 0.1% |
| DICOM association reject rate | Rolling | > 1% |
| GSPS send failure rate | Rolling | > 0.5% |

## 3. Windows and baselines

| Monitor | Window | Baseline |
|---------|--------|----------|
| Input distribution | 7-day rolling | 90-day rolling prior period, or fixed validation baseline |
| Output distribution | 7-day rolling | Same |
| Performance (primary ground truth) | 30-day rolling | Validation study baseline |
| Performance (reference set) | Quarterly | Validation study baseline |
| Operational | 1-hour rolling | 7-day prior |

## 4. Alerting ladder

Each drift signal has a severity ladder. Severity maps to response.

| Severity | Criterion | Response |
|----------|-----------|----------|
| Informational | Within normal operating range | Logged only |
| Warning | Approaching threshold | Email to on-call; daily digest |
| Alert | Threshold crossed | Page on-call clinical-IT; review within 4 business hours |
| Critical | Threshold exceeded in way that implies patient safety | Page clinical-lead; invoke incident response |

## 5. Subgroup monitoring

Performance is stratified continuously by:
- Age band: < 40, 40–59, 60–74, ≥ 75
- Sex: Male, Female, Unknown/Other
- Camera model: per unique DICOM 0008,1090 value
- Site: deploying hospital or clinic identifier
- Prevalence conditions as available

Subgroup divergence triggers alert when:
- Any subgroup's sensitivity < 0.05 below overall
- Any subgroup's sensitivity drops > 10 percentage points while overall holds steady
- Any subgroup's false-negative rate exceeds a pre-specified clinical safety floor

## 6. Statistical method notes

- **Sample size awareness**: Many alerts are not meaningful below a minimum sample size per window. Minimum N per bucket is enforced; below N, only trend monitoring runs.
- **Multiple testing**: Given dozens of simultaneous tests, false positive alerts are likely. Alerts are triaged; sustained alerts across multiple windows or correlated signals are prioritised.
- **Baseline maintenance**: Validation-study baselines are anchored; rolling baselines drift as population evolves. Alerts reference both.
- **Seasonality**: Known seasonal patterns (e.g. diabetic screening campaigns in autumn) are accounted for with year-over-year comparison where applicable.

## 7. Dashboard and reporting

A drift dashboard surfaces, per site:

- Traffic light summary (green/amber/red) per monitor
- Trend chart (last 90 days) for each signal
- Subgroup heatmap
- Alerts in the last 30 days with status (new / reviewing / closed)

Quarterly PSUR (Periodic Safety Update Report) summarises drift findings for regulatory purposes.

## 8. Response procedures

### 8.1 Drift in input distribution

1. Confirm signal with additional data (larger window)
2. Inspect representative samples — camera change? acquisition protocol change? new population?
3. If new camera model — invoke camera acceptance protocol per PCCP (if in scope) or propose a change cycle (if out of scope)
4. If new population — inform clinical lead; evaluate whether intended use is violated
5. Document findings in quarterly PSUR

### 8.2 Drift in performance

1. Confirm signal with additional data and subgroup stratification
2. Hypothesise mechanism: data drift, label drift, concept drift
3. Run diagnostic analysis — where are errors concentrated?
4. If mitigation available via threshold adjustment, consider a Tier A PCCP change
5. If retraining needed, consider a Tier A change with new data
6. If root cause is outside PCCP scope, escalate to Tier B (new submission)
7. Document in change-control record

### 8.3 Subgroup degradation

1. Investigate whether subgroup sample size is sufficient for valid comparison
2. If valid: clinical lead reviews cases; decision on whether to pause routing for the subgroup, re-calibrate, or retrain
3. Fairness re-evaluation per [`../../governance/fairness-evaluation.md`](../../governance/fairness-evaluation.md)
4. Document decision

## 9. Relationship to incident response

Drift alerts are not incidents by default. An incident is invoked when:

- A drift signal is upgraded to Critical
- A cluster of overrides suggests patient-safety exposure
- A regulatory reporting obligation is triggered
- Clinical-lead judgement says so

See [`incident-response.md`](incident-response.md).

## 10. Data for drift monitoring

Drift monitoring operates on the same pseudonymised data as inference. No additional PHI collection is introduced for drift purposes. The monitoring stream is separated from operational logging and has restricted access.

## 11. Model vs. environment drift

A diagnostic question: is the problem the model or the environment?

| Observation | Likely cause | Response |
|-------------|-------------|----------|
| Stable input distribution, stable override rate, stable calibration, drop in sensitivity | Probably labelling or ground-truth shift | Investigate clinician panel calibration |
| Input intensity shift + performance drop | Data drift (camera, protocol) | Camera acceptance protocol |
| Stable inputs, performance drop, rising override rate | Concept drift or clinician trust issue | Clinical review; possibly retrain |
| Input OOD rate rising | New population or broken pipeline | Investigate upstream |

## 12. References

- FDA PCCP Dec 2024 — Real-World Performance Monitoring
- Ovadia et al. 2019, *Can You Trust Your Model's Uncertainty?*
- Rabanser, Günnemann, Lipton 2019, *Failing Loudly: An Empirical Study of Methods for Detecting Dataset Shift*
- Platt 1999, *Probabilistic Outputs for SVMs and Comparisons to Regularized Likelihood Methods* (calibration)
- Guo et al. 2017, *On Calibration of Modern Neural Networks*
