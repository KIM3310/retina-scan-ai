# HIPAA Security Rule Mapping

> **Educational reference only.** A production deployment requires a written risk analysis under 45 CFR § 164.308(a)(1)(ii)(A), a signed Business Associate Agreement (BAA) with every Covered Entity, and a formal Security Management Process. This file describes the *technical scaffolding* Retina Scan AI provides in support of those obligations — it does not, by itself, make a deployment compliant.

## Scope

This document maps the HIPAA Security Rule (45 CFR Part 164 Subpart C) to controls implemented in Retina Scan AI. Required implementation specifications ("Required") must be implemented as stated. Addressable specifications ("Addressable") must be implemented if reasonable and appropriate given the entity's environment; if not, an equivalent measure plus written justification must be documented.

Retinal fundus images combined with a 18 HIPAA identifier (Patient ID, date of birth, medical record number, etc.) constitute **Protected Health Information (PHI)**. Once images are de-identified under § 164.514 (Safe Harbor method) or Expert Determination, they fall outside HIPAA — but biometric linkage via retinal vasculature remains a residual re-identification risk that is documented separately in [`phi-handling.md`](phi-handling.md).

## Role of Retina Scan AI

For most deployment patterns, Retina Scan AI operates as a **Business Associate** to a Covered Entity hospital or clinic. The hospital is the Covered Entity; we receive PHI (DICOM images plus linkable identifiers) to perform a service (classification + Grad-CAM). A Business Associate Agreement (BAA) per § 164.504(e) is required before PHI is exchanged.

Where the deployment is as an on-premise service inside the hospital firewall with no data leaving the hospital network, the hospital remains the Covered Entity and Retina Scan AI is a software component used by that Covered Entity's workforce; a BAA is not required but the Security Rule obligations still apply to the deployment environment.

## Mapping tables

Legend for "Status":
- **Implemented** — the repository provides working technical controls
- **Scaffolded** — documented design and stub/reference implementation, production hardening required
- **Operational** — outside the software boundary; the deploying organisation must operationalise
- **Guidance** — the repository provides written guidance that informs operational controls

### § 164.308 — Administrative Safeguards

