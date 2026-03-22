# Deployment and MLOps notes

## Current posture

This repository demonstrates a **production-style shape** for a medical AI service, but it is not a production medical deployment.

## Included operational surfaces

- FastAPI inference API
- structured audit-aware logging
- synthetic validation artifact generation
- runtime monitoring endpoint
- portfolio-safe release-readiness endpoint
- CI workflow for lint, compile, tests, and artifact generation

## Suggested deployment path

1. containerize API + dashboard
2. separate inference service from review UI
3. add secret management and environment-specific config
4. persist monitoring / audit events outside process memory
5. version models and evaluation artifacts together
6. gate promotion on documented offline validation artifacts

## What is deliberately not claimed

- regulatory approval
- clinical readiness
- real-world monitoring coverage
- trained-model deployment with representative data
