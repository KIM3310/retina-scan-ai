# Clinical UI Mockup

A minimal HTML/CSS mockup of the clinician triage view for the Retina Scan AI service. Demonstrates ergonomic layout patterns for a second-reader / triage workflow.

## Files

- `mockup.html` — The static UI mockup. Open in a browser.
- `design-rationale.md` — Why each element is where it is; human factors engineering (HFE) notes.

## What this is

- A reference for the clinical workflow the service is designed to support.
- A conversation artifact for early customer discussions.
- A thumbnail of what a productionized UI would feel like.

## What this is NOT

- Not a production UI. The real UI would be React, integrate with the hospital EHR via HL7/FHIR, render DICOM via Cornerstone.js, and follow each site's design system.
- Not accessibility-audited. A real clinical UI must meet WCAG 2.2 AA at minimum; this mockup has basic semantic HTML but has not been formally audited.
- Not regulatory-ready. UIs intended for diagnostic use face regulatory requirements (FDA 21 CFR 820, IEC 62366-1 usability engineering); this is an educational artifact.

## Workflow the mockup represents

```
1. Clinician opens work list showing pending studies.
2. Clicks a study to open the triage view.
3. Sees the fundus image in the center panel.
4. Sees the model's predicted classes with confidence bars on the right.
5. Toggles the Grad-CAM overlay to understand what the model attended to.
6. Either agrees with the model's top class (one click), disagrees (captures reason), or
   requests a second reader (escalation).
7. Adds a note if needed.
8. Closes the case; next pending study loads.
9. The full interaction (view, toggle, agree/disagree, note, close) is audited.
```

## Keyboard shortcuts (indicative)

- `G` → toggle Grad-CAM overlay.
- `1` - `5` → select class for agreement (Normal, DR, Glaucoma, Cataract, AMD).
- `D` → disagree with top prediction.
- `R` → request second reader.
- `N` → focus note field.
- `Enter` → close case (with confirmation if any field is dirty).

## Viewing the mockup

Open `mockup.html` in any modern browser. No build step, no dependencies.

## Integration points (for a real deployment)

- Auth: redirect to hospital IdP via OIDC (see `access/oidc_integration.py`).
- Study list: backend query against the service; filter by assigned-to-me unless compliance officer.
- Image display: DICOM viewer (Cornerstone.js, OHIF).
- Grad-CAM overlay: fetched from the GSPS endpoint (see `dicom/gsps_generator.py`).
- Classification result: fetched from `/api/v1/studies/{uid}/classification`.
- Actions (agree, disagree, note): POST to `/api/v1/studies/{uid}/clinician-decision` (see `api/main.py`).
- Audit: every action triggers an audit event via `audit/logger.py`.
