# Model Card — Retina Scan AI (ResNet18 v1.0)

> Google-style model card per Mitchell et al. (2019), *Model Cards for Model Reporting*. **Numbers are illustrative for the reference training pipeline.** A deployed version's model card should report numbers from that deployment's validation.

## Model Details

| | |
|---|---|
| Model name | Retina Scan AI |
| Architecture | ResNet18 (ImageNet pretrained) with custom classification head (Dropout 0.3 → Linear 512→256 → ReLU → Dropout 0.2 → Linear 256→5) |
| Model type | Convolutional neural network; multi-class image classification |
| Version | 1.0.0 |
| Training framework | PyTorch 2.2 + torchvision 0.17 |
| Input | Fundus image, 3-channel RGB, resized to 224×224, normalised with ImageNet statistics |
| Output | 5-class probability distribution over {Normal, Diabetic Retinopathy, Glaucoma, Cataract, AMD} |
| Parameters | 11.2M total; 11.2M trainable (full fine-tuning) |
| Model size on disk | ~45 MB |
| Inference latency | ~60 ms on NVIDIA T4; ~200 ms on CPU (batch of 1) |
| Licence (weights) | To be determined per deployment agreement |
| Licence (code) | See repository licence file |
| Owner | KIM3310 / Retina Scan AI |
| Contact | See repository |
| Feedback | GitHub issues on the repository |
| Citation | Kim, D. (2026). *Retina Scan AI: Retinal Disease Classification with ResNet18 and Grad-CAM Interpretability* |

## Intended Use

### Primary intended use

Decision support for the triage of retinal fundus photographs in an outpatient or screening setting. Specifically, the model is intended to:

- Highlight images with suspected pathology for prioritisation in a radiologist's reading queue
- Surface candidate class and localisation cues (via Grad-CAM) to support, **not replace**, the reader's interpretation

### Primary intended users

- Credentialed ophthalmologists and retinal specialists reading fundus photographs
- Under second-reader configurations: optometrists and nurse practitioners operating within a screening protocol that escalates to ophthalmology on positive findings

### Out-of-scope uses

- **Not** intended for autonomous diagnosis; every output requires clinician review
- **Not** intended for differential diagnosis beyond the five defined classes
- **Not** intended for use on paediatric patients (training data was adults ≥ 18)
- **Not** intended for use on non-mydriatic ultra-widefield imaging modalities without re-validation
- **Not** intended for use on OCT or OCTA (not fundus photography)
- **Not** intended for use in determining disease severity beyond presence/absence of class
- **Not** intended as a substitute for dilated ophthalmologic examination
- **Not** intended for deployment in any clinical setting without site-specific validation and regulatory clearance

## Factors

### Relevant factors

Factors that have been considered for their effect on model behaviour:

| Factor | Values / categorisation |
|--------|-------------------------|
| Age | < 40, 40–59, 60–74, ≥ 75 |
| Sex | Male, Female, Not recorded |
| Fundus camera model | Topcon NW400, Canon CR-2 AF, Zeiss Clarus 500, Centervue DRS, Other |
| Image quality | Good, Adequate, Poor (as rated by a fixed quality rubric) |
| Ethnic group | Asian, European, African, Hispanic, Other / Not recorded (from DICOM 0010,2160 where present) |
| Mydriatic status | Dilated, Non-mydriatic |
| Media opacity | Clear, Mild cataract, Moderate cataract |

### Evaluation factors

Per-subgroup metrics are reported in [`fairness-evaluation.md`](fairness-evaluation.md).

### Factors that were **not** considered adequately

Known gaps in the factor set:

- **Image acquisition protocol variability** across sites beyond what the four reference cameras captured
- **Paediatric imaging** — no paediatric data in training set; performance is undefined
- **Diabetic severity grading** — the model predicts DR vs not-DR but does not grade severity; this is a known limitation relative to the ICDR 5-stage scale
- **Pregnancy-related retinopathies** — gestational DR and pregnancy-related changes are not a separately represented class
- **Global representation** — training data concentrated in South/East Asian cohorts (ODIR-5K origin); performance on African, Latin American, and Indigenous populations less thoroughly characterised

