# PHI / Personal Data Handling

> **Educational reference only.** Deployment requires a privacy impact assessment signed off by a qualified Privacy Officer and a Business Associate Agreement with every Covered Entity when operating as a Business Associate.

## 1. Data classification

| Data element | HIPAA status | GDPR status | Flow through Retina Scan AI |
|--------------|-------------|-------------|----------------------------|
| Patient Name (DICOM 0010,0010) | PHI direct identifier (18 identifiers: name) | Personal data; identifies a natural person | Stripped by anonymizer before inference |
| Patient ID / MRN (0010,0020) | PHI direct identifier | Personal data | Pseudonymised to SHA-256 salted hash; mapping held only in hospital boundary |
| Date of Birth (0010,0030) | PHI — dates | Personal data | Replaced with decade-only category |
| Full DOB, dates of service, admission, discharge | PHI — dates | Personal data | Year-only retention for dates; zero-day anchoring |
| Full-face photographic and comparable images | PHI — full face image | Biometric data (special category) | Not applicable — fundus images only |
| Biometric identifiers including finger and voice prints | PHI | Biometric data (GDPR Art. 9) | Retinal vasculature is potentially biometric — see §4 residual risk |
| Fundus image pixels (de-identified) | Not PHI after header anonymisation — subject to re-identification risk | Non-special category once pseudonymised; special category while linkable | Processed by model |
| Class probabilities (model output) | Health data about the patient if linkable | Health data (Art. 9) if linkable | Returned only to authorised clinical user |
| Grad-CAM heatmap | Derivative of model output | Derivative health data | Returned only to authorised clinical user |

## 2. De-identification approaches

HIPAA § 164.514 provides two methods:

### 2.1 Safe Harbor (§ 164.514(b)(2))

Remove all 18 specified identifiers. Retina Scan AI's DICOM anonymizer (`../dicom/anonymizer.py`) implements Safe Harbor on DICOM metadata per **DICOM PS3.15 Annex E Basic Profile**, addressing each identifier:

| # | HIPAA Identifier | DICOM tag(s) | Anonymizer action |
|---|------------------|--------------|-------------------|
| 1 | Names | (0010,0010) PatientName, (0008,0090) ReferringPhysicianName, (0008,1050) PerformingPhysicianName, (0008,1060) NameOfPhysiciansReadingStudy, (0040,A075) VerifyingObserverName | Replaced with empty DICOM PN VR |
| 2 | Geographic subdivisions smaller than state | (0010,1040) PatientAddress, institutional (0008,0080) InstitutionName, (0008,0081) InstitutionAddress | Stripped |
| 3 | All elements of dates (except year) directly related to an individual | (0010,0030) PatientBirthDate, (0008,0020) StudyDate, (0008,0030) StudyTime, (0008,0022) AcquisitionDate, etc. | Year-only; day/month zeroed |
| 4 | Telephone numbers | (0010,2154) PatientTelephoneNumbers | Stripped |
| 5 | Fax numbers | — | Stripped where present |
| 6 | Electronic mail addresses | — | Stripped where present |
| 7 | Social security numbers | (0010,2160) EthnicGroup rarely — checked | Stripped where present |
| 8 | Medical record numbers | (0010,0020) PatientID | Pseudonymised |
| 9 | Health plan beneficiary numbers | (0010,1000) OtherPatientIDs | Stripped |
| 10 | Account numbers | (0008,0050) AccessionNumber | Pseudonymised |
| 11 | Certificate/license numbers | — | Stripped |
| 12 | Vehicle identifiers | — | Stripped |
| 13 | Device identifiers and serial numbers | (0018,1000) DeviceSerialNumber | Stripped |
| 14 | Web URLs | — | Stripped |
| 15 | IP addresses | (0008,0054) RetrieveAETitle, private tags containing IPs | Stripped |
| 16 | Biometric identifiers | — | See §4 residual risk |
| 17 | Full face photographs | — | Not applicable |
| 18 | Any other unique identifying number, characteristic, or code | All private tags | Private tags entirely removed (DICOM PS3.15 Annex E Basic Profile baseline) |

### 2.2 Expert Determination (§ 164.514(b)(1))

A statistical or scientific expert can certify that the risk of re-identification is very small. This is a heavier lift but allows retention of more data (e.g. full dates) if necessary for the model. Retina Scan AI defaults to Safe Harbor for simplicity; Expert Determination is documented as a future option.

## 3. Under GDPR — pseudonymisation vs anonymisation

GDPR Recital 26 distinguishes:
- **Anonymisation** — data that cannot be linked to an identifiable person by any means "reasonably likely to be used" — falls outside GDPR scope
- **Pseudonymisation** — reversible with a key held separately — still personal data, still GDPR-covered, but reduces risk

Retina Scan AI performs **pseudonymisation** at the hospital boundary. The true anonymisation threshold is higher because fundus vasculature is biometric enough to support re-identification with another fundus image of the same eye — see §4.

## 4. Residual biometric re-identification risk

Retinal vasculature is unique to each person and approximately stable over decades. Published research has demonstrated the feasibility of re-identification from fundus image pairs with high accuracy. This means that even after stripping all header identifiers, a fundus image paired with any other identified fundus image of the same person can re-identify the subject.

