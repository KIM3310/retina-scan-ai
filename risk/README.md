# Risk Management

ISO 14971-aligned risk management artifacts for the Retina Scan AI system.

## Scope

This directory contains the risk management artifacts that an ISO 14971:2019 risk management file (RMF) would contain. Full regulatory submission requires additional content (device description, risk management plan approval records, design verification/validation traceability) that are out of scope for a research prototype.

## Philosophy

Risk management is not a compliance artifact produced at the end. It is an engineering practice that shapes every design decision. Three principles:

1. **Enumerate failure modes up front.** You can't mitigate what you haven't named.
2. **Quantify on severity × occurrence, not "it'll be fine."**
3. **Mitigations are code, not promises.** Every mitigation maps to a specific code path, test, monitoring check, or operational procedure.

## Files

- `fmea.md` — Failure Mode and Effects Analysis. The primary risk inventory.
- `iso14971-mapping.md` — How this system's artifacts map to ISO 14971 clauses.
- `known-limitations.md` — Cataloged limitations from development and testing.

## Risk management process (summary)

1. **Identify hazards** — through design review, FMEA workshops, and published literature on AI-in-medicine failures.
2. **Estimate risks** — severity × probability of occurrence, with detectability as a secondary factor for the risk priority number (RPN).
3. **Evaluate acceptability** — against pre-defined acceptance criteria (severity × occurrence matrix).
4. **Control risks** — design controls, protective measures, information for safety.
5. **Residual risk evaluation** — after controls, is the remaining risk acceptable?
6. **Risk management review** — before release, periodic thereafter.
7. **Production and post-production** — monitor production for new hazards; feed back into the RMF.

## Risk acceptance criteria

We adopt the following matrix. Severity is the worst plausible patient outcome; probability is per-use.

| Severity \\ Probability | Frequent (>1/100) | Occasional (1/100 – 1/10,000) | Remote (<1/10,000) |
|------------------------|-------------------|-------------------------------|---------------------|
| **Catastrophic** (death, irreversible harm) | Unacceptable | Unacceptable | Mitigate if feasible |
| **Major** (serious injury, reversible) | Unacceptable | Mitigate if feasible | Acceptable |
| **Moderate** (medical intervention needed) | Mitigate if feasible | Acceptable | Acceptable |
| **Minor** (temporary discomfort) | Acceptable | Acceptable | Acceptable |

Unacceptable risks block release until mitigated. "Mitigate if feasible" means the team must attempt a control and document the residual risk.

## Risk management team

- Principal Investigator (clinician).
- Lead Engineer.
- Quality / Regulatory Specialist.
- Clinical Advisor (ophthalmologist or retina specialist).
- Cybersecurity Advisor.

Meet quarterly, plus any time a new hazard is identified.

## Post-market surveillance

Production deployments require ongoing surveillance. Key mechanisms:

- `docs/clinical/drift-monitoring.md` — tracks input distribution, confidence drift, calibration drift.
- `audit/` — every prediction is audited; aggregate trends feed the risk review.
- Incident tracking per `docs/clinical/incident-response.md` — post-hoc review of every SEV-1 or SEV-2 incident.
- Customer reports — dedicated channel for clinician feedback, tracked in the RMF.

## References

- ISO 14971:2019 — Medical devices — Application of risk management to medical devices.
- IEC 62304:2006+A1:2015 — Medical device software — Software life cycle processes.
- FDA Guidance on Software Pre-Cert Program and AI/ML SaMD Action Plan (2021).
- Published AI-in-medicine failure analyses:
  - Obermeyer et al., "Dissecting racial bias in an algorithm used to manage the health of populations" (Science 2019).
  - Finlayson et al., "Adversarial attacks on medical machine learning" (Science 2019).
  - Oakden-Rayner et al., "Hidden stratification causes clinically meaningful failures in machine learning for medical imaging" (Proc. ACM CHIL 2020).