| Rule | Requirement | This Repo's Approach | Evidence | Status |
|------|-------------|----------------------|----------|--------|
| § 164.308(a)(1)(i) | Security Management Process — implement policies and procedures to prevent, detect, contain, correct security violations | Risk management process documented per ISO 14971; FMEA at `risk/fmea.md`; incident response at `docs/clinical/incident-response.md` | `risk/iso14971-mapping.md`, `docs/clinical/incident-response.md` | Scaffolded |
| § 164.308(a)(1)(ii)(A) — Required | Risk Analysis | FMEA + ISO 14971 risk analysis template covers information-security risks as a subset of overall patient-safety risks | `risk/fmea.md`, `risk/iso14971-mapping.md` | Scaffolded |
| § 164.308(a)(1)(ii)(B) — Required | Risk Management | Mitigations assigned per failure mode with RPN tracking | `risk/fmea.md` (Mitigation column) | Scaffolded |
| § 164.308(a)(1)(ii)(C) — Required | Sanction Policy | Template policy requires deploying organisation to adopt; audit log supports enforcement | `access/mfa-policy.md` (break-glass section) | Operational |
| § 164.308(a)(1)(ii)(D) — Required | Information System Activity Review | Structured audit logs searchable by user, patient, and event type | `audit/logger.py`, `audit/search_tools.py` | Implemented |
| § 164.308(a)(2) — Required | Assigned Security Responsibility | Role template requires deploying organisation to designate a Security Official | `access/roles.py` (Admin role) | Operational |
| § 164.308(a)(3)(i) | Workforce Security | RBAC with clinical roles (Radiologist, Technician, Admin, Researcher) | `access/roles.py` | Implemented |
| § 164.308(a)(3)(ii)(A) — Addressable | Authorization and/or Supervision | Role-permission matrix; admin role required for user provisioning | `access/roles.py` (permission matrix) | Implemented |
| § 164.308(a)(3)(ii)(B) — Addressable | Workforce Clearance Procedure | Operational; deploying organisation responsibility | N/A | Operational |
| § 164.308(a)(3)(ii)(C) — Addressable | Termination Procedures | OIDC integration supports immediate deactivation via hospital IdP | `access/oidc_integration.py` | Implemented |
| § 164.308(a)(4)(i) | Information Access Management | RBAC, OIDC, least-privilege by default | `access/roles.py`, `access/oidc_integration.py` | Implemented |
| § 164.308(a)(4)(ii)(A) — Required (for health plans) | Isolating Health Care Clearinghouse Functions | Not applicable — Retina Scan AI is not a clearinghouse | N/A | N/A |
| § 164.308(a)(4)(ii)(B) — Addressable | Access Authorization | Role-based default-deny; privileged actions gated by role | `access/roles.py` | Implemented |
| § 164.308(a)(4)(ii)(C) — Addressable | Access Establishment and Modification | OIDC claim-driven role assignment; audit log of all changes | `access/oidc_integration.py`, `audit/logger.py` | Implemented |
| § 164.308(a)(5)(i) | Security Awareness and Training | Training materials pointer — operational responsibility | `access/mfa-policy.md` | Guidance |
| § 164.308(a)(5)(ii)(A) — Addressable | Security Reminders | Operational | N/A | Operational |
| § 164.308(a)(5)(ii)(B) — Addressable | Protection from Malicious Software | Container image scanning in CI (documented); runtime file integrity; read-only model artifacts | `docs/clinical/deployment-architecture.md` | Guidance |
| § 164.308(a)(5)(ii)(C) — Addressable | Log-in Monitoring | Failed login, lockout threshold logged as audit events | `audit/logger.py` (`AUTHN_FAILURE` event) | Implemented |
| § 164.308(a)(5)(ii)(D) — Addressable | Password Management | Delegated to OIDC IdP; never stores passwords | `access/oidc_integration.py`, `access/mfa-policy.md` | Implemented |
| § 164.308(a)(6)(i) | Security Incident Procedures | Incident response playbook | `docs/clinical/incident-response.md` | Scaffolded |
| § 164.308(a)(6)(ii) — Required | Response and Reporting | Severity ladder, notification timelines, audit-log evidence preservation | `docs/clinical/incident-response.md` | Scaffolded |
| § 164.308(a)(7)(i) | Contingency Plan | Clinical workflow fallback documented | `docs/clinical/incident-response.md` (fallback section) | Scaffolded |
| § 164.308(a)(7)(ii)(A) — Required | Data Backup Plan | Model artifacts backed up per release; audit log retention on WORM storage | `audit/retention_policy.md` | Guidance |
| § 164.308(a)(7)(ii)(B) — Required | Disaster Recovery Plan | Documented; hospital DR infrastructure carries runtime | `docs/clinical/deployment-architecture.md` | Guidance |
| § 164.308(a)(7)(ii)(C) — Required | Emergency Mode Operation Plan | Break-glass procedure permits identity-bypass for emergencies with mandatory post-hoc review | `access/mfa-policy.md` (break-glass) | Scaffolded |
| § 164.308(a)(7)(ii)(D) — Addressable | Testing and Revision Procedures | DR drill frequency recommended in retention policy | `audit/retention_policy.md` | Guidance |
| § 164.308(a)(7)(ii)(E) — Addressable | Applications and Data Criticality Analysis | Criticality documented: Class IIa / high-risk | `compliance/fda-samd-considerations.md`, `compliance/mdr-ce-considerations.md` | Guidance |
| § 164.308(a)(8) — Required | Evaluation | Periodic security evaluation procedure templated | `audit/retention_policy.md` (review cadence) | Guidance |
| § 164.308(b)(1) | Business Associate Contracts | Template BAA pointer — legal review required | `compliance/phi-handling.md` (BAA section) | Guidance |
| § 164.308(b)(3) — Required | Written Contract or Other Arrangement | Operational | N/A | Operational |

