# DICOM Integration

This module provides DICOM (Digital Imaging and Communications in Medicine) integration for Retina Scan AI. It contains:

| File | Purpose |
|------|---------|
| [`scp_listener.py`](scp_listener.py) | C-STORE SCP listener (accepts DICOM images from a PACS) |
| [`anonymizer.py`](anonymizer.py) | DICOM de-identification per DICOM PS3.15 Annex E Basic Profile + HIPAA Safe Harbor |
| [`gsps_generator.py`](gsps_generator.py) | Grayscale Softcopy Presentation State generator for Grad-CAM overlays |
| [`audit_logger.py`](audit_logger.py) | Structured audit logging for every DICOM operation |

## Dependencies

- `pydicom` — DICOM file parsing and composition
- `pynetdicom` — DICOM networking (association, C-STORE, C-ECHO)
- `numpy` — array manipulation for GSPS pixel data

These are not currently listed in `requirements.txt` to avoid pulling heavy dependencies for the reference ML pipeline. To enable DICOM integration, install:

```
pip install pydicom pynetdicom
```

## Quick start — launch an SCP listener

```
python -m dicom.scp_listener --ae-title RETINASCAN --port 11112
```

This starts a DICOM SCP on port 11112 accepting C-STORE associations. Received instances are anonymised, staged to a configured directory, and logged via the audit logger. Inference is triggered by a downstream worker in production; the listener itself is narrow by design.

## Architecture

```
PACS ──DICOM C-STORE──► scp_listener
                          │
                          ├──► anonymizer ──► staging
                          │                     │
                          └──► audit_logger    ▼
                                           (inference worker)
                                                │
                                                ▼
                                       gsps_generator
                                                │
                                                └──DICOM C-STORE──► PACS
```

See [`../docs/clinical/dicom-integration.md`](../docs/clinical/dicom-integration.md) for the full integration story, supported SOP classes, anonymisation mapping, and security posture.

## Testing without a PACS

Use the open-source DICOM tools to simulate:

```
# send a test image to the listener
storescu -v -aec RETINASCAN localhost 11112 test.dcm

# verify echo
echoscu -v -aec RETINASCAN localhost 11112
```

Or use the `pynetdicom` `apps` (`storescu`, `echoscu`) included in the `pynetdicom` distribution.

## Disclaimers

- This code is reference / educational. Production use requires integration testing against the target PACS, DICOM conformance statement publication, notified body review if part of a CE-marked device.
- AE title whitelisting, TLS configuration, and PACS-side routing rules are deployment-specific and outside the scope of this repository.
