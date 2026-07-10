# Bias and Limitations

## 1. Intent

This file is the canonical list of known biases and limitations of Retina Scan AI. It is intentionally frank. A model card that hides its own limitations is worse than useless because it invites misplaced trust.

For the upstream training dataset's composition and known issues, see [`datasheet.md`](datasheet.md).

## 2. Dataset biases

### 2.1 Geographic concentration

Training data (ODIR-5K) was collected in a subset of Chinese clinics. This produces:

- Over-representation of East Asian retinal anatomy and disease presentation
- Under-representation of other populations' fundus appearance (melanin density, disc appearance, drusen patterns)
- Under-representation of health-system contexts outside East Asian clinical practice

**Implication**: Model performance on non-East-Asian populations is not established. External-cohort testing showed degradation on the available external cohort but the external cohort was small (~300 images) and not itself globally representative.

### 2.2 Age distribution

Training data skews toward working-age and early-elderly adults. Under-representation of:

- Children and adolescents (absent entirely)
- Very elderly (≥ 85) with associated multi-morbidity
- Early-onset paediatric retinopathies

**Implication**: The model is not validated for paediatric use; do not deploy on < 18 years old. Very elderly performance is likely under-powered in evaluation.

### 2.3 Camera diversity

Training data was acquired on a narrow set of fundus cameras (exact set not published). Camera-specific features (optics, illumination, colour profile) may be learned as confounders.

**Implication**: Deployment on a new camera model requires a distribution-shift acceptance test. This is codified in the PCCP and change-control process.

### 2.4 Acquisition protocol

Training data predominantly non-mydriatic imaging. Mydriatic (dilated) imaging produces different image appearance.

**Implication**: Model may underperform on dilated imagery until retraining includes such samples. Conversely, if deployed in contexts where dilated imaging is standard, results may not transfer.

### 2.5 Disease severity

Training data collapses ICDR-style DR staging (no DR / mild / moderate / severe / proliferative) into binary DR-positive for the 5-class taxonomy. Similarly, AMD and glaucoma are not staged.

**Implication**: The model cannot grade severity. A positive finding should trigger full clinical evaluation, not direct treatment decision.

### 2.6 Co-occurring conditions

Images with multiple findings are collapsed to a primary-class label during training. Real-world retina has co-occurring DR + cataract frequently.

**Implication**: The 5-class output is a single-label classification over a multi-label reality. Where both DR and cataract are present, the model's second-highest probability may contain the missed co-morbidity.

### 2.7 Label noise

Upstream labelling is from contributing clinicians; inter-rater agreement statistics are not published. Our estimate of 3–5% label noise on borderline cases is based on small-scale re-annotation.

**Implication**: Reported sensitivity and specificity are against noisy labels. True performance against expert panel ground truth may differ.

## 3. Model architecture limitations

### 3.1 Classification, not detection

The model outputs a single probability vector per image, not bounding boxes or segmentation masks. Lesion localisation is implicit via Grad-CAM and should not be over-interpreted.

### 3.2 Single-image, not longitudinal

Each image is classified independently. Longitudinal change (progression of DR from non-DR to mild to moderate) is not modelled. Clinicians tracking a patient over time receive independent single-image classifications.

### 3.3 Single-eye, not binocular

Each eye is an independent input. The model does not use both eyes of the same patient as context.

### 3.4 No external context

The model has no access to patient age, glucose, visual acuity, or other clinical data. All context comes from the pixels.

### 3.5 Fixed input resolution

Training at 224×224 loses fine detail visible at native resolution (typically 2000+ pixels across). Microaneurysms and subtle cotton-wool spots may be lost.

**Implication**: Model is a triage aid, not a micro-lesion detector. A fundus specialist working at native resolution may see findings the model cannot.

## 4. Calibration limitations

- Model is calibrated on the training/validation distribution. Deployment populations may show different calibration.
- Site-specific recalibration is available via PCCP but must be validated before adoption.
- Expected calibration error (ECE) is an average metric; per-subgroup calibration can differ.

## 5. Failure modes observed in testing