### § 164.310 — Physical Safeguards

| Rule | Requirement | This Repo's Approach | Evidence | Status |
|------|-------------|----------------------|----------|--------|
| § 164.310(a)(1) | Facility Access Controls | Deployment targets hospital data centre or cloud region already under Covered Entity's physical controls | `docs/clinical/deployment-architecture.md` | Operational |
| § 164.310(a)(2)(i) — Addressable | Contingency Operations | Operational | N/A | Operational |
| § 164.310(a)(2)(ii) — Addressable | Facility Security Plan | Operational | N/A | Operational |
| § 164.310(a)(2)(iii) — Addressable | Access Control and Validation Procedures | Operational | N/A | Operational |
| § 164.310(a)(2)(iv) — Addressable | Maintenance Records | Operational | N/A | Operational |
| § 164.310(b) — Required | Workstation Use | Viewer workstations run inside hospital network; no direct workstation-to-internet path in reference architecture | `docs/clinical/deployment-architecture.md` (DMZ section) | Guidance |
| § 164.310(c) — Required | Workstation Security | Operational | N/A | Operational |
| § 164.310(d)(1) | Device and Media Controls | All on-disk data encrypted at rest; tmpfs for transient DICOM receive buffer | `docs/clinical/deployment-architecture.md` (storage section) | Scaffolded |
| § 164.310(d)(2)(i) — Required | Disposal | Operational: hospital media destruction procedure | N/A | Operational |
| § 164.310(d)(2)(ii) — Required | Media Re-use | Operational | N/A | Operational |
| § 164.310(d)(2)(iii) — Addressable | Accountability | Asset register template | `docs/clinical/deployment-architecture.md` | Guidance |
| § 164.310(d)(2)(iv) — Addressable | Data Backup and Storage | See § 164.308(a)(7)(ii)(A) | `audit/retention_policy.md` | Guidance |

### § 164.312 — Technical Safeguards

| Rule | Requirement | This Repo's Approach | Evidence | Status |
|------|-------------|----------------------|----------|--------|
| § 164.312(a)(1) | Access Control | RBAC enforced at API layer with role-permission matrix | `access/roles.py` | Implemented |
| § 164.312(a)(2)(i) — Required | Unique User Identification | OIDC `sub` claim used as stable principal ID; never shared accounts | `access/oidc_integration.py` | Implemented |
| § 164.312(a)(2)(ii) — Required | Emergency Access Procedure | Break-glass role with mandatory audit trail and post-hoc review | `access/mfa-policy.md` (break-glass) | Implemented |
| § 164.312(a)(2)(iii) — Addressable | Automatic Logoff | Session timeout configured at IdP; default 15 minutes idle | `access/mfa-policy.md` (session section) | Scaffolded |
| § 164.312(a)(2)(iv) — Addressable | Encryption and Decryption | TLS 1.2+ for transit; AES-256-GCM for data at rest (hospital storage layer) | `docs/clinical/deployment-architecture.md` (encryption section) | Scaffolded |
| § 164.312(b) — Required | Audit Controls | Structured JSON audit log with user, patient, action, timestamp, outcome, source IP | `audit/logger.py` | Implemented |
| § 164.312(c)(1) | Integrity | Audit log append-only via WORM storage; SHA-256 hash chain | `audit/logger.py`, `audit/retention_policy.md` | Scaffolded |
| § 164.312(c)(2) — Addressable | Mechanism to Authenticate Electronic PHI | Hash chain detects tampering of audit records; input image SHA-256 recorded per inference | `audit/logger.py` | Implemented |
| § 164.312(d) — Required | Person or Entity Authentication | Delegated to hospital IdP via OIDC; supports SAML for legacy | `access/oidc_integration.py` | Implemented |
| § 164.312(e)(1) | Transmission Security | TLS 1.2+ enforced; DICOM TLS (DICOM PS3.15) or IPSec tunnel for PACS link | `dicom/scp_listener.py`, `docs/clinical/deployment-architecture.md` | Scaffolded |
| § 164.312(e)(2)(i) — Addressable | Integrity Controls | HMAC on inter-service calls; DICOM association AE Title + called/calling check | `dicom/scp_listener.py` | Scaffolded |
| § 164.312(e)(2)(ii) — Addressable | Encryption | TLS 1.2+ everywhere; mTLS between internal services | `docs/clinical/deployment-architecture.md` | Scaffolded |

