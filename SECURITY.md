# Security Policy

## Supported Versions

Security fixes are applied to the default branch. Consumers should run the latest commit or latest tagged release when available.

## Reporting a Vulnerability

Do not open a public issue for suspected vulnerabilities. Use GitHub private vulnerability reporting if it is enabled for this repository, or contact the repository owner through their GitHub profile.

Please include:

- A clear description of the issue and affected component
- Reproduction steps or a minimal proof of concept
- Potential impact and any known mitigations
- Whether PHI, DICOM metadata, credentials, model artifacts, or audit logs may be exposed

## Security Expectations

- Never commit API keys, PHI, DICOM test data with patient identifiers, OIDC secrets, or deployment credentials.
- Treat retinal images, DICOM metadata, audit events, and clinical labels as sensitive data.
- Validate uploads before inference and reject malformed image payloads.
- Use TLS, network allow-lists, and site-specific access controls for DICOM integrations.
- Run local verification before merging:

```bash
python -m ruff check .
python -m pytest -q
```
