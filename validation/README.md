# Clinical Validation

Artifacts for designing, running, and reporting a validation study of the retinal classification model before any clinical deployment.

## Why validation

Laboratory accuracy on ODIR-5K or a held-out test set is necessary but insufficient for clinical use. A validation study measures performance on:

- **Prospective** data (collected after model training, not from the training distribution).
- **Multi-site** data (from facilities other than where training data came from).
- **Prospective workflow** (the model in the clinical UI, not just the model in isolation).
- **Ground truth established by panel-adjudicated clinical diagnosis**, not auto-generated labels.

This directory contains the templates for running such a study. It is NOT the study results — those come from running the protocol with an IRB-approved clinical partner.

## Files

- `study-protocol.md` — The validation study protocol: population, endpoints, statistical plan.
- `case-report-form.md` — CRF template for capturing ground truth vs model prediction.
- `sample-size-calculation.py` — Runnable sample size calculator.
- `results-template.json` — Structure of the validation study output.

## Design philosophy

1. **Pre-specified analysis plan**. Primary and secondary endpoints are fixed before the study starts. No post-hoc subgroup fishing.
2. **Blinding where possible**. Adjudicators are blinded to model predictions during ground truth establishment.
3. **Adequate power**. Sample size is calculated to detect the minimum clinically meaningful difference, not just statistical significance.
4. **Fairness audit**. Subgroup performance is reported by age, sex, ethnicity, and camera type.
5. **Transparent failure reporting**. Every false negative and every false positive is reviewed and categorized (near-miss, severe-miss, ambiguous case).

## Primary endpoint

Sensitivity at a fixed specificity threshold (typically specificity ≥ 0.90 — matching typical screening tool requirements).

**Success criterion**: sensitivity lower bound of 95% CI ≥ 0.85 for each of the four disease classes (DR, Glaucoma, Cataract, AMD), with specificity ≥ 0.90.

## Secondary endpoints

- Per-class sensitivity and specificity.
- AUC by class.
- Agreement with adjudicator panel (Cohen's kappa).
- Subgroup performance by age, sex, ethnicity, camera type.
- Time-to-decision (model) vs time-to-decision (clinician alone).
- False-positive review burden (additional clinician minutes per 100 cases).

## Study population

- Prospective enrollment at 3+ clinical sites.
- Sample size ≥ 2,000 eyes (determined by `sample-size-calculation.py`).
- Inclusion criteria: adults ≥ 18, fundus image available, consent provided.
- Exclusion criteria: known predefined conditions that are out of scope (e.g., post-surgical patients for some classes).

## Ground truth establishment

Panel adjudication:
- 3 independent retina specialists grade each fundus image without model predictions.
- Disagreements resolved by panel consensus.
- Ground truth locked before model predictions are revealed.

## Fairness audit

Per-subgroup metrics computed for:
- Age groups: 18-39, 40-59, 60-79, 80+.
- Sex: male, female, other.
- Self-reported ethnicity (site-adapted to local conventions).
- Camera types: Topcon, Canon, Zeiss, iCare, other.

For each subgroup, report:
- Sensitivity and specificity with 95% CI.
- Difference from overall metric.
- Statistical test for subgroup difference (Bonferroni-corrected).

If any subgroup shows sensitivity difference > 10 percentage points with p < 0.01, the model is flagged for remediation before deployment.

## What this is NOT

- Not a regulatory submission package (separate FDA / CE process).
- Not a marketing claim (internal validation; no marketing without broader studies).
- Not a substitute for ongoing post-market surveillance (see `docs/clinical/drift-monitoring.md`).

## Running the analysis

When the study data is collected:

```bash
# 1. Compute sample-size adequacy on the final enrolled cohort
python validation/sample-size-calculation.py --enrolled-n 2150 --prevalence 0.18

# 2. Fit the primary analysis from collected ground truth + model predictions
python -m src.evaluate checkpoints/best_model.pth \
    --ground-truth validation/study_data/ground_truth.csv \
    --predictions validation/study_data/predictions.csv \
    --output validation/study_results.json

# 3. Generate the subgroup analysis
python validation/fairness_audit.py validation/study_data/ validation/subgroup_results.json
```

The output JSON matches the schema in `results-template.json`.

## References

- FDA Guidance on Clinical Decision Support Software (2022)
- CONSORT-AI 2020 — reporting standard for AI-in-medicine clinical trials
- SPIRIT-AI 2020 — trial protocol standard for AI studies
- DECIDE-AI 2022 — reporting standard for early-stage AI evaluation
