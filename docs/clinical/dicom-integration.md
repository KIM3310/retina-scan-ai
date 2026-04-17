# DICOM Integration

## 1. Overview

Retina Scan AI integrates with hospital PACS/VNA infrastructure using the DICOM (Digital Imaging and Communications in Medicine) standard. The service acts as:

- **SCP (Service Class Provider)** — accepts C-STORE associations from the PACS, receiving fundus images for inference
- **SCU (Service Class User)** — sends Grayscale Softcopy Presentation State (GSPS) objects containing the Grad-CAM overlay back to the PACS for viewing alongside the original study

Reference implementation is in [`../../dicom/`](../../dicom/).

## 2. SOP Classes supported

### 2.1 Inbound (SCP)

| SOP Class Name | SOP Class UID | Role |
|----------------|---------------|------|
| Ophthalmic Photography 8 Bit Image Storage | 1.2.840.10008.5.1.4.1.1.77.1.5.1 | Primary format for fundus cameras |
| Ophthalmic Photography 16 Bit Image Storage | 1.2.840.10008.5.1.4.1.1.77.1.5.2 | Higher bit-depth fundus imagery |
| VL Photographic Image Storage | 1.2.840.10008.5.1.4.1.1.77.1.4 | General visible light photography — used by some fundus cameras |
| Ophthalmic Tomography Image Storage | 1.2.840.10008.5.1.4.1.1.77.1.5.4 | OCT — not currently classified; received but not routed to model |
| Secondary Capture Image Storage | 1.2.840.10008.5.1.4.1.1.7 | Legacy fundus workflows that emit SC instead of OP |

### 2.2 Outbound (SCU)

| SOP Class Name | SOP Class UID | Purpose |
|----------------|---------------|---------|
| Grayscale Softcopy Presentation State Storage | 1.2.840.10008.5.1.4.1.1.11.1 | Overlay with Grad-CAM visualisation |
| Encapsulated PDF Storage | 1.2.840.10008.5.1.4.1.1.104.1 | Human-readable report with class probabilities (optional) |
| Structured Report — Enhanced SR | 1.2.840.10008.5.1.4.1.1.88.22 | Machine-readable report for downstream consumers (optional) |

## 3. Transfer syntaxes negotiated

Inbound:
- Explicit VR Little Endian (1.2.840.10008.1.2.1) — preferred
- Implicit VR Little Endian (1.2.840.10008.1.2) — fallback
- JPEG Lossless (1.2.840.10008.1.2.4.70) — where source emits compressed

Outbound:
- Explicit VR Little Endian for GSPS

## 4. Association negotiation

- **Called AE Title**: Configurable; default `RETINASCAN`
- **Calling AE Title**: Whitelist of permitted source AE titles (PACS routing AE, fundus modality AE)
- **Max PDU Size**: 16384 bytes by default; negotiable to PACS preference
- **Extended Negotiation**: Not required; standard association sufficient

Association failures are logged with reason codes per DICOM PS3.8.

## 5. Anonymisation — DICOM PS3.15 Annex E Basic Profile

Upon receipt, every DICOM instance passes through the anonymizer (`../../dicom/anonymizer.py`) before reaching the staging area. The implementation follows DICOM PS3.15 Annex E Basic Application Level Confidentiality Profile as a baseline, with additional HIPAA Safe Harbor identifiers removed.

Key tags handled:

