# Known Limitations

Documented constraints, edge cases, and known failure modes of the Retina Scan AI system, based on development testing and published literature.

## Model limitations

### Subgroup performance not fully characterized

The training dataset (ODIR-5K) has under-representation of several populations. Performance is not guaranteed to generalize to:

- Ethnic groups under-represented in ODIR-5K.
- Patients with rare retinal conditions outside the 5 trained classes.
- Very young patients (pediatric fundus anatomy differs).
- Post-surgical eyes (healing artifacts).

**Implication**: validation study (`validation/`) must characterize subgroup performance before deployment.

### Limited class vocabulary

The model handles 5 classes: Normal, Diabetic Retinopathy, Glaucoma, Cataract, Age-related Macular Degeneration. Real fundus pathology includes dozens more conditions (retinal detachment, central retinal vein occlusion, optic neuritis, etc.). The model will either:

- Silently predict "Normal" for out-of-vocabulary conditions (high-severity failure mode).
- Incorrectly assign one of the 5 known classes.

**Mitigation**: gradeability classifier rejects clearly-OOD images; workflow assumes the model is a *triage* tool, not a primary diagnostic tool.

### Image quality sensitivity

Performance depends on image quality:

- Minimum resolution: 224 × 224 (matches ResNet18 input).
- Minimum field of view: 45 degrees.
- Focus must be within the macula or optic disc for DR / Glaucoma detection.
- Gradable image quality is assumed; automatic gradeability check rejects low-quality inputs.

**Typical ungradeable rate**: 3-5% in real deployments. This rate is tracked in production.

### Camera / device variation

Trained on a subset of fundus cameras present in ODIR-5K. Performance may vary with:

- Camera models not in training set (e.g., portable retinal cameras, smartphone attachments).
- Lighting variation across facilities.
- Dye-dilated vs non-dilated imaging.

**Mitigation**: subgroup analysis by camera type; retraining recommended before use with substantially different equipment.

### Lateralization

The model does not distinguish left vs right eye. Upstream metadata must preserve laterality.

## Interpretability limitations

### Grad-CAM is approximate

Grad-CAM highlights activation regions in the last convolutional layer. It can:

- Highlight regions that correlate with, but don't cause, the prediction.
- Miss fine-grained features that differentiate between similar conditions.
- Anchor on artifacts (lens flare, vignetting) that may correlate with confounds.

**Implication**: Grad-CAM is a diagnostic aid, not an explanation. Clinicians must not treat Grad-CAM as ground truth about what the model actually used.

### No counterfactual explanations

The system provides no counterfactual ("if this feature weren't present, the prediction would change to X"). Counterfactual explanations are a research area; they are not available in this prototype.

### No confidence calibration guarantee

Model probabilities are not calibrated by default. A 0.87 DR probability does not mean 87% of such predictions are DR. Calibration (Platt scaling, isotherm regression, or histogram binning) is a post-hoc step performed after training and must be re-done after retraining.

## Workflow limitations

### Single-image inference

The model operates on a single fundus image per inference. It does not consider:

- Longitudinal change (prior visit imagery).
- Bilateral comparison (both eyes).
- Multi-modal data (OCT, visual field tests, patient history).

**Implication**: this is a screening/triage tool, not a substitute for a comprehensive ophthalmic examination.

### No integrated clinical context

The model does not ingest patient history, medications, or comorbidities. A patient with known diabetic retinopathy will be scored the same as a patient with no history; the clinical context is the clinician's responsibility.

### Latency assumptions

Target inference latency: under 300 ms on standard GPU hardware. Under load, latency may exceed this. The UI shows a spinner and does not time out studies, but high-latency deployment may disrupt clinician workflow.

## Operational limitations

### Not a medical device

This code is research. It is not FDA-cleared, CE-marked, or approved for clinical use in any jurisdiction. Any deployment for clinical use requires regulatory clearance.

### No real-time monitoring integration

The system emits audit and drift metrics but does not integrate with any specific PACS, EHR, or hospital monitoring platform out of the box. Integration is documented but implemented per deployment.

### Dependency on external identity provider

The authentication layer assumes a hospital OIDC provider. Deployments without federated identity must implement a local auth mechanism, which is not provided.

### No offline mode

The service requires network connectivity between the clinical UI, the inference service, and the identity provider. Offline operation is not supported.

## Known bugs and issues

This section is updated from issue tracker findings and deployment lessons.

| Date | Issue | Status |
|------|-------|--------|
| 2026-04-17 | Initial catalog | Baseline |

(Add entries here as production issues are identified and resolved.)

## What good looks like (not current)

To move from research to production-ready, the following are required:

1. External multi-site clinical validation per `validation/study-protocol.md`.
2. FDA 510(k) submission or equivalent regulatory pathway (see `compliance/fda-samd-considerations.md`).
3. ISO 13485 QMS certification of the development organization.
4. IEC 62304 software lifecycle documentation.
5. IEC 62366-1 usability engineering (summative evaluation with representative users).
6. Cybersecurity posture per IEC 81001-5-1 and FDA premarket cybersecurity guidance.
7. Post-market surveillance plan with regulatory reporting links.
8. Clinical benefit-risk memorandum.

The current system is a research reference; production readiness is a separate, substantial program of work.

## References

- ODIR-5K dataset: https://www.kaggle.com/datasets/andrewmvd/ocular-disease-recognition-odir5k
- "Hidden stratification" (Oakden-Rayner et al. 2020): https://dl.acm.org/doi/10.1145/3368555.3384468
- FDA Guidance on CDSS (2022).
- CONSORT-AI 2020.
- Grad-CAM (Selvaraju et al. 2017): https://arxiv.org/abs/1610.02391
