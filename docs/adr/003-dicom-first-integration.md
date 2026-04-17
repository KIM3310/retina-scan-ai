# ADR 003: DICOM-first integration

- **Status**: Accepted
- **Date**: 2026-04-17

## Context

Hospitals store and exchange medical imagery via DICOM (Digital Imaging and Communications in Medicine). Fundus cameras produce DICOM outputs natively. The retinal classification service can ingest images via:

1. DICOM (C-STORE SCP listener accepting pushes from PACS).
2. HTTP uploads (multipart form data).
3. S3/Object-store pulls.
4. HL7-FHIR DiagnosticReport with embedded imagery.
5. Direct integration into a DICOM viewer (Cornerstone.js hook).

## Decision

**DICOM is the primary ingestion path**. HTTP uploads and S3/Object-store pulls are supported as secondary paths for non-DICOM environments. HL7-FHIR and direct viewer integration are deferred.

## Consequences

### Positive

- **Native to hospital workflow**: hospitals already route fundus images via DICOM; the service integrates without requiring workflow change.
- **Preserves metadata**: DICOM tags carry patient ID, study UID, series UID, acquisition parameters, camera model — all useful for audit and drift monitoring.
- **Standard protocol**: C-STORE is well-understood by hospital IT. Onboarding a new customer involves allow-listing the SCP endpoint, not building a new integration.
- **Routing to PACS via GSPS**: the service can return Grad-CAM overlays as DICOM GSPS objects, visible in the radiologist's normal PACS viewer without special software.
- **Anonymization pipeline is DICOM-native**: pydicom provides clean access to tags; de-identification is a well-defined operation per DICOM PS3.15.

### Negative

- **Implementation complexity**: DICOM networking (C-ECHO, C-STORE, C-FIND, C-MOVE) is non-trivial to implement correctly. We use `pynetdicom` to mitigate.
- **Hospital network requirements**: DICOM traffic is typically on port 11112, requires firewall rules and often VPN access. Onboarding adds network-engineering work.
- **Ungradeable image filtering**: DICOM may deliver low-quality or wrong-modality images (e.g., OCT instead of fundus). Requires a gradeability check before inference.
- **Versioning complexity**: DICOM has multiple versions and transfer syntaxes. Supporting JPEG Baseline + Lossless + JPEG 2000 requires careful testing.

### Mitigations

- **Clear modality filtering**: the SCP listener rejects non-fundus modalities (SOP Class UID != Ophthalmic Photography).
- **Gradeability classifier before inference**: filters low-quality images.
- **Testing with DICOM test suites**: dcm4che's test vectors cover common transfer syntaxes.
- **Onboarding runbook**: documented network requirements, firewall rules, DICOM AE title configuration.

## Alternatives considered

### HTTP uploads (as primary)

Rejected as primary: requires hospitals to build a custom HTTP integration, disrupting their DICOM-native workflow. Retained as secondary for environments where DICOM is unavailable (e.g., research deployments from static image libraries).

### S3/Object-store pulls (as primary)

Rejected as primary: requires hospitals to push images to a cloud bucket, which raises PHI-handling concerns and adds steps. Retained as secondary for cloud-native deployments where DICOM routing is already S3-backed.

### HL7-FHIR DiagnosticReport

Deferred. FHIR is the future of clinical data exchange, but FHIR imaging support (ImagingStudy, Binary) is still thin in hospital deployments. Revisit in 2-3 years.

### Direct DICOM viewer integration

Deferred. Requires building a Cornerstone.js plugin or OHIF extension. Useful for inline use in the radiologist's reading workflow, but out of scope for a prototype.

## How this constrains future work

- **Scalability**: DICOM C-STORE is connection-oriented. Under high load, we need connection pooling or batching. Design for this in `dicom/scp_listener.py`.
- **Non-DICOM environments**: the HTTP upload path remains simpler and is recommended for non-hospital pilots.
- **Global deployment**: DICOM is widely adopted but implementation varies. Each new hospital customer gets a DICOM conformance-statement review.

## Implementation notes

- SCP listener: `dicom/scp_listener.py`, binds configurable port (default 11112).
- Anonymization: `dicom/anonymizer.py`, implements DICOM PS3.15 Annex E Basic Application Confidentiality Profile.
- GSPS overlay: `dicom/gsps_generator.py`, produces GSPS objects with Grad-CAM heatmap as a Graphic Annotation.
- Audit: `dicom/audit_logger.py` emits audit events for every DICOM operation.

## References

- DICOM Standard: https://www.dicomstandard.org/current
- DICOM PS3.15 Annex E (Basic Application Confidentiality Profile): https://dicom.nema.org/medical/dicom/current/output/html/part15.html
- pynetdicom: https://pydicom.github.io/pynetdicom/
- SOP Class UID for Ophthalmic Photography: 1.2.840.10008.5.1.4.1.1.77.1.5.1 (8-bit) and others.
- GSPS (Grayscale Softcopy Presentation State): DICOM PS3.3 §A.33.4.