| Tag | Name | VR | Action | Rationale |
|-----|------|----|--------|-----------|
| (0008,0018) | SOPInstanceUID | UI | Replace with new UID | UID remapping |
| (0008,0020) | StudyDate | DA | Year-only (`YYYY0101`) | HIPAA dates |
| (0008,0021) | SeriesDate | DA | Year-only | HIPAA dates |
| (0008,0022) | AcquisitionDate | DA | Year-only | HIPAA dates |
| (0008,0023) | ContentDate | DA | Year-only | HIPAA dates |
| (0008,0030) | StudyTime | TM | `000000.000000` | HIPAA |
| (0008,0050) | AccessionNumber | SH | Pseudonymise | Linkable |
| (0008,0080) | InstitutionName | LO | Remove | Identifies < state |
| (0008,0081) | InstitutionAddress | ST | Remove | Identifies < state |
| (0008,0090) | ReferringPhysicianName | PN | Empty | HIPAA names |
| (0008,0092) | ReferringPhysicianAddress | ST | Remove | Identifies < state |
| (0008,0094) | ReferringPhysicianTelephoneNumbers | SH | Remove | HIPAA phone |
| (0008,1010) | StationName | SH | Remove | Device ID |
| (0008,1030) | StudyDescription | LO | Retain if no PII; monitor | Clinical |
| (0008,103E) | SeriesDescription | LO | Retain | Clinical |
| (0008,1040) | InstitutionalDepartmentName | LO | Remove | Identifiable |
| (0008,1048) | PhysiciansOfRecord | PN | Empty | HIPAA names |
| (0008,1050) | PerformingPhysicianName | PN | Empty | HIPAA names |
| (0008,1060) | NameOfPhysiciansReadingStudy | PN | Empty | HIPAA names |
| (0008,1070) | OperatorsName | PN | Empty | HIPAA names |
| (0010,0010) | PatientName | PN | Empty | HIPAA names |
| (0010,0020) | PatientID | LO | Pseudonymise (HMAC-SHA256) | Primary linkage |
| (0010,0030) | PatientBirthDate | DA | Decade bucket | HIPAA dates |
| (0010,0040) | PatientSex | CS | Retain (clinically relevant) | Required for fairness eval |
| (0010,1000) | OtherPatientIDs | LO | Remove | Linkable |
| (0010,1001) | OtherPatientNames | PN | Empty | HIPAA names |
| (0010,1010) | PatientAge | AS | Retain (clinically relevant for triage) | Clinical utility |
| (0010,1040) | PatientAddress | LO | Remove | HIPAA geographic < state |
| (0010,2154) | PatientTelephoneNumbers | SH | Remove | HIPAA phone |
| (0010,2160) | EthnicGroup | SH | Retain if present (fairness eval); configurable | Fairness monitoring |
| (0018,1000) | DeviceSerialNumber | LO | Remove | HIPAA device ID |
| (0020,000D) | StudyInstanceUID | UI | Retain mapping (pseudonymised) | Link clinical record |
| (0020,000E) | SeriesInstanceUID | UI | Replace consistent UID | UID remap |
| (0020,0010) | StudyID | SH | Remove | Linkable |
| All private groups | — | — | Remove | May contain PHI |
| Curves, overlays | — | — | Remove unless clinically needed | May contain burned-in PII |

UID remapping uses a site-specific salt so that the same original UID maps to the same new UID consistently within the site (needed for series coherence) but different sites produce different mappings.

**Pixel data burn-in** is checked before acceptance: if (0028,0301) BurnedInAnnotation is `YES`, the image is quarantined rather than processed; burned-in pixels may contain identifiers that header anonymisation cannot remove.

## 6. Grad-CAM as a Grayscale Softcopy Presentation State

The Grad-CAM visualisation is returned as a GSPS object per DICOM PS3.3 section A.33.4, referencing the original image's StudyInstanceUID and SeriesInstanceUID.

Key GSPS attributes used:

| Attribute | Value |
|-----------|-------|
| (0008,0018) SOPInstanceUID | New UID for the presentation state |
| (0008,0016) SOPClassUID | 1.2.840.10008.5.1.4.1.1.11.1 |
| (0008,1115) ReferencedSeriesSequence > (0008,1140) ReferencedImageSequence | References the original fundus image |
| (0070,0001) GraphicAnnotationSequence | Contains the Grad-CAM heatmap as graphic annotations OR as a referenced secondary capture — the repo implementation encodes as referenced SC for vendor interoperability |
| (0070,0080) ContentLabel | `RETINASCAN_GRADCAM` |
| (0070,0081) ContentDescription | `Retina Scan AI — Grad-CAM attention overlay` |
| (0070,0082) PresentationCreationDate | Today |
| (0070,0083) PresentationCreationTime | Current time |
| (0070,0084) ContentCreatorName | `RETINA-SCAN-AI^v<version>` |
| (0028,1052) RescaleIntercept, (0028,1053) RescaleSlope, (0028,1050) WindowCenter, (0028,1051) WindowWidth | Configured for overlay display |

The overlay is represented as a palette-color heatmap that vendor viewers can toggle on and off like any other GSPS. This preserves the radiologist's existing workflow.

## 7. Return path — C-STORE back to PACS