## Metrics

### Primary metrics

| Metric | Value (held-out test set, n = 750) |
|--------|-----------------------------------|
| Overall accuracy | 0.87 |
| Macro F1 | 0.84 |
| Macro AUC | 0.93 |

### Per-class metrics

| Class | n | Sensitivity | Specificity | PPV | NPV | AUC |
|-------|---|-------------|-------------|-----|-----|-----|
| Normal | 210 | 0.91 | 0.89 | 0.86 | 0.93 | 0.94 |
| Diabetic Retinopathy | 180 | 0.89 | 0.94 | 0.84 | 0.96 | 0.95 |
| Glaucoma | 145 | 0.82 | 0.95 | 0.83 | 0.94 | 0.92 |
| Cataract | 110 | 0.88 | 0.93 | 0.78 | 0.97 | 0.93 |
| AMD | 105 | 0.80 | 0.96 | 0.82 | 0.95 | 0.91 |

Bootstrap 95% confidence intervals (1000 resamples) are reported in the evaluation output. Intervals at this sample size are typically ±3–5 percentage points on sensitivity and specificity.

### Operating point selection

For triage use, a sensitivity-favouring operating point is preferred. Default operating point per class (calibrated):

| Class | Threshold | Sensitivity | Specificity |
|-------|-----------|-------------|-------------|
| DR | 0.35 | 0.93 | 0.88 |
| Glaucoma | 0.40 | 0.88 | 0.90 |
| Cataract | 0.45 | 0.91 | 0.89 |
| AMD | 0.40 | 0.86 | 0.92 |

Deployers may adjust thresholds within PCCP-defined bounds; any adjustment is audited.

### Calibration

Expected Calibration Error (ECE) across 15 bins: 0.037 on held-out test set. Platt-scaled variant achieves 0.021.

### Secondary metrics

| Metric | Value |
|--------|-------|
| Per-study inference time | 60 ms (GPU T4) |
| Grad-CAM generation time | 80 ms additional |
| Model file SHA-256 | (recorded per release) |

## Evaluation Data

See [`datasheet.md`](datasheet.md) for full datasheet.

| | |
|---|---|
| Dataset | Held-out test split from ODIR-5K, plus a small external test set for generalisation check |
| Size | 750 fundus photographs in held-out test; external test ~300 |
| Source | ODIR-5K (Peking University International Competition on Ocular Disease Intelligent Recognition) |
| Preprocessing | Resized to 224×224, normalised with ImageNet mean/std |
| Split methodology | Stratified by class; random seed fixed; patient-level split where patient ID available |
| Data from other distributions | External 300-image cohort from a different camera and geography used for generalisation probe |

## Training Data

| | |
|---|---|
| Dataset | ODIR-5K |
| Size | ~5000 images originally, filtered to the 5-class subset (~3500 usable images post filtering) |
| Preprocessing | Class re-labelling to the 5-class taxonomy; images with mixed findings resolved per protocol; see datasheet |
| Augmentation | Random horizontal flip, random rotation up to ±15°, colour jitter (brightness/contrast/saturation 0.2), affine |
| Split | 70/15/15 train/val/test (stratified by class) |
| Class distribution | Per datasheet |
| Known biases | South/East Asian geographic skew; adult-only; non-mydriatic imaging predominant |

## Ethical Considerations

### Potential harms

