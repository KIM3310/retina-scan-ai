# Data Protection Impact Assessment (DPIA)

> **Template filled with illustrative content for a reference deployment.** An actual DPIA under GDPR Article 35 must be prepared and signed off by a qualified DPO for a specific deployment context, with current legal basis review. The content below illustrates the structure and reasoning a DPIA would take.

## Status

| Field | Value |
|-------|-------|
| DPIA title | Retina Scan AI — retinal disease decision-support deployment |
| Version | 0.1 (template) |
| Prepared by | Engineering + (placeholder DPO) |
| Date | 2026-04 |
| Review date | Annual + on material change |
| Controller | Deploying hospital / clinical network |
| Processor | Retina Scan AI operator |
| DPO consulted | [Yes/No — hospital DPO contact on file] |
| Result | High residual risk? [No] — DPIA approved by DPO; conditional on mitigations below |

## 1. Why is a DPIA required?

Under GDPR Article 35(1), a DPIA is required when processing is likely to result in a high risk to rights and freedoms. Per Article 35(3)(b), systematic processing of special category data (including health data under Art. 9) on a large scale always requires a DPIA. The European Data Protection Board (EDPB) WP248 rev.01 confirms that AI-based diagnostic support processing health data meets multiple "likely-high-risk" criteria:

| EDPB criterion | Met? | Note |
|----------------|------|------|
| Evaluation or scoring | Yes | Model classifies across 5 disease categories |
| Automated decision-making with legal or similarly significant effect | Partially | Decision support, not autonomous; clinician remains in the loop — reduces to Art. 22 non-applicability, but still material |
| Systematic monitoring | Yes | Ongoing drift monitoring |
| Sensitive data or data of highly personal nature | Yes | Health data; retinal vasculature has biometric character |
| Processed on a large scale | Yes | Multiple sites, thousands of patients |
| Datasets combined or matched | Partially | Model output linked back to clinical record at the hospital |
| Data concerning vulnerable data subjects | Partially | Patients are in a vulnerable position vis-à-vis the healthcare provider |
| Innovative use / new technology | Yes | Convolutional neural network on retinal imagery |
| Prevents data subjects from exercising a right or using a service | Potentially | If a positive finding triggers a referral the patient had not anticipated |

Four or more criteria met → DPIA strongly required.

## 2. Systematic description of processing

### 2.1 Nature

Automated classification of retinal fundus photographs into five disease categories (Normal, DR, Glaucoma, Cataract, AMD), producing a class probability vector and a Grad-CAM visualisation highlighting image regions contributing to the prediction. Output is shown in the hospital PACS viewer alongside the original image for review by a clinician.

### 2.2 Scope

- Data subjects: patients referred for fundus photography at participating sites
- Categories of data: fundus image pixels, DICOM header (pseudonymised before inference), timestamp of study, pseudonymised patient ID, pseudonymised study UID
- Special category: yes (health data, biometric character)
- Volume: estimated 500–5000 studies per site per month
- Retention: per `../audit/retention_policy.md`

### 2.3 Context

- Relationship with data subject: patient-provider, with clinical duty of care
- Consent granted for the processing through general clinical consent + specific notification about decision-support use; an option to opt out of AI-assisted reading is offered

### 2.4 Purposes

- Primary: decision-support to assist clinician triage and referral prioritisation
- Secondary: aggregate quality monitoring (drift)
- Not permitted: secondary research without a separate ethics approval and consent; marketing; profiling beyond the clinical purpose

### 2.5 Recipients

- Treating clinician at the deploying site
- Authorised audit and QA personnel within the Controller organisation
- Processor (Retina Scan AI operator) — for technical support only under Art. 28 DPA, access limited to pseudonymised data

## 3. Lawful basis

Under GDPR Article 6 — processing necessary for performance of a task carried out in the public interest or in the exercise of official authority vested in the controller (Art. 6(1)(e)) **or** for compliance with a legal obligation (Art. 6(1)(c)) for public healthcare providers; legitimate interests (Art. 6(1)(f)) for private providers where proportionate.

Under GDPR Article 9 — lawful basis for special category data:
- Art. 9(2)(h) — processing necessary for medical diagnosis, the provision of health care, under responsibility of a professional subject to professional secrecy — **primary basis**
- Art. 9(2)(i) — reasons of public interest in public health — applicable in screening contexts with appropriate safeguards
- Supplementary: Member State law permitting automated processing of health data per Art. 9(4) derogation

## 4. Necessity and proportionality

### 4.1 Necessity

Does the processing achieve a legitimate purpose? Yes — improving early detection of sight-threatening disease.

Could it be done with less data? Evaluated — minimum necessary is: fundus pixels, timestamp (for ordering), pseudonymised ID (for linking clinical follow-up). All other DICOM fields are stripped pre-inference.

### 4.2 Proportionality

| Factor | Assessment |
|--------|------------|
| Expected benefit | Earlier detection of DR, AMD, glaucoma — demonstrated clinical utility for DR in literature, expected to extend |
| Risk to rights | Limited by human-in-the-loop and pseudonymisation |
| Alternative less intrusive means | Unassisted clinician reading — the comparator in the validation study; the AI does not remove this option, it supplements it |
| Is the processing proportionate? | Yes, assuming clinician oversight and robust validation |

## 5. Consultation