After anonymisation and inference, the GSPS is sent back to the PACS via C-STORE. Importantly, the PACS route is configured to attach the returned GSPS under the **original, non-pseudonymised** StudyInstanceUID — this is only possible because the PACS is inside the same trust boundary and the original→pseudonymised mapping is retained in the hospital-local anonymizer state, never leaving the boundary.

If the deployment pattern does not permit the Retina Scan AI namespace to know the original UID (strict separation), an alternative pattern is used:

1. PACS sends image tagged with a routing-correlation key in a private attribute
2. Anonymizer retains only the correlation key → pseudonymised UID mapping
3. GSPS response includes the same correlation key
4. PACS applies the mapping back to the original study on receipt

## 8. Audit linkage

Every DICOM operation emits an audit event per HIPAA § 164.312(b) via `../../audit/logger.py`:

| Event | Trigger |
|-------|---------|
| `DICOM_ASSOCIATION_OPEN` | SCP accepts new association |
| `DICOM_ASSOCIATION_REJECT` | SCP rejects (auth, whitelist, or association negotiation failure) |
| `DICOM_CSTORE_RECEIVE` | Individual instance received |
| `ANONYMIZATION` | After anonymizer completes, logged with original hashes and new UIDs |
| `INFERENCE` | Model forward pass, class probabilities logged |
| `GSPS_CREATE` | GSPS object created |
| `DICOM_CSTORE_SEND` | GSPS sent to PACS |
| `DICOM_ASSOCIATION_CLOSE` | Association closed |

## 9. Interoperability testing

Before go-live at any site, a DICOM conformance test is executed:

- Connectathon-style round trip with the target PACS
- Test images covering all supported SOP Classes at all supported transfer syntaxes
- Intentional malformed associations to verify reject paths
- Failover and retry behaviour
- Burn-in annotation detection with synthetic test images

A DICOM Conformance Statement is produced per release, describing declared capabilities. This is a deliverable to site integration teams.

## 10. Known constraints

- No RT Structure Set or RT Plan — retinal imaging is not radiotherapy
- Not a DICOM Query/Retrieve SCP — does not perform C-FIND/C-MOVE; images are pushed by PACS routing
- Not a DICOMweb (WADO-RS, STOW-RS) server — considered for a future release
- Not a DIMSE storage commitment SCP — images are treated as ephemeral until GSPS is returned and PACS re-archives

## 11. Error handling

| Error | Handling |
|-------|----------|
| Unsupported SOP Class | Reject association presentation context, log, continue |
| Malformed DICOM instance | Reject instance with appropriate DIMSE status, log, continue |
| Burn-in annotation detected | Quarantine, emit alert to site administrator |
| Anonymisation failure | Quarantine, emit alert, block downstream inference |
| Inference failure | Audit log entry, return error GSPS or none; do not send bad GSPS back |
| PACS C-STORE failure (return path) | Retry with backoff; alert on persistent failure |

## 12. Vendor testing matrix

Integration has been verified (design intent) against representative PACS vendors:

| Vendor | Version | Fundus modality | Notes |
|--------|---------|-----------------|-------|
| Sectra | IDS7 | Topcon NW400, Zeiss Clarus 500 | Confirmed OP 8-bit path |
| Philips IntelliSpace | 4.4 | Canon CR-2 AF, Topcon | Requires transfer syntax negotiation fallback |
| Agfa Enterprise Imaging | 8.2 | Centervue DRS | GSPS rendering verified |
| GE Centricity | 6.x | Various | Configure call/called AE title carefully |
| Open-source (dcm4chee, Orthanc) | recent | Any OP-compliant | Used for CI integration tests |

Vendor-specific quirks (GSPS attribute rendering, transfer syntax preferences) are documented in release notes for each site onboarding.

## 13. Security on the DICOM link

- **DICOM TLS** (DICOM PS3.15) or network-level IPsec tunnel between PACS and Retina Scan AI
- Mutual TLS (mTLS) preferred; the service and the PACS present certificates signed by an internal CA
- AE Title whitelist enforced regardless of TLS — defence in depth
- Association rejected on certificate validation failure with audit trail

## 14. References

- DICOM PS3.3 Information Object Definitions
- DICOM PS3.4 Service Class Specifications
- DICOM PS3.15 Annex E — Basic Application Level Confidentiality Profile
- NEMA PS3.6 — Data Dictionary
- IHE Eye Care Technical Framework (adjacent; fundus workflows)
- `pydicom` project — Python DICOM library used
- `pynetdicom` project — Python DICOM network library used
