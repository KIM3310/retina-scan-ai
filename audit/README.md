# Audit Logging

HIPAA-aligned audit event capture for all significant operations on the retinal classification service.

## Scope

This audit layer implements the technical safeguards of **HIPAA Security Rule §164.312(b) — Audit controls**, which requires:

> Implement hardware, software, and/or procedural mechanisms that record and examine activity in information systems that contain or use electronic protected health information.

Every operation that touches a patient image, classification result, clinician decision, or audit metadata itself is logged to an append-only, tamper-resistant store with a 7-year retention window aligned to HIPAA §164.530(j)(2).

## What is logged

| Event category | Events |
|----------------|--------|
| Access | DICOM study receive, image read, classification result view, audit log read |
| Modify | Clinician override, annotation edit, report edit |
| Delete | Patient record deletion, study purge (with reason code) |
| Authentication | Login success, login failure, MFA challenge, logout |
| Authorization | Role assignment, role removal, break-glass activation |
| Export | Study export, classification batch export, audit extract |
| System | Model version change, policy update, retention purge run |

## Event record schema

Each event is a JSON document with the following required fields:

```json
{
  "event_id": "evt_01HYX...",
  "event_timestamp": "2026-04-17T09:23:45.123456Z",
  "event_type": "access.study_read",
  "actor": {
    "user_id": "u_42",
    "display_name": "Dr. Jane Doe",
    "role": "Radiologist",
    "session_id": "sess_01HY..."
  },
  "subject": {
    "patient_hash": "p_sha256_abc...",
    "study_uid": "1.2.840.113654.2.70.1.102...",
    "series_uid": "1.2.840..."
  },
  "action": "READ",
  "outcome": "SUCCESS",
  "source": {
    "ip": "10.0.12.34",
    "user_agent": "dicom-viewer/3.2.1",
    "device_id": "ws-radiology-04"
  },
  "context": {
    "purpose_of_use": "TREATMENT",
    "consent_reference": "consent_2025_v3",
    "break_glass": false
  },
  "integrity": {
    "prev_hash": "sha256:abcd...",
    "current_hash": "sha256:efgh..."
  }
}
```

## Integrity model

- Events are chained by hash: `current_hash = SHA256(event_json || prev_hash)`.
- Breaks in the hash chain are detectable and raise a compliance alert.
- The audit store is append-only at the application layer and write-once-read-many at the storage layer (S3 Object Lock or equivalent).
- Integrity is verified periodically by `audit/search_tools.py verify-chain`.

## Retention

7-year retention per `retention_policy.md`. Events older than 7 years are automatically deleted after a compliance-officer-approved purge window.

## Access to audit logs

- Clinicians cannot read audit logs.
- Compliance officers read via `search_tools.py` with a dedicated audit-read role.
- Every read of the audit log is itself audited (recursive audit).
- Administrative roles that could modify audit logs are eliminated by the architecture: not even a database admin can mutate a committed event without breaking the hash chain.

## Files

- `logger.py` — the primary logging API used by every service endpoint.
- `retention_policy.md` — retention window rationale, purge process.
- `search_tools.py` — compliance officer tooling for ad-hoc audit queries.

## Integration points

- `src/inference.py` → logs `access.classification_run` on every inference.
- `api/main.py` → logs `access.study_read` on study fetch, `access.result_view` on result fetch.
- `dicom/scp_listener.py` → logs `access.study_receive` on DICOM C-STORE.
- `access/oidc_integration.py` → logs `authentication.*` events.
