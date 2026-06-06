# Review Guide - Retina Scan AI

Updated: 2026-05-30

Use this page as the short path through the repository. It keeps the review grounded in the code, docs, commands, and boundaries that are already present.

## Summary

| Field | Notes |
|---|---|
| Lane | B2B non-clinical ML validation |
| Core idea | Medical-image research workflow with Grad-CAM and explicit non-diagnostic boundaries. |
| Primary reader | Research groups, health-tech prototype teams, ML reviewers, and model governance teams. |
| Stack | Python, Docker |

## Open First

1. Start with the README fast path and architecture section.
2. Open `docs/service-launch-playbook.md` only when reviewing the product or service angle.
3. Check the commands below before making claims about quality.
4. Skim the CI workflows and fixture data before deeper implementation review.
5. Read the boundaries section before presenting the project externally.

## Checks

| Purpose | Command |
|---|---|
| Test suite | `python -m pytest` |

## CI

- .github/workflows/architecture-blueprint.yml
- .github/workflows/ci.yml
- .github/workflows/dependency-review.yml
- .github/workflows/repository-health.yml
- .github/workflows/repository-surface.yml
- .github/workflows/secret-scan.yml

## Evidence

- pytest/ruff-style local verification path
- containerized delivery path
- pytest passes
- Model card/risk notes exist
- API inference path is documented

## Commercial Notes

| Possible offer | Working scope assumption |
|---|---|
| Validation template | $3k-$10k validation study |
| Explainability demo | $10k-$35k prototype review |
| Model governance review artifact | $1k-$5k/month governance support |

## Boundaries

- Not a medical device
- No diagnosis claims
- Formal validation required for clinical use

## Useful Metrics

- Metric coverage
- Explainability artifact quality
- Risk register completeness