Mitigations adopted:
- **Retain pseudonymisation in addition to DICOM header strip** — fundus images never leave the hospital trust boundary as bare pixel arrays; they travel with a pseudonymised ID that allows audit linkage inside the boundary only
- **No external publication of fundus pixels** without institutional consent and appropriate consent framework (research) or Expert Determination
- **Disclose biometric character** — explicitly to patients during consent per GDPR Art. 9 standards
- **Treat as biometric data** for GDPR Art. 9 purposes even after pseudonymisation, to err on side of higher protection

## 5. Data flow diagram

```
Fundus camera
    │
    │ DICOM C-STORE (TLS)
    ▼
Hospital PACS                      [Hospital trust boundary]
    │
    │ DICOM C-STORE (TLS, internal)
    ▼
Retina Scan AI SCP listener ─► Anonymizer ─► Staging (tmpfs)
                                 │                │
                                 │                ▼
                                 │            Inference (model)
                                 │                │
                                 │                ▼
                                 │            Grad-CAM
                                 │                │
                                 │                ▼
                                 │            GSPS object
                                 │                │
                                 ▼                │
                              Audit log ◄─────────┘
                                 │
                                 │ TLS
                                 ▼
                          PACS (GSPS archived alongside study)
                                 │
                                 ▼
                          Clinician viewer (no pixel data crosses hospital firewall outbound)
```

Hospital trust boundary: The service is deployed inside the hospital network. No pixel data or linkable header data crosses the hospital firewall outbound in the reference architecture. If a cloud deployment is chosen, a BAA and associated architecture controls described in `../docs/clinical/deployment-architecture.md` apply.

## 6. Business Associate Agreement (BAA) template checklist

When operating as a Business Associate, the BAA must include (per 45 CFR § 164.504(e)):

- [ ] Description of permitted and required uses/disclosures of PHI
- [ ] Not to use or disclose PHI other than as permitted or as required by law
- [ ] Use appropriate safeguards (§ 164.308 + § 164.312) — this repo's mapping
- [ ] Report breaches and Security Incidents to the Covered Entity
- [ ] Ensure subcontractors agree to same restrictions
- [ ] Make PHI available to individuals as required under § 164.524
- [ ] Make PHI available for amendment per § 164.526
- [ ] Make disclosures tracking available per § 164.528
- [ ] Make internal practices, books, and records available to HHS for compliance determination
- [ ] At termination, return or destroy all PHI; extend protections to retained PHI
- [ ] Authorise termination by Covered Entity for material breach

## 7. International transfer considerations

Under GDPR Chapter V, transfers of personal data outside the EEA require a legal basis (adequacy decision, SCCs, BCRs). Fundus data transfer to a US cloud region requires Standard Contractual Clauses (2021 version) plus supplementary measures per Schrems II, or reliance on the EU-US Data Privacy Framework where the recipient is certified.

Default deployment pattern avoids international transfer by keeping processing inside the hospital boundary.

## 8. Data subject rights

Under GDPR Articles 15–22:

| Right | How Retina Scan AI supports |
|-------|----------------------------|
| Access (Art. 15) | Audit log searchable by pseudonymised patient ID; hospital maps back to identified patient and responds |
| Rectification (Art. 16) | Model does not store identified personal data; rectification is at the source PACS |
| Erasure (Art. 17) | On request, all pseudonymised records for a given hash can be deleted from staging and audit per retention policy |
| Restriction (Art. 18) | Access to inference results can be restricted per-record via access control list |
| Portability (Art. 20) | Inference results and Grad-CAM can be exported in standard formats (GSPS, JSON) |
| Object (Art. 21) | Patient-level block list prevents processing of specific pseudonymised IDs |
| Automated decision-making (Art. 22) | Model output is decision-support, not autonomous decision; clinician oversight per `../docs/clinical/clinician-in-the-loop.md` makes Art. 22 non-applicable |

## 9. Retention

See [`../audit/retention_policy.md`](../audit/retention_policy.md).

Summary:
- Audit logs: 7 years (exceeds HIPAA 6-year minimum)
- Model inference results linked to pseudonymised ID: 90 days in staging, then archived only if attached to a clinical record at the hospital's storage
- Inference staging pixel data: retained no longer than necessary for QA — default 48 hours, configurable
- De-identified aggregated performance statistics: indefinite

## 10. Breach response

Cross-referenced to [`../docs/clinical/incident-response.md`](../docs/clinical/incident-response.md).

HIPAA Breach Notification thresholds:
- Breach affecting 500+ individuals — notify HHS Secretary and prominent media within 60 days of discovery
- Breach affecting <500 individuals — log and report annually

GDPR thresholds:
- Supervisory authority: 72 hours if risk to rights and freedoms
- Data subjects: without undue delay if high risk

## 11. Processor vs Controller

Under GDPR:
- **Controller**: the hospital determines purposes and means
- **Processor**: Retina Scan AI processes on behalf of the hospital
- Article 28 Data Processing Agreement (DPA) required, analogous to HIPAA BAA

Recommended DPA clauses align with BAA checklist in §6, plus:
- Sub-processor flow-through per Art. 28(4)
- International transfer provisions per Chapter V
- Security measures reference (Art. 32)
- Assistance to controller for DPIA, data subject requests, breach
- Audit rights
