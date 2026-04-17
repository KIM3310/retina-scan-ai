# ADR 004: RBAC with clinical roles

- **Status**: Accepted
- **Date**: 2026-04-17

## Context

Clinical imaging services have diverse users (radiologists, ophthalmologists, referring physicians, technicians, researchers, compliance officers, admins). Each user type has different permission needs. Access control models considered:

1. Attribute-Based Access Control (ABAC): fine-grained, policy-driven.
2. Role-Based Access Control (RBAC): coarse-grained, role-to-permission matrix.
3. Relationship-Based Access Control (ReBAC): e.g., "clinician can access their assigned patients."
4. Hybrid: RBAC for the permission matrix, with ReBAC rules for patient-assignment scope.

## Decision

**Hybrid model: RBAC for the coarse permission matrix, with ReBAC rules (`_if_assigned_or_breakglass`) for patient-assignment scope**. Attribute-based extension is possible but not enabled in the baseline.

Roles defined:
- `Radiologist`, `Ophthalmologist` — full clinical access
- `ReferringPhysician` — access limited to assigned patients
- `Technician` — study intake only
- `Researcher` — de-identified only
- `ComplianceOfficer` — audit logs only
- `SystemAdmin` — config, no PHI
- `AuditorExternal` — time-boxed scoped access
- `BreakGlass` — ephemeral role augmentation

Implementation: `access/roles.py`.

## Consequences

### Positive

- **Clinicians understand roles**: hospital IT and clinicians both reason in role-language ("I'm a radiologist," "she's a technician"). Policies match this vocabulary.
- **Auditability**: a role assignment change is a single event; audit queries like "who was a Radiologist on date X" are direct.
- **Simple to reason about**: the permission matrix is a 2D table. Compliance reviewers can verify it without reading code.
- **Federation-friendly**: hospital IdP groups map 1:1 to roles. New hospital = new role-mapping config, no code change.
- **Scope via ReBAC for assignment**: the `_if_assigned_or_breakglass` rule expresses "physicians see their patients" without adding attribute-parsing complexity.

### Negative

- **Coarse-grained**: RBAC doesn't express rules like "only during business hours" or "only from the hospital network." These would require ABAC extensions.
- **Role explosion risk**: as workflows proliferate, we could end up with 20+ roles. Mitigate by combining roles + ReBAC rather than multiplying roles.
- **Break-glass still needed**: RBAC alone doesn't handle emergency access to non-assigned patients. We added the BREAK_GLASS augmentation specifically for this.

### Mitigations

- **Keep role count small**: enforce a policy that new permissions attach to existing roles or create a new role only when the user persona is genuinely distinct.
- **Document the matrix**: `access/README.md` shows the role × action matrix. `roles.py::describe_permission_matrix()` emits a human-readable dump for compliance review.
- **Anticipate ABAC needs**: the `PermissionContext` dataclass already carries attributes (purpose_of_use, MFA recency, IP, device). Future ABAC rules attach here without disrupting the matrix.

## Alternatives considered

### Pure ABAC

Rejected because:
- Clinicians and hospital IT reason in roles, not attributes.
- Policy rules are harder to audit by non-engineers.
- Policy engines (OPA, Cedar) add operational surface area for a prototype.

### Pure ReBAC

Rejected because:
- ReBAC is excellent for scope ("patient assigned to physician") but poor for role-level permissions ("can sign reports").
- Implementing both in one model adds complexity without clear benefit.

### No break-glass, emergency access via admin override

Rejected. Requiring an admin to grant ad-hoc access creates a workflow bottleneck in emergencies. Break-glass with post-hoc review is the standard healthcare pattern.

## How this constrains future work

- **Adding a new role**: update `access/roles.py::Role` enum, add permission entries to `_MATRIX`, update `access/README.md` matrix, update `mfa-policy.md` if MFA requirements differ.
- **Adding a new permission**: update `access/roles.py::Action` enum, add to relevant roles' entries in `_MATRIX`, add an MFA recency requirement if the action modifies state.
- **Time-based or location-based rules**: implement as new allow functions (e.g., `_business_hours_only`) that read from `PermissionContext`. Don't restructure the matrix.
- **Federated role mapping**: configure via `access/oidc_integration.py::EXAMPLE_KEYCLOAK_CONFIG`. No code changes.

## Implementation notes

- `access/roles.py::is_permitted()` is the single entry point. API handlers must use it, never check roles directly.
- `access/roles.py::_MATRIX` is the source of truth. Synchronized with documentation in CI via a test that dumps `describe_permission_matrix()` and diffs against the checked-in README.
- Break-glass state lives on the session (`break_glass_active`, `break_glass_reason`). Activating break-glass requires a fresh MFA and typed reason; see `access/mfa-policy.md`.

## References

- NIST SP 800-162 — Guide to ABAC Definition and Considerations.
- HIPAA Security Rule §164.308(a)(4)(ii)(B) — Workforce access authorization.
- HIPAA Security Rule §164.312(a)(1) — Access control technical safeguard.
- XACML 3.0: https://www.oasis-open.org/standard/xacmlv3-0/
- Open Policy Agent (OPA): https://www.openpolicyagent.org/
- `access/roles.py` — implementation.
- `access/mfa-policy.md` — MFA policy doc.
