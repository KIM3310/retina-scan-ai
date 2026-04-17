# Clinician-in-the-Loop Design

## 1. Position statement

Retina Scan AI is **decision support, not autonomous diagnosis**. Every clinically consequential output must be reviewed and either accepted, overridden, or ignored by a credentialed clinician. The UI and workflow are designed to:

- Make the clinician's authority unambiguous
- Provide enough information to enable meaningful oversight (not rubber-stamp)
- Capture disagreement as signal, not friction
- Preserve the clinician's time — decision support should be a net positive on cognitive load, not a distraction

This position aligns with:
- FDA Good Machine Learning Practice Principle 7 (Human-AI team performance)
- EU AI Act Article 14 (human oversight)
- IMDRF N41 (IMDRF Clinical Evaluation of SaMD)
- ISO/IEC TR 24028 (trustworthiness of AI)

## 2. Operating roles

Two clinician roles interact with the model output. Role definitions are in [`../../access/roles.py`](../../access/roles.py).

| Role | Decision authority | Typical action on model output |
|------|-------------------|------------------------------|
| Radiologist / Ophthalmologist | Final diagnostic reader | Accepts, overrides, or ignores; signs the final report |
| Technician / Imaging specialist | Image capture; preliminary triage | May use model to prioritise workflow, cannot override diagnostic finding |

An optional **second-reader** configuration permits a nurse practitioner or primary-care physician to triage screening workflows, with auto-escalation to ophthalmology on high-confidence positive findings for DR, AMD, or glaucoma.

## 3. Model output contract

The model produces, per image:

| Output | Type | Use |
|--------|------|-----|
| Class probabilities across 5 classes | Float vector of length 5, sum = 1 | Primary display |
| Calibrated confidence on top class | Float in [0,1], calibrated via Platt scaling or temperature scaling | Binary "show / flag" gate |
| Grad-CAM overlay | 224×224 heatmap | Visual explanation |
| Quality score | Float in [0,1] | OOD detection, image quality gating |
| Model version identifier | String | Audit traceability |

## 4. Confidence thresholds

The UI uses a **three-tier** presentation based on calibrated confidence:

| Band | Calibrated confidence on top-1 | UI presentation | Required clinician action |
|------|-------------------------------|-----------------|----------------------------|
| Low | < 0.50 | No suggestion surfaced; image shown without annotation | Clinician reads normally; model result retained in audit log |
| Medium | 0.50 – 0.80 | Suggestion surfaced as "Possible <class>"; overlay available on toggle | Read normally, consider overlay |
| High | > 0.80 | Finding prominently displayed; overlay on by default | Must explicitly confirm or override |

Thresholds are **site-configurable** within bounds defined by the validation study protocol. Any change to thresholds is audited and requires clinical-lead approval.

Threshold rationale:
- Low — avoids priming the clinician when the model is uncertain
- Medium — surfaces the model's best guess without claiming authority
- High — concentrates human attention; requires deliberate acknowledgement

## 5. Disagreement workflow

When a clinician's reading disagrees with the model:

1. Clinician selects "Override" with a reason code (structured list) and optional free-text note
2. Audit event `CLINICIAN_OVERRIDE` written with:
   - Patient pseudonymised ID
   - Original model output (class + confidence)
   - Clinician reading
   - Reason code
   - Clinician ID (principal)
   - Timestamp
3. The override is **not pushed back to the model as a label immediately** — this avoids reinforcement of individual clinician bias
4. Overrides are aggregated monthly for review by the clinical-lead panel, which decides whether:
   - The case should be added to the retraining set
   - A retraining trigger has been met (disagreement rate > configurable threshold)
   - A calibration issue exists that warrants a threshold adjustment

When a clinician's reading agrees with the model, an implicit confirmation audit event is logged (via the report-signoff event emitted by the reporting system).

## 6. Second-reader role

In triage / screening deployments, a second-reader workflow operates:

