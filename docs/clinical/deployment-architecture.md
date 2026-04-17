# Clinical Deployment Architecture

> **Educational reference.** This document describes a reference architecture for deploying Retina Scan AI inside a hospital environment. It is not prescriptive; every site's network topology, identity platform, and PACS vendor differs. The design intent is to situate the model behind appropriate network, identity, and audit controls.

## 1. Guiding principles

| Principle | Implication |
|-----------|-------------|
| Least privilege | Service account and every user role scoped to the minimum permissions needed |
| Defence in depth | Network, identity, application, data — each layer enforces independently |
| No PHI egress by default | The service lives inside the hospital trust boundary; no pixel data leaves the network without an explicit architectural decision |
| Use what's there | Hospital IT already has an IdP, a PACS, and SIEM — integrate, don't replace |
| Reversibility | Every clinical decision influenced by the model must be reversible at the EHR layer; the model is decision support, not autonomous |
| Observability | Every DICOM, inference, and user action has a correlatable audit record |

## 2. Logical architecture

```
                               Internet
                                 │
                                 ▼
                        ┌──────────────────┐
                        │  Hospital edge    │
                        │  firewall / WAF   │
                        └────────┬─────────┘
                                 │
                       (Public services only)
                                 │
                                 ▼
                        ┌──────────────────┐
                        │     DMZ subnet    │
                        │  Patient portal,  │
                        │  public web       │
                        └────────┬─────────┘
                                 │
                       (Internal firewall)
                                 │
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
    ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
    │  Clinical VLAN │   │  Identity &    │   │  PACS / VNA    │
    │  (radiology   │   │  Directory     │   │  DICOM archive │
    │   workstations)│   │  Keycloak/ AD  │   │                │
    └───────┬───────┘   └───────┬───────┘   └───────┬───────┘
            │                   │                    │
            │  OIDC/SAML         │                    │
            │  (auth)            │                    │
            │                    │                    │
            └───────────────┬────┴────────────────────┘
                            │
                            ▼
                   ┌───────────────────┐
                   │ Retina Scan AI    │
                   │  Namespace         │
                   │                    │
                   │  ┌──────────────┐  │    DICOM C-STORE
                   │  │ SCP Listener │ ◄┼──── (mTLS)
                   │  └──────┬───────┘  │
                   │         ▼          │
                   │  ┌──────────────┐  │
                   │  │ Anonymizer   │  │
                   │  └──────┬───────┘  │
                   │         ▼          │
                   │  ┌──────────────┐  │
                   │  │ Staging      │  │     (tmpfs, max 48h)
                   │  │ (tmpfs)      │  │
                   │  └──────┬───────┘  │
                   │         ▼          │
                   │  ┌──────────────┐  │
                   │  │ Inference    │  │
                   │  │ (GPU pool)   │  │
                   │  └──────┬───────┘  │
                   │         ▼          │
                   │  ┌──────────────┐  │
                   │  │ GSPS gen     │  │
                   │  └──────┬───────┘  │
                   │         │          │    DICOM C-STORE (return)
                   │         ├─────────────► PACS / VNA
                   │         ▼          │
                   │  ┌──────────────┐  │
                   │  │ Audit log    │──┼───► SIEM
                   │  │ (WORM)       │  │
                   │  └──────────────┘  │
                   └────────────────────┘
```

## 3. Network segmentation

Three logical zones relevant to Retina Scan AI:

| Zone | Purpose | Retina Scan AI component |
|------|---------|---------------------------|
| DMZ | Public-internet-facing services | None — no part of Retina Scan AI sits in the DMZ by default |
| Clinical VLAN | Workstations, EMR clients, radiologist reading stations | UI is served to this zone only |
| Service / data VLAN | PACS, VNA, service endpoints | Retina Scan AI namespace lives here |

Firewall rules (deny-all default + explicit allows):

| Flow | From → To | Protocol | Port | Rationale |
|------|-----------|----------|------|-----------|
| DICOM send from PACS | PACS VLAN → Retina Scan AI SCP | TCP, DICOM+TLS | 11112 (config) | Image ingestion |
| GSPS return | Retina Scan AI → PACS | TCP, DICOM+TLS | 11112 (PACS config) | Overlay archived with study |
| OIDC auth | Retina Scan AI → IdP | HTTPS | 443 | User authentication |
| UI access | Clinical VLAN → Retina Scan AI web | HTTPS | 443 | Viewer / triage UI |
| SIEM log | Retina Scan AI → SIEM | HTTPS or Syslog-TLS | 514/6514 | Audit log shipping |
| No outbound internet | Retina Scan AI → Internet | — | — | Block by default |

## 4. Identity and access

Users authenticate via the hospital's existing IdP. OIDC (OpenID Connect) is the default; SAML 2.0 is supported for legacy environments.

### 4.1 Supported IdPs

- Keycloak (open source; common in EU academic hospitals)
- Microsoft Entra ID (formerly Azure AD) via OIDC
- Okta via OIDC
- Active Directory Federation Services (AD FS) via SAML
- Ping Identity via OIDC

Implementation is in `../../access/oidc_integration.py`.

### 4.2 Claims mapping

| OIDC claim | Retina Scan AI use |
|-----------|---------------------|
| `sub` | Stable principal ID (stored in audit log) |
| `email` | Display only; never the primary key |
| `preferred_username` | Display only |
| `groups` or custom `roles` | Mapped to RBAC roles per `../../access/roles.py` |
| `amr` | Authentication Method References; checked for MFA when required |
| `sid` | Session ID; allows Back-Channel Logout per OpenID spec |

### 4.3 MFA enforcement

MFA is required for:
- Any write action (accept / reject a model output, override)
- Any export (audit log, aggregate report)
- Admin role actions
- Break-glass access