| Party | Consulted | Outcome |
|-------|-----------|---------|
| DPO | [yes] | Opinion incorporated; sign-off recorded |
| Data subjects (via patient representative group) | [yes] | Transparency and opt-out concerns addressed |
| Information Governance / Caldicott Guardian (UK) | [where applicable] | Use justified under Caldicott principles |
| Clinical leadership | Yes | Clinical necessity confirmed |
| IT Security | Yes | Controls in `../compliance/hipaa-mapping.md` confirmed |
| Legal | Yes | Lawful basis confirmed |

## 6. Risk identification

High-level risks assessed; detailed failure modes in `../risk/fmea.md`.

| ID | Risk | Likelihood | Severity | Inherent risk | Mitigation | Residual |
|----|------|-----------|----------|---------------|-----------|----------|
| P1 | Re-identification from pseudonymised fundus image via biometric character | Low | High | Medium | Data stays in hospital boundary; no external publication; biometric character disclosed in consent | Low |
| P2 | Unauthorised access to inference results | Low | High | Medium | RBAC, OIDC, audit logging, break-glass review | Low |
| P3 | Audit log tampering | Low | High | Medium | WORM storage, SHA-256 hash chain, separation of duties | Low |
| P4 | Model produces systematically biased output harming a subgroup | Medium | Medium | Medium | Fairness evaluation per subgroup, drift monitoring, bias disclosures in model card | Medium |
| P5 | Clinician over-reliance on model output (automation bias) | Medium | High | High | UI design avoids anchoring; confidence shown as calibrated probability; disagreement workflow | Medium |
| P6 | Model output used beyond intended purpose (scope creep) | Medium | Medium | Medium | Model card enumerates intended use; DPA restricts; annual re-review | Low |
| P7 | Adversarial image manipulation to flip classification | Low | Medium | Low | Input quality gating; conformal prediction flags out-of-distribution | Low |
| P8 | Data leak during incident response | Low | High | Medium | Incident procedure requires pseudonymised-only data sharing with vendor | Low |
| P9 | Cross-border transfer of personal data outside EEA | Low | Medium | Low | Default architecture avoids transfer; if unavoidable, SCCs + supplementary measures | Low |
| P10 | Lack of individual awareness that AI is involved | Medium | Low | Low | Consent form updated; clinician informs patient; public-facing notice at deployment site | Low |
| P11 | Inability to exercise data subject rights because hospital is the controller | Low | Medium | Low | DPA defines processor assistance; request routing documented | Low |
| P12 | Retention exceeds necessity | Low | Medium | Low | Retention schedule enforced; automated deletion | Low |

## 7. Measures to address risks

### 7.1 Technical measures

Matched to risks above.

- Pseudonymisation at ingestion (`../dicom/anonymizer.py`)
- End-to-end encryption in transit (TLS 1.2+) and at rest (AES-256-GCM at hospital storage layer)
- RBAC and OIDC authentication (`../access/`)
- Audit logging (`../audit/`) with tamper detection
- Input quality gating and out-of-distribution detection
- Conformal prediction intervals for uncertainty quantification
- Automated deletion per retention policy

### 7.2 Organisational measures

- DPA / BAA in place before go-live
- Training of clinicians on model use, limitations, and disagreement workflow
- DPIA review annually and on material change
- Incident response drill quarterly
- Privacy Officer / DPO review of any new data source before onboarding
- Patient information leaflet updated with AI disclosure

### 7.3 Model-specific measures

- Periodic fairness re-evaluation per subgroup (`../governance/fairness-evaluation.md`)
- Drift monitoring and alerting (`../docs/clinical/drift-monitoring.md`)
- Change control (`../docs/clinical/change-control.md`) requires re-validation before any model update
- Shadow-mode deployment for any new version before live routing

## 8. Residual risk acceptance

The residual risk profile, after application of mitigations, is judged acceptable by the Controller. The DPIA is a living document and will be re-evaluated:

- Annually on calendar cadence
- On any material change to model or architecture
- On any change to data flow or processor
- On any breach incident

## 9. Signatures

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Data Protection Officer | | | |
| Controller representative | | | |
| Processor representative | | | |
| Clinical sponsor | | | |

## 10. Appendix — Article 35(7) checklist

GDPR Article 35(7) requires DPIA to contain at least:

- [x] Description of envisaged processing operations and purposes — §2, §4
- [x] Assessment of necessity and proportionality — §4
- [x] Risks to rights and freedoms of data subjects — §6
- [x] Measures envisaged to address risks, safeguards — §7

## 11. Annex — Consent and transparency text

Suggested patient-facing text (to be localised):

> "As part of your eye examination, a fundus photograph may be reviewed by a clinician with the assistance of a computer program that highlights image regions and suggests possible findings. The program is a decision-support tool — your clinician makes the final decision about your care. Your image is processed in a de-identified form; no commercial use or external sharing occurs without your specific consent. You may ask for your image to be read without computer assistance; this will not affect your care."

## 12. Cross-references

- `hipaa-mapping.md` — US counterpart controls
- `phi-handling.md` — data flow detail
- `fda-samd-considerations.md` — US regulatory framing
- `mdr-ce-considerations.md` — EU medical device framing
- `../risk/fmea.md` — detailed risk register
- `../docs/clinical/incident-response.md` — breach response
- `../audit/retention_policy.md` — retention schedule
