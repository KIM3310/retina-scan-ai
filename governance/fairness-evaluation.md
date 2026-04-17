# Fairness Evaluation

> Numbers below are **illustrative** for the reference training pipeline on the ODIR-5K 5-class task. An actual deployment must produce its own fairness evaluation on a representative deployment cohort.

## 1. Position

Fairness in medical AI is not a single metric. Different fairness criteria (demographic parity, equal opportunity, equalised odds, predictive parity) can be incompatible, and choosing among them is a normative decision that belongs with the clinical sponsor, not the model. This evaluation reports multiple criteria so that the clinical sponsor can make an informed choice.

Anchor text on the trade-offs: Kleinberg, Mullainathan, Raghavan (2017); Chouldechova (2017); Mitchell et al. (2018).

## 2. Framework

We report per-subgroup performance along three complementary criteria:

| Criterion | Definition |
|-----------|------------|
| Equal opportunity | TPR equal across groups (same sensitivity for true positives) |
| Equalised odds | Both TPR and FPR equal across groups |
| Predictive parity | PPV equal across groups (same positive predictive value) |

For retinal screening use, **equal opportunity** is most directly relevant: a sight-threatening condition should be detected equally well for all patients. PPV parity is relevant for downstream workflow equity. Demographic parity (equal positive rate) is **not** a target — disease prevalence legitimately differs by age and other factors.

## 3. Subgroups evaluated

From the reference validation set:

| Factor | Groups |
|--------|--------|
| Age | < 40, 40–59, 60–74, ≥ 75 |
| Sex | Male, Female (Not recorded excluded from subgroup analysis due to N < 10) |
| Camera model | Topcon NW400, Canon CR-2 AF, Zeiss Clarus 500, Other |
| Image quality | Good, Adequate |

Ethnicity stratification is attempted but the source dataset does not record it reliably; subgroup results by ethnicity are available only from the external validation cohort and are sparse.

## 4. Per-subgroup sensitivity — DR

Illustrative results on held-out test set; minimum N per bucket displayed. Bootstrap 95% CI (1000 resamples) in brackets.

| Subgroup | N | Sensitivity | 95% CI |
|----------|---|-------------|--------|
| Overall | 180 | 0.89 | [0.84, 0.93] |
| Age < 40 | 12 | 0.83 | [0.58, 1.00] — wide CI, under-powered |
| Age 40–59 | 58 | 0.91 | [0.83, 0.97] |
| Age 60–74 | 79 | 0.89 | [0.82, 0.95] |
| Age ≥ 75 | 31 | 0.87 | [0.74, 0.97] |
| Sex Male | 94 | 0.89 | [0.83, 0.95] |
| Sex Female | 86 | 0.88 | [0.81, 0.95] |
| Camera Topcon | 71 | 0.90 | [0.83, 0.96] |
| Camera Canon | 58 | 0.88 | [0.79, 0.95] |
| Camera Zeiss | 30 | 0.87 | [0.73, 0.97] |
| Camera Other | 21 | 0.86 | [0.67, 1.00] — wide CI |
| Quality Good | 132 | 0.91 | [0.86, 0.95] |
| Quality Adequate | 48 | 0.83 | [0.73, 0.92] |

Interpretation:
- No subgroup's sensitivity for DR falls more than 5 percentage points below overall after accounting for confidence intervals
- Age < 40 subgroup is under-powered for firm conclusions
- Image quality has the largest observed effect (Good vs Adequate)
- Camera "Other" is under-powered

## 5. Per-subgroup sensitivity — AMD

| Subgroup | N | Sensitivity | 95% CI |
|----------|---|-------------|--------|
| Overall | 105 | 0.80 | [0.72, 0.87] |
| Age 40–59 | 15 | 0.67 | [0.47, 0.87] — under-powered |
| Age 60–74 | 54 | 0.81 | [0.70, 0.91] |
| Age ≥ 75 | 36 | 0.83 | [0.71, 0.94] |
| Sex Male | 48 | 0.79 | [0.67, 0.90] |
| Sex Female | 57 | 0.81 | [0.70, 0.91] |
| Camera Topcon | 41 | 0.83 | [0.71, 0.93] |
| Camera Canon | 35 | 0.77 | [0.63, 0.91] |

Interpretation:
- AMD detection in the Age 40–59 group is lower; AMD is uncommon at these ages but the model's under-detection is concerning — investigated in bias-and-limitations
- Camera dependency is modest

## 6. Per-subgroup sensitivity — Glaucoma

| Subgroup | N | Sensitivity | 95% CI |
|----------|---|-------------|--------|
| Overall | 145 | 0.82 | [0.75, 0.88] |
| Age 40–59 | 47 | 0.85 | [0.74, 0.94] |
| Age 60–74 | 62 | 0.82 | [0.73, 0.92] |
| Age ≥ 75 | 28 | 0.79 | [0.64, 0.93] |
| Sex Male | 77 | 0.83 | [0.75, 0.91] |
| Sex Female | 68 | 0.81 | [0.72, 0.90] |