| Step | Actor | Action |
|------|-------|--------|
| 1 | Technician | Acquires fundus image; quality gate checks |
| 2 | Retina Scan AI | Inference; if Normal with high confidence → low-priority queue; else → ophthalmology referral queue |
| 3 | Primary care / NP | Reviews low-priority queue; can release or escalate |
| 4 | Ophthalmologist | Reviews referral queue; makes definitive reading |

The AI is never the sole gatekeeper for release. Every study passes through at least one human reviewer before being closed. The AI's role is to **prioritise**, not to substitute.

## 7. Automation bias mitigation

Automation bias — over-reliance on automated output — is a known risk (documented in HF literature; e.g. Goddard et al. 2012). Countermeasures built into the UI:

| Bias | Mitigation |
|------|-----------|
| Anchoring on model's top class | Probability bar chart shows all 5 classes, not just top-1 |
| Over-trust of confidence | Confidence displayed with calibration note; "calibrated" label explains to user that this is not raw softmax |
| Missed low-probability findings | Review summary displays all classes with probability > 0.10 |
| Skipping image inspection | Image is always shown fullsize; overlay is off by default below the "High" band |
| Forgetting override capability | Override button always visible; labelled in plain language |
| Clinician habituation to agreement | Random 1% of cases surface "Are you sure?" challenge (measured to not disrupt flow); calibration is verified against clinician's in-session disagreement rate |

## 8. Consent, transparency, and patient communication

Where local regulation requires it, patients are informed that AI-assisted reading may be part of their care. The information leaflet describes:

- What the tool does (classifies fundus images into five categories)
- What it does **not** do (replace the clinician; make the final decision)
- That the patient may request reading without AI assistance
- That no external sharing of the image occurs without specific consent

## 9. Clinician training

Before a site goes live, participating clinicians complete a training module covering:

- Model's intended use and limitations (drawn from `../../governance/model-card.md`)
- Known bias and limitations (drawn from `../../governance/bias-and-limitations.md`)
- UI walkthrough including override workflow
- Examples of confident-but-wrong model predictions
- Incident reporting process

Completion is tracked; the deploying organisation's clinical-lead holds the training register.

## 10. Ergonomic principles

Drawn from IEC 62366-1 (usability engineering) and HFE (Human Factors Engineering) literature specific to radiology reading environments:

| Principle | Application |
|-----------|-------------|
| Avoid interruption | Model output inline with existing study viewer; no separate window required |
| Minimise clicks | Overlay toggle bound to single key; confirm/override as single click |
| Do not change colour language | Use established radiology colour conventions; new colours would confuse |
| Respect reading pace | Model inference completes before clinician opens the study; no wait state introduced |
| Make disagreement low-friction | Override reason is structured dropdown; free text is optional |
| Surface uncertainty | Confidence band labelling, calibration note |

## 11. Auditability of clinical actions

Every clinician-facing action is audited. From [`../../audit/logger.py`](../../audit/logger.py):

| Event | Trigger |
|-------|---------|
| `STUDY_VIEW` | Clinician opens a study |
| `OVERLAY_TOGGLE` | Clinician toggles Grad-CAM overlay on/off |
| `AI_FINDING_ACCEPT` | Clinician confirms model finding |
| `AI_FINDING_OVERRIDE` | Clinician overrides model finding |
| `REPORT_SIGN` | Final report signed |

Retention aligns with HIPAA/GDPR per [`../../audit/retention_policy.md`](../../audit/retention_policy.md).

## 12. Escalation pathway

If a clinician suspects a model malfunction (consistent wrong predictions in a cluster, impossible output, UI anomaly), the reporting pathway is:

1. Mark the study with a structured problem-report code in the UI
2. Event is logged and routed to a queue monitored by the vendor's on-call engineer and the site's clinical-IT liaison
3. Triage within site-configurable SLA (default 4 business hours)
4. Escalation to incident response (`incident-response.md`) if malfunction impact is material

## 13. Caveats

- The above presumes a fully-staffed clinical context with at least one qualified reader per site
- In resource-limited settings, the balance between AI autonomy and human oversight may differ; any deviation must be revalidated
- The disagreement rate is a lagging indicator; proactive drift monitoring is complementary (see `drift-monitoring.md`)
