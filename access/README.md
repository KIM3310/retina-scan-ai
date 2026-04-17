# Access Control

Role-based access control (RBAC) layer for the retinal classification service, designed for hospital IT integration patterns.

## Design principles

1. **Federation-first**. The service does not maintain its own user accounts in production. Identity federates from the hospital's identity provider (Keycloak, Okta, Azure AD) via OIDC.
2. **Roles, not permissions in code**. Every code path checks a role; the role-to-permission mapping lives in `roles.py` and is the only place that changes when new permissions are added.
3. **Explicit purpose-of-use**. Every session captures the user's declared purpose (TREATMENT, PAYMENT, OPERATIONS, RESEARCH) per HIPAA conventions. This flows into audit events.
4. **Break-glass is a first-class pattern**. When a clinician needs emergency access beyond their role, they trigger break-glass with a required reason; this is logged and reviewed post-hoc.
5. **MFA is not optional for write operations**. Read-only can be single-factor; any modification, override, or export requires a recent MFA challenge (see `mfa-policy.md`).

## Clinical roles

Mapping to typical hospital staff categories:

| Role | Purpose | Read | Write classification | Override | Export | Break-glass allowed |
|------|---------|------|----------------------|----------|--------|---------------------|
| Radiologist | TREATMENT | Yes | Yes (second read) | Yes | Yes | Yes |
| Ophthalmologist | TREATMENT | Yes | Yes (primary read) | Yes | Yes | Yes |
| Referring Physician | TREATMENT | Yes (assigned patients) | No | No | No | Limited |
| Technician | OPERATIONS | Study intake only | No | No | No | No |
| Researcher | RESEARCH | De-identified only | No | No | Aggregate only | No |
| Compliance Officer | OPERATIONS | Audit logs only | No | No | Audit export | No |
| System Admin | OPERATIONS | No PHI | Config only | No | No | No |
| Auditor (external) | OPERATIONS | Time-boxed, scoped | No | No | Time-boxed | No |

Cross-cutting roles (orthogonal to clinical role):

- `billing_authorized` — may view billing-related metadata, not clinical imaging.
- `quality_reviewer` — may participate in disagreement resolution workflows.

## Session flow

```
1. User opens clinical UI → redirected to hospital IdP (OIDC authorization code flow).
2. IdP authenticates user, returns id_token + access_token.
3. oidc_integration.py validates the token, extracts claims (sub, role via group membership).
4. Service establishes session with:
   - session_id (unique)
   - actor (user_id, role, display_name)
   - purpose_of_use (user declared at session start)
   - mfa_last_verified_at (timestamp)
   - session_expires_at (default 8h, configurable)
5. Every subsequent API call carries the session token.
6. API handlers call is_permitted(role, action, subject) from roles.py.
```

## MFA policy

See `mfa-policy.md`. Summary:

- Read-only actions: single-factor OK if session < 8h old.
- Any write or override: MFA within last 30 minutes required.
- Export: MFA within last 5 minutes required; plus a re-authentication for exports > 100 records.
- Break-glass: MFA + typed reason + secondary approval (in configurations requiring it).

## Files

- `roles.py` — role definitions and `is_permitted()` entry point.
- `oidc_integration.py` — OIDC client wiring, token validation, session establishment.
- `mfa-policy.md` — full MFA policy document.

## Integration with hospital IdPs

The `oidc_integration.py` module is config-driven. Typical configs:

**Keycloak**:
```yaml
oidc:
  issuer: https://idp.hospital.example.com/realms/clinical
  client_id: retina-scan-ai
  client_secret_ref: vault:secret/retina/oidc#client_secret
  scopes: [openid, profile, email, groups]
  group_claim: groups
  role_mapping:
    radiology-physicians: Radiologist
    ophthalmology-physicians: Ophthalmologist
    radiology-techs: Technician
    research-team: Researcher
    compliance-team: ComplianceOfficer
```

**Okta** / **Azure AD** have equivalent structures; the `role_mapping` translates IdP group names into application role names.

## Implementation status

This is research code. Before production use:

- [ ] Penetration test the OIDC flow, in particular token validation and replay protection.
- [ ] Review against OWASP ASVS Level 2.
- [ ] Verify the role-permission matrix with the hospital compliance officer.
- [ ] Configure the break-glass approval workflow per the hospital's policies.
- [ ] Perform disaster-recovery test of the MFA verifier dependency.

## References

- HIPAA Security Rule §164.312(a)(1) — Access Control
- HIPAA Security Rule §164.308(a)(4)(ii)(B) — Workforce access authorization
- OWASP ASVS 4.0.3: https://owasp.org/www-project-application-security-verification-standard/
- OpenID Connect Core 1.0: https://openid.net/specs/openid-connect-core-1_0.html