Glaucoma sensitivity is below DR sensitivity, consistent with the literature finding that glaucoma detection from fundus photography alone is harder than DR.

## 7. Per-subgroup specificity — cross-class

Cross-class false positive rate (model predicts disease when ground truth is Normal) stratified:

| Subgroup | N Normal | FPR | 95% CI |
|----------|----------|-----|--------|
| Overall | 210 | 0.11 | [0.07, 0.15] |
| Age 40–59 | 68 | 0.10 | [0.04, 0.18] |
| Age 60–74 | 95 | 0.11 | [0.06, 0.18] |
| Age ≥ 75 | 32 | 0.16 | [0.05, 0.30] |
| Sex Male | 108 | 0.12 | [0.07, 0.19] |
| Sex Female | 102 | 0.10 | [0.05, 0.16] |

The older age band sees slightly elevated FPR — older fundi have natural age-related changes (drusen, pigmentary changes) that the model may misclassify as early AMD.

## 8. Predictive parity — DR

Positive predictive value stratified:

| Subgroup | N predicted DR | PPV | 95% CI |
|----------|---------------|-----|--------|
| Overall | 191 | 0.84 | [0.78, 0.89] |
| Sex Male | 100 | 0.85 | [0.77, 0.92] |
| Sex Female | 91 | 0.83 | [0.74, 0.91] |

PPV is close across sex groups. Not computed across age bands because DR prevalence varies substantially with age (Simpson-type confounding caution applies — PPV parity in the presence of differential prevalence is not straightforward).

## 9. Summary across subgroups

| Subgroup | Largest gap from overall | Direction | Clinical concern? |
|----------|--------------------------|-----------|-------------------|
| Age < 40 | wide CIs; DR sensitivity point estimate 0.83 vs 0.89 | Lower | Under-powered — not conclusive |
| Age ≥ 75 | FPR elevated (0.16 vs 0.11) | Higher FP | Low-moderate |
| Sex | All gaps < 2 percentage points | — | No |
| Camera | Modest variation; "Other" under-powered | — | No |
| Image quality | Sensitivity drops ~8 points on Adequate vs Good | Lower on Adequate | Moderate — quality gating in UI is the mitigation |

## 10. Mitigations adopted

- **Image quality gate**: Images below a quality threshold trigger a UI warning rather than a confident prediction. Quality score is displayed to the clinician.
- **Older-age FP**: Threshold calibration per age band available via PCCP; any adjustment is validated before deployment.
- **Under-powered subgroups**: Drift monitoring ensures that as sample size grows in deployment, a fairness re-evaluation is triggered.

## 11. What this evaluation does **not** tell us

- Ethnic-group fairness — insufficient data in training set
- Indigenous-population fairness — no representation
- Performance in deployment populations — requires site-specific validation
- Performance under rare-disease conditions
- Interaction effects (e.g. older women with poor image quality) — N too small
- Longitudinal fairness (stability over time) — prospective monitoring required

## 12. Limitations of this kind of analysis

Fairness evaluation on small test sets is noisy. Confidence intervals above are wide; apparent gaps may not be statistically significant. Additionally:

- Demographic labels in fundus datasets are often missing or unreliable
- Fairness metrics in multi-class medical classification are not standardised
- Equal numerical performance does not imply equal clinical value (e.g. sensitivity matters more for sight-threatening conditions)

## 13. Process

This evaluation is re-run:
- On every model release
- On every addition of new training data
- On every expansion of deployment population
- Annually as a minimum
- Whenever drift monitoring flags a subgroup concern

## 14. Governance

Results are reviewed by:
- Clinical lead (signs off clinical acceptability of observed disparities or lack thereof)
- Regulatory lead (signs off on post-market obligations)
- DPO / equity officer where deployment context requires

Sign-off is captured; failures to sign off block release.

## 15. References

- Kleinberg, J., Mullainathan, S., Raghavan, M. (2017). *Inherent Trade-Offs in the Fair Determination of Risk Scores.* ITCS.
- Chouldechova, A. (2017). *Fair prediction with disparate impact.* Big Data.
- Mitchell, S., Potash, E., Barocas, S., D'Amour, A., Lum, K. (2018). *Prediction-Based Decisions and Fairness.* ArXiv.
- Obermeyer, Z., Powers, B., Vogeli, C., Mullainathan, S. (2019). *Dissecting racial bias in an algorithm used to manage the health of populations.* Science.
- Seyyed-Kalantari, L. et al. (2021). *Underdiagnosis bias of AI algorithms in chest X-rays.* Nature Medicine.