MFA is verified at the IdP via `amr` claim inspection; the API rejects any token lacking the required method reference value. See `../../access/mfa-policy.md`.

## 5. DICOM integration

A full integration description is in [`dicom-integration.md`](dicom-integration.md). Summary:

- Retina Scan AI operates as both a **DICOM SCP** (receiving images from PACS as part of a modality-worklist push or study-routing rule) and an **SCU** (returning GSPS objects to the PACS)
- Only the SOP Classes necessary for inbound images (Ophthalmic Photography Image Storage, CT if needed) and outbound overlays (Grayscale Softcopy Presentation State) are negotiated
- Association Abstract Syntax and Transfer Syntax negotiation is logged per association

## 6. Data storage

| Storage | Purpose | Lifetime | Encryption |
|---------|---------|----------|------------|
| SCP receive buffer | Temporary hold during association | Minutes | tmpfs (memory-backed) |
| Staging (anonymised) | Anonymised image awaiting inference | ≤48h default; shorter preferred | AES-256-GCM on encrypted volume |
| Model inference output | Class probs + Grad-CAM heatmap | Tied to study retention in PACS | Encrypted at PACS layer |
| Audit log | HIPAA/GDPR audit | 7 years (see `../../audit/retention_policy.md`) | WORM storage, TLS in transit |
| Model weights | The trained model file | Released per version; signed | Integrity via SHA-256 + signing key |

## 7. Runtime environment

### 7.1 Container hardening

- Non-root container user
- Read-only root filesystem where possible
- No capabilities beyond `NET_BIND_SERVICE` (for DICOM SCP) if needed
- `seccomp` default profile applied
- No privileged mode

### 7.2 Supply chain

- Base image from approved registry with image signing (cosign)
- All dependencies pinned to specific versions (cf. `requirements.txt`)
- Image scanned for CVEs in CI; blocker severity threshold configurable
- SBOM generated per release and archived (CycloneDX)

### 7.3 Secrets

- No secrets in container image
- Injected via hospital secret store (HashiCorp Vault, Kubernetes Secrets with KMS-backed encryption, etc.)
- No secret appears in logs

## 8. Observability

| Signal | Destination | Purpose |
|--------|-------------|---------|
| Application logs (structured JSON) | Log aggregator (Loki, ELK) | Troubleshooting, non-audit operational logging |
| Audit events (structured JSON, separate stream) | SIEM with WORM backing | HIPAA § 164.312(b) compliance |
| Metrics (Prometheus) | Metrics backend | SLO monitoring |
| Traces (OpenTelemetry) | APM backend | Request flow debugging |
| Model drift metrics | Drift monitoring backend | See `drift-monitoring.md` |

## 9. Availability and disaster recovery

| Scenario | Handling |
|----------|----------|
| Single-instance crash | Kubernetes readiness/liveness probes; restart on failure; multi-replica by default |
| GPU failure | Inference queue drains; on failure, workflow fallback per `incident-response.md` |
| PACS unreachable | SCP listener queues associations up to configurable depth; returns DIMSE retry |
| IdP unreachable | Sessions continue until timeout; no new logins possible (fail-closed) |
| Full service outage | Workflow fallback: clinician reads without AI overlay; documented in `incident-response.md` |

Recovery objectives:
- RPO (Recovery Point Objective): 15 minutes for audit log; 0 for ephemeral inference state
- RTO (Recovery Time Objective): 60 minutes for service restoration

## 10. Hospital infrastructure assumptions

The reference architecture assumes:

- A hospital PACS / VNA with DICOM C-STORE routing
- An IdP supporting OIDC or SAML
- A SIEM or log aggregation platform
- Encrypted storage at rest
- Network segmentation capability
- Change management process (ITIL-aligned)
- 24×7 on-call support

If any of these are absent, a gap analysis and remediation plan is required before go-live.

## 11. Sequence: single study

```
Radiographer acquires fundus image
    │
    ▼
PACS receives image, routing rule triggers
    │  C-STORE (DICOM+TLS)
    ▼
Retina Scan AI SCP listener
    │
    │  accept association, verify called/calling AE title
    ▼
Anonymizer — DICOM PS3.15 Annex E Basic Profile
    │
    ▼
Staging (tmpfs)
    │
    ▼
Inference
    │  model forward pass
    ▼
Grad-CAM heatmap
    │
    ▼
GSPS generation
    │  C-STORE (DICOM+TLS) back to PACS
    ▼
PACS archives GSPS under same StudyInstanceUID
    │
    ▼
Clinician opens study in reading workstation; GSPS overlay toggles on/off per user preference
    │
    ▼
Clinician accepts or rejects model finding; action logged
    │
    ▼
Audit log entry written
```

## 12. Alternate deployment patterns

### 12.1 Cloud deployment

If the hospital chooses a cloud deployment:

- BAA with cloud provider required
- Data residency constraints per regional regulation
- Private connectivity (VPC peering, AWS PrivateLink, Azure Private Endpoint) preferred over public internet
- Additional encryption in transit between hospital and cloud
- Customer-managed encryption keys (CMEK) recommended

### 12.2 Edge deployment

For sites with limited central IT:

- Self-contained appliance image with all components
- Outbound connection only for audit log shipping
- Model updates via signed release bundle; no inbound connection required

## 13. Review cadence

Architecture is reviewed:
- At initial go-live
- Annually
- On any change affecting scope (new site, new data source, new IdP)
- On any security incident

## 14. References

- NIST SP 800-66 Rev 2 — Implementing the HIPAA Security Rule
- HL7 FHIR SMART on FHIR — emerging pattern for identity
- DICOM PS3.15 — Security and System Management Profiles
- IHE XDS — Cross-Enterprise Document Sharing (adjacent)