### § 164.314 — Organisational Requirements

| Rule | Requirement | This Repo's Approach | Evidence | Status |
|------|-------------|----------------------|----------|--------|
| § 164.314(a)(1) | Business Associate Contracts | BAA template pointer | `compliance/phi-handling.md` | Guidance |
| § 164.314(a)(2)(i)(A) — Required | BAA — Permitted Uses | Use-bound to classification service described in model card | `governance/model-card.md` (Intended Use) | Guidance |
| § 164.314(a)(2)(i)(B) — Required | BAA — Safeguards | This mapping document itself is the evidence | This file | Implemented |
| § 164.314(a)(2)(i)(C) — Required | BAA — Subcontractor flow-down | Listed in BAA template; any cloud infra must have its own BAA | `compliance/phi-handling.md` | Operational |
| § 164.314(a)(2)(i)(D) — Required | BAA — Reporting of breaches | Incident response playbook defines notification path and timelines | `docs/clinical/incident-response.md` | Scaffolded |
| § 164.314(b) | Group Health Plan requirements | Not applicable | N/A | N/A |

### § 164.316 — Policies and Procedures, and Documentation

| Rule | Requirement | This Repo's Approach | Evidence | Status |
|------|-------------|----------------------|----------|--------|
| § 164.316(a) | Policies and Procedures | Policies templated in `access/`, `audit/`, `compliance/`, `risk/` | Repository structure | Scaffolded |
| § 164.316(b)(1) — Required | Documentation | All policies, risk assessments, and audit records retained electronically | `audit/retention_policy.md` | Scaffolded |
| § 164.316(b)(2)(i) — Required | Retention — 6 years | 7-year retention adopted to exceed HIPAA minimum and align with hospital norms | `audit/retention_policy.md` | Implemented |
| § 164.316(b)(2)(ii) — Required | Availability | Search-tools script, quarterly restore drills recommended | `audit/search_tools.py` | Implemented |
| § 164.316(b)(2)(iii) — Required | Updates | Annual policy review cadence documented | `audit/retention_policy.md` | Guidance |

## Breach Notification Rule (§§ 164.400–164.414) considerations

A breach of unsecured PHI that compromises the security or privacy of PHI triggers HHS notification obligations. Retina Scan AI supports breach detection and evidence preservation via:

- **Detection** — Audit log tamper detection via hash chain; anomaly alerting on access patterns
- **Investigation** — `audit/search_tools.py` supports per-patient and per-user forensic queries
- **Reporting** — Incident playbook defines the notification timer (60 days for HHS per § 164.408, without unreasonable delay)
- **Risk of compromise assessment** — FMEA RPN score for the triggering failure mode guides the § 164.402 four-factor analysis

## Privacy Rule adjacency

This file focuses on the Security Rule. The Privacy Rule's Minimum Necessary standard (§ 164.502(b)) shapes the API surface: the `/predict` endpoint returns class probabilities and Grad-CAM only, never echoes back PHI fields from the incoming DICOM header. The anonymizer (`dicom/anonymizer.py`) strips all 18 Safe Harbor identifiers before any artifact leaves the trust boundary.

## What is **not** covered

- State-level privacy laws (Texas HB 300, California CMIA, etc.)
- Substance-use disorder records under 42 CFR Part 2 (not implicated by retinal imaging)
- Research-use subject protections under 45 CFR Part 46 (applies when the service is used in IRB-approved research)
- Accessibility (Section 508) — covered in usability design docs

## Revision history

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-04 | Initial mapping |
