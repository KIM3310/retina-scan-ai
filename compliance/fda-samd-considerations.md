# FDA SaMD Considerations

> **Educational reference only.** This file does not constitute a regulatory strategy or legal advice. A real submission requires engagement with qualified regulatory affairs counsel, a formal Q-submission (Q-Sub) with CDRH, and a clinical evaluation plan reviewed by a biostatistician. The descriptions below reflect the author's reading of FDA guidance as of early 2026; they are subject to change.

## 1. Is it a device?

Under 21 U.S.C. § 321(h), a "device" includes "an instrument, apparatus, … or other similar or related article … intended for use in the diagnosis of disease or other conditions, or in the cure, mitigation, treatment, or prevention of disease." The Software Precertification Program and IMDRF N10/N12/N41 SaMD definitions clarify that standalone software intended to inform a clinical decision is a device.

Retina Scan AI outputs a five-class probability distribution (Normal, Diabetic Retinopathy, Glaucoma, Cataract, AMD) over a fundus image. If used *in a clinical decision-making context* (triage, referral, diagnosis assistance), this is a device. The 21st Century Cures Act § 3060 software carve-outs (21 U.S.C. § 360j(o)) do not apply because the software interprets images rather than only displays clinical laboratory values.

If used *strictly for education* (as this repository is), it is not a device. Deployment for patient care requires a regulatory submission.

## 2. SaMD classification — IMDRF framework

IMDRF N12 categorises SaMD on two axes:

| Axis | Retina Scan AI position |
|------|-------------------------|
| Significance of information provided by SaMD to healthcare decision | **Drive clinical management** — the model's top-class output, if trusted, would drive a referral decision to ophthalmology |
| State of healthcare situation or condition | **Serious** — DR and AMD can cause irreversible vision loss; time-sensitive referral pathways exist |

Combining these per IMDRF N12 Table 1 yields **Category III** SaMD. Category III SaMD typically maps to FDA Class II and EU MDR Class IIa or IIb.

## 3. FDA pathway options

### 3.1 510(k) — most likely pathway

Several predicate devices exist for AI-based retinal screening and are the natural predicate candidates:

| Predicate device | Clearance / Authorisation | Indication | Relevance |
|------------------|---------------------------|------------|-----------|
| IDx-DR (LumineticsCore) | De Novo DEN180001 (2018) | Autonomous detection of more-than-mild diabetic retinopathy | First autonomous AI diagnostic; De Novo established the category |
| EyeArt (Eyenuk) | 510(k) K200667 (2020), K223870 (2023) | DR detection | Active commercial predicate; 510(k) with IDx-DR as predicate |
| AEYE-DS (AEYE Health) | 510(k) K220137 (2022) | DR screening | Portable fundus camera workflow |
| SELENA+ (EyRIS) | Pre-submission meetings, global clearances (Singapore, EU) | Multi-disease (DR, AMD, glaucoma) | Closest clinical analogue to multi-class output |

A 510(k) pathway is viable if substantial equivalence to a legally marketed predicate can be demonstrated. The five-class multi-disease output is a difference vs most single-disease predicates; SELENA+ is the closest analogue and may be useful as a reference device for the expanded indication.

### 3.2 De Novo — if no suitable predicate

If CDRH determines no predicate is substantially equivalent (e.g. the multi-disease indication is deemed a new intended use with different risk), a De Novo classification request under section 513(f)(2) of the FD&C Act is required. De Novo has been the historical path for first-of-kind AI diagnostics (e.g. IDx-DR, OsteoDetect, Caption Guidance).

### 3.3 Pre-market Approval (PMA) — unlikely

A PMA would apply only if the device were classified Class III, which would require CDRH to find that general and special controls are insufficient to assure safety and effectiveness. For decision-support retinal screening this is not expected; PMA devices in ophthalmology tend to be implants and intraocular prostheses.

## 4. Special considerations for AI/ML devices

### 4.1 Good Machine Learning Practice (GMLP)

The FDA, Health Canada and MHRA jointly published *Good Machine Learning Practice for Medical Device Development: Guiding Principles* (October 2021). The ten principles are addressed in this repository as follows:

| GMLP Principle | Addressed by |
|----------------|--------------|
| 1. Multi-disciplinary expertise applied throughout lifecycle | `docs/clinical/clinician-in-the-loop.md`, `docs/clinical/change-control.md` |
| 2. Good software engineering and security practices | Existing `src/`, `api/`; test suite; `audit/`; CI pipeline (to be added) |
| 3. Clinical study participants and datasets representative of intended patient population | `governance/datasheet.md`, `governance/bias-and-limitations.md`, `validation/study-protocol.md` |
| 4. Training datasets independent of test sets | `src/train.py` (stratified split), `governance/datasheet.md` |
| 5. Selected reference datasets based on best available methods | `governance/datasheet.md` (ODIR-5K + external validation cohorts) |
| 6. Model design tailored to available data, reflects intended use | `governance/model-card.md`, `governance/explainability-design.md` |
| 7. Human-AI team performance focus | `docs/clinical/clinician-in-the-loop.md`, `clinical_ui/` |
| 8. Testing demonstrates performance during clinically relevant conditions | `validation/study-protocol.md` (prospective multi-site) |
| 9. Users provided with clear, essential information | `clinical_ui/`, `governance/model-card.md` |
| 10. Deployed models monitored for performance and retraining risks managed | `docs/clinical/drift-monitoring.md`, `docs/clinical/change-control.md` |

### 4.2 Predetermined Change Control Plan (PCCP)

The FDA's December 2024 final guidance *Marketing Submission Recommendations for a Predetermined Change Control Plan for Artificial Intelligence-Enabled Device Software Functions* allows sponsors to pre-specify certain model modifications that can be made post-market without a new submission. A PCCP contains:

1. **Description of Modifications (DoM)** — which planned changes are covered (e.g. retraining on new data, hyperparameter tuning within bounds)
2. **Modification Protocol (MP)** — how each change will be implemented, verified, validated
3. **Impact Assessment** — benefits and risks of the changes

Retina Scan AI's PCCP (if pursued) would cover:

- **Retraining** on new labelled data from deployed sites, holding architecture and class list fixed
- **Threshold calibration** per site using conformal prediction or Platt scaling, with bounded shift
- **New camera model support** when added cameras pass an input-distribution acceptance test

Out-of-scope for a PCCP — requires new submission:
- Adding a new disease class
- Changing backbone architecture
- Expanding indication to paediatric or gestational populations

Our change-control gating logic is documented in [`../docs/clinical/change-control.md`](../docs/clinical/change-control.md).

## 5. Regulatory artefacts inventory

A 510(k) for an AI ophthalmology device typically contains the following. Columns indicate where this repository begins to satisfy each.

| Artifact | Required content | This repo |
|----------|-----------------|-----------|
| 510(k) Cover Letter | Administrative | Operational |
| Indications for Use | Patient population, setting, clinical decision supported | `governance/model-card.md` |
| Device Description | Algorithm, architecture, inputs/outputs, hardware if any | `README.md`, `governance/model-card.md` |
| Substantial Equivalence Discussion | Side-by-side comparison vs predicate | Not in repo — regulatory work |
| Performance Testing — Bench | Analytical performance (software V&V) | `tests/`, `src/evaluate.py` outputs |
| Performance Testing — Clinical | Clinical study report | `validation/study-protocol.md`, `validation/results-template.json` |
| Labelling | IFU, user manual, warnings | `clinical_ui/`, `governance/model-card.md` (Caveats) |
| Risk Analysis | ISO 14971 per software risk | `risk/fmea.md`, `risk/iso14971-mapping.md` |
| Software Documentation (Level of Concern) | Level per FDA 2023 *Content of Premarket Submissions for Device Software Functions* | Enhanced/Basic determination; software requirements, arch, V&V |
| Cybersecurity Documentation | Per FDA 2023 *Cybersecurity in Medical Devices* | `compliance/hipaa-mapping.md`, `access/`, `audit/` |
| Human Factors / Usability | IEC 62366-1 usability engineering file | `clinical_ui/design-rationale.md`, summative HF study (outside repo) |
| Biocompatibility | Not applicable — non-contact software | N/A |
| Electromagnetic Compatibility | Not applicable — pure software, no hardware | N/A |

## 6. Software Level of Concern and IEC 62304 class

Per FDA 2023 guidance, software submissions are classified as **Basic** or **Enhanced** documentation level. A device where a failure could result in serious injury is Enhanced. Retina Scan AI's failure modes (missed DR referral → delayed treatment → permanent vision loss) support **Enhanced** documentation level.

IEC 62304 Software Safety Class:

| Class | Criterion | Retina Scan AI |
|-------|-----------|----------------|
| A | No injury possible | No |
| B | Non-serious injury possible | Candidate if used with clinician oversight and confirmatory dilated exam |
| C | Death or serious injury possible | Candidate if used autonomously (no clinician review) |

Our deployment pattern (second-reader / triage with mandatory clinician sign-off) supports **Class B**. An autonomous-screening deployment (IDx-DR style) would be **Class C**. The reference UI (`clinical_ui/`) explicitly requires clinician concurrence for high-severity classes.

## 7. Change control — what triggers a new submission?

Under FDA's *Deciding When to Submit a 510(k) for a Software Change to an Existing Device* (2017), these changes require a new submission unless covered by a PCCP:

- Changes to the indications for use
- Change that significantly affects clinical functionality or performance specifications (> documented thresholds)
- New risk introduced by the change
- Change in core algorithmic approach (e.g. ResNet18 → Vision Transformer)

Changes that typically do **not** require a new submission:
- Bug fixes with documented regression tests
- Retraining within the scope of an approved PCCP
- Performance optimisations that don't change model outputs

Our cadence is described in [`../docs/clinical/change-control.md`](../docs/clinical/change-control.md).

## 8. Post-market obligations

If cleared, a deployment must:

- **MDR (Medical Device Reporting)** — report any death, serious injury, or malfunction likely to cause serious injury per 21 CFR Part 803 within specified timelines (30 days; 5 days for events requiring immediate remedy)
- **Corrections and Removals** — report per 21 CFR Part 806 any correction or removal initiated to reduce a health risk
- **Complaint Handling** — QSR § 820.198 complaint system with documented investigation
- **Post-Approval Monitoring** — for AI devices, aligned with the PCCP's real-world performance monitoring plan — implemented as drift monitoring in [`../docs/clinical/drift-monitoring.md`](../docs/clinical/drift-monitoring.md)

## 9. Interaction with other frameworks

| Framework | Interaction |
|-----------|-------------|
| HIPAA | Security & privacy baseline underlies all FDA deployment |
| ISO 13485:2016 | QMS standard; FDA now recognises ISO 13485 under 21 CFR Part 820 QMSR (published Jan 2024, effective Feb 2026) |
| ISO 14971:2019 | Required risk management process; referenced in CDRH reviews |
| IEC 62304 | Software lifecycle; FDA consensus standard |
| IEC 62366-1 | Usability engineering; FDA consensus standard |
| ISO 14155 | Clinical investigations if prospective pivotal study required |

## 10. Timeline realism

For planning purposes, a realistic commercial timeline for a first-of-its-kind multi-disease retinal AI:

| Phase | Duration |
|-------|----------|
| Algorithm freeze → V&V complete | 6–9 months |
| Clinical validation study execution | 9–15 months (multi-site prospective) |
| Submission preparation | 3–6 months |
| FDA review (510(k)) | 90–180 days review clock; elapsed time often 6–12 months including questions |
| FDA review (De Novo) | 150 days review clock; elapsed time 12–18 months |
| Total wall-clock | 2.5–4 years |

This is the primary reason a mature change-control plan (PCCP) is valuable: subsequent model updates avoid repeating the full cycle.

## 11. What this repository is not

To restate with precision:

- Not an FDA-cleared device
- Not in a cleared indication
- Not validated clinically for use in patient care
- Not a substitute for dilated ophthalmologic examination

Anyone considering moving this toward clearance should begin with a CDRH Q-Submission to align on pathway, predicate, and clinical evidence expectations.

## References

- FDA, *Artificial Intelligence and Machine Learning Software as a Medical Device Action Plan*, January 2021
- FDA, *Marketing Submission Recommendations for a Predetermined Change Control Plan for Artificial Intelligence-Enabled Device Software Functions*, December 2024 (final)
- FDA/Health Canada/MHRA, *Good Machine Learning Practice for Medical Device Development: Guiding Principles*, October 2021
- FDA, *Content of Premarket Submissions for Device Software Functions*, June 2023
- FDA, *Cybersecurity in Medical Devices: Quality System Considerations and Content of Premarket Submissions*, September 2023
- IMDRF/SaMD WG, *Software as a Medical Device: Possible Framework for Risk Categorization and Corresponding Considerations*, N12 (2014)
- FDA De Novo DEN180001 (IDx-DR) decision summary