| Harm | Likelihood | Mitigation |
|------|-----------|-----------|
| False negative for sight-threatening disease → delayed treatment | Medium | Sensitivity-favouring operating point; mandatory clinician review; not used as sole gatekeeper |
| False positive → unnecessary referral | Medium | Specificity-aware operating point; clinician review filters FP before patient notification |
| Differential performance across subgroups → unequal care | Medium | Fairness evaluation; subgroup drift monitoring; deployment blocked for subgroups with known insufficient training representation |
| Automation bias → clinician accepts a wrong AI answer | Medium | UI design mitigations; mandatory review on high-confidence class; disagreement workflow |
| Privacy exposure via fundus biometric | Low | Pseudonymisation; no external sharing; biometric disclosure in consent |
| Model drift → degraded performance without detection | Medium | Drift monitoring programme |
| Scope creep → model used outside intended use | Low–Medium | Model card, training, audit |

### Populations for whom the model should **not** be used

- Paediatric patients (< 18 years)
- Patients with unusual or extensive media opacity obscuring the fundus
- Patients imaged with ultra-widefield or non-RGB fundus modalities
- Patients in populations not represented in training data (documented in bias and limitations)

### Consent and transparency

Deployment context expects:
- General clinical consent framework covers AI-assisted reading
- Patient-facing information leaflet discloses AI use
- Opt-out available where local regulation or institutional policy supports it

See [`../compliance/gdpr-dpia.md`](../compliance/gdpr-dpia.md) §11 for suggested patient-facing text.

### Fairness

See [`fairness-evaluation.md`](fairness-evaluation.md).

## Caveats and Recommendations

### Caveats

- **This is research / reference code.** Not FDA-cleared, not CE-marked. Any clinical deployment requires regulatory clearance and revalidation.
- **Training data is limited** in geography, ethnicity, age spread, and camera variety. Real-world deployment requires validation on the target population.
- **Grad-CAM is an explanation, not a segmentation.** See [`explainability-design.md`](explainability-design.md) for its limits.
- **Calibration must be checked locally.** Global calibration does not imply local calibration per site.
- **Deployment changes trigger re-validation.** New camera, new population, new protocol → re-validate.
- **Numbers above are illustrative** from the reference ODIR-5K training pipeline and should not be cited as performance for any real deployment.

### Recommendations

1. Deploy only after local validation per `../validation/study-protocol.md`
2. Configure RBAC via `../access/roles.py` for the clinical roles at the site
3. Enable all audit events per `../audit/`
4. Configure drift monitoring from day 1
5. Train clinicians per `../docs/clinical/clinician-in-the-loop.md` §9
6. Establish CCB per `../docs/clinical/change-control.md` §6
7. Run an incident-response tabletop before go-live
8. Plan for quarterly PSUR / equivalent

## Change History

| Version | Date | Change |
|---------|------|--------|
| 1.0.0 | 2026-04 | Initial release — reference training |

## Additional Notes

### Why ResNet18 over a larger backbone

Rationale documented in [`../docs/adr/001-resnet18-over-efficientnet.md`](../docs/adr/001-resnet18-over-efficientnet.md).

### Why Grad-CAM over other explainability methods

Rationale in [`explainability-design.md`](explainability-design.md) and [`../docs/adr/002-gradcam-interpretability.md`](../docs/adr/002-gradcam-interpretability.md).

### Known limitations

See [`bias-and-limitations.md`](bias-and-limitations.md) for the canonical list.

## Model Card Maintenance

- Reviewed on every major model release
- Reviewed annually
- Reviewed on discovery of material new information

## Contacts

- Technical: engineering lead on the repository
- Clinical: designated Clinical Lead per deployment
- Regulatory: designated Regulatory Affairs lead per deployment
- Privacy: designated DPO per deployment

## Citation

```
@misc{retinascan2026modelcard,
  title        = {Retina Scan AI Model Card, Version 1.0},
  author       = {Kim, Doeon},
  year         = {2026},
  howpublished = {Retina Scan AI repository},
  note         = {Educational reference; not a regulatory artefact}
}
```

## References

- Mitchell, M. et al. (2019). *Model Cards for Model Reporting.* FAT* Conference.
- FDA/Health Canada/MHRA (2021). *Good Machine Learning Practice for Medical Device Development: Guiding Principles.*
- IMDRF N12. *SaMD Risk Categorization.*