From internal testing; subject to expansion as deployments reveal more.

| Failure mode | Observed trigger | Mitigation |
|-------------|------------------|-----------|
| Confident wrong on very dark / underexposed images | Low contrast input | Image quality gate |
| Mis-classification of Normal with prominent drusen as AMD | Older subjects with benign drusen | Clinician review |
| Cataract false positive on images with media opacity from non-cataract causes | Vitreous haze, corneal edema | Clinician review; note in UI |
| Glaucoma under-detection on low-cup-disc eyes | Small disc, small cup | Specialist referral remains primary pathway |
| Grad-CAM pointing to optic disc regardless of actual lesion location | DR images | Clinician education on Grad-CAM interpretation |
| Out-of-distribution image (non-fundus, e.g. OCT, slit-lamp) producing confident prediction | Wrong modality uploaded | Input modality gate; OOD detector |

## 6. Populations where the model should **not** be used

Authoritative list:

1. Paediatric patients (< 18 years old)
2. Patients with extensive media opacity obscuring the fundus (heavy cataract, vitreous haemorrhage)
3. Patients imaged with non-RGB ultra-widefield systems without site validation
4. Patients imaged on OCT / OCTA / slit-lamp (not fundus photography)
5. Patients in populations with no training data representation (requires site-specific validation or do-not-use declaration)

## 7. Clinical workflow contexts where deployment requires care

- Remote screening without access to an ophthalmologist for referral — the model's output requires a referral pathway; deploying where no referral is available is inappropriate
- Emergency ophthalmology — the model is not validated for acute presentations
- Pregnancy-related retinal conditions — gestational DR and pregnancy-related changes are not characterised
- Post-surgical monitoring — model is not validated for post-op fundus appearance

## 8. Security and adversarial considerations

- No adversarial training was performed
- Adversarial robustness not tested in depth
- Input quality gating provides some defence against heavily perturbed inputs
- Audit logging provides post-hoc detection of unusual input patterns

## 9. Feedback loops

Possible feedback-loop risks if the model is used uncritically:

- If the model directs screening attention preferentially to certain subgroups, detection rates in those subgroups increase (apparent improvement) while undetected disease in other subgroups compounds (real degradation)
- If the model's output influences which patients are re-imaged, the training data evolves toward the model's biases when retrained on post-deployment data

**Mitigation**: retraining data selection is not driven by model output; clinical protocols for re-imaging are not model-gated; disagreement and override data are specifically tracked as a counter-signal.

## 10. Assumptions about deployment environment

The model's performance assumes the deployment environment:

- Has a qualified clinician review step
- Maintains image quality standards at least as good as the training set
- Has a referral pathway for positive findings
- Has a functioning audit and drift monitoring stack
- Has governance processes per `../docs/clinical/`

Violations of any of these assumptions may invalidate reported performance.

## 11. What we do not know

Honest statement of gaps:

- Longitudinal stability (how does the model perform across a patient's repeat visits over years?)
- Rare subgroup interactions (elderly + low quality + non-East-Asian)
- Performance at the extremes of disease severity
- Impact on clinician decision-making over time (does reliance grow, skill atrophy?)
- Downstream health outcomes (does AI-assisted screening translate to better patient outcomes? — requires an outcomes study, not this model card)

## 12. Where to send updates to this document

As deployment data accumulates, this document is revised. Suggested update triggers:

- Any incident retrospective that identifies a new failure mode
- Drift-monitoring finding that reveals a previously undocumented bias
- External research that characterises a limitation of this class of model
- Fairness evaluation update that changes the subgroup picture

## 13. Relationship to regulatory documentation

Regulatory submissions (510(k), CE technical file) contain a structured risk analysis per ISO 14971 (see `../risk/fmea.md` and `../risk/iso14971-mapping.md`). The items here feed into that analysis; the FMEA is the operational register.

## 14. Statement for users

To any clinician or institution considering use of this model: **read this file in full before deciding to deploy, read it again before training your team, and read it a third time if you change any of the deployment conditions**. The list is not exhaustive; your site's deployment will discover more.
