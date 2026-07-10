# MFA Policy

## Principle

MFA is not optional for any operation that can modify, override, or export clinical data.

Read-only operations may proceed with single-factor (primary session credential), provided the session is recent and has not been flagged for anomalous behavior.

## MFA recency requirements

| Operation class | MFA required within |
|-----------------|---------------------|
| Study read / classification view | Not required (single-factor session OK) |
| Classification override | 30 minutes |
| Report write | 30 minutes |
| Report sign | 15 minutes |
| Export (single record) | 5 minutes |
| Export (> 100 records) | Fresh re-auth required (MFA within 60 seconds) |
| Break-glass activation | Fresh re-auth + typed reason |
| Secondary approver (break-glass) | Fresh re-auth |
| Config change (system admin) | 5 minutes |
| Audit export (compliance officer) | 30 minutes |

## MFA methods accepted

In priority order:

1. **FIDO2 / WebAuthn security key** (preferred).
2. **TOTP authenticator app** (Authy, Google Authenticator, 1Password, etc.).
3. **Hospital-issued smart card / PKI client cert** (where already deployed).
4. **Push notification** via hospital's federated MFA provider.

**Not accepted**:
- SMS-based one-time codes (NIST SP 800-63B-3 restricts SMS; attacker SIM-swap risk is documented).
- Email magic links (susceptible to email-account compromise).
- Security questions.

## Session lifecycle

- Session TTL: 8 hours idle / 12 hours absolute.
- Idle timeout: any 30-minute gap in API activity invalidates the session.
- Concurrent session limit: 2 per user (configurable; exceeding this logs out the oldest).
- Forced re-authentication on role change, IP change (warn and require reauth), and user profile update.

## Break-glass flow

When a clinician needs access beyond their role (e.g., Referring Physician reading a study for a patient not on their assigned list):

1. User clicks "Request emergency access" in UI.
2. MFA challenge fires immediately (single-factor session is insufficient).
3. User types a reason (minimum 30 characters, free text).
4. If configuration requires secondary approval:
   - System generates a request ID and notifies the on-call approver.
   - Secondary approver receives a notification, views the requesting user and reason.
   - Secondary approver approves or denies with their own MFA challenge.
5. Upon approval (or automatic approval in emergencies):
   - Session gains `break_glass_active=True` and `break_glass_reason=<text>`.
   - Break-glass session TTL is shorter (2 hours).
6. Every action under break-glass is marked in the audit log.
7. Post-hoc review:
   - Compliance officer reviews break-glass events within 72 hours.
   - If inappropriate, user is contacted; potential disciplinary action per hospital policy.

Break-glass is auditable and reversible (a session can be revoked mid-use). It is NOT a backdoor.

## Anomaly detection

The following trigger an MFA re-challenge or session invalidation:

- IP change mid-session (geolocation change > 500 km in < 2 hours).
- User-agent change mid-session.
- Unusual access pattern (> 50 studies accessed in < 10 minutes).
- Access attempt from a blocked IP or banned device ID.
- Failed MFA challenge (3 in a row locks the account for 15 minutes; compliance officer notified).

## MFA enrollment and recovery

- New users enroll at least one FIDO2 security key during onboarding (technician-assisted in person).
- Backup method: second enrolled FIDO2 key OR TOTP app.
- Lost primary factor: user contacts hospital IT help desk; identity verification per hospital policy; re-enrollment requires in-person verification.
- Account recovery via self-service email is disabled.

## Relationship to hospital IdP

Where the hospital IdP (Keycloak / Okta / Azure AD) already enforces MFA with equivalent or stricter policy, this application trusts the IdP's MFA claim (`amr` claim in the ID token, looking for "mfa" or specific values like "hwk", "otp").

Where the hospital IdP does not enforce MFA for clinical apps, this application requires an MFA step-up via its own MFA verifier before any write-class operation.

## Testing and audit

- Automated tests verify the permission matrix respects MFA recency requirements.
- Quarterly penetration test exercises MFA bypass attempts.
- Compliance officer reviews break-glass events and MFA failure rates monthly.

## References

- HIPAA Security Rule §164.312(a)(2)(i) — Unique user identification (implies strong authentication).
- NIST SP 800-63B-3 — Digital Identity Guidelines, Authentication and Lifecycle Management.
- NIST SP 800-63B-3 §5.1.3 — Out-of-band authenticators (explains SMS restrictions).
- FIDO Alliance: https://fidoalliance.org/
- OWASP ASVS 4.0.3 V2 — Authentication Verification Requirements.
