# Clinical UI Design Rationale

Why each element of `mockup.html` is placed where it is. Grounded in human factors engineering (HFE) conventions for diagnostic imaging software.

## Three-pane layout

The left-center-right grid is the dominant pattern in diagnostic imaging UIs (OHIF, eFilm, Syngo.via) because it matches radiologist scanning behavior:

- **Left (work list)**: peripheral awareness of queue status without visual commitment.
- **Center (image)**: the primary cognitive focus. Given ~70% of the screen.
- **Right (actions + data)**: supporting information and decision capture, ipsilateral to the user's dominant hand for mouse interaction.

This layout lets a right-handed radiologist mouse-scan the image while glancing at predictions and committing decisions without crossing the midline.

## Image area: 70% of viewport

Diagnostic imaging's cardinal rule: the image is king. The image panel gets the largest real estate. Confidence bars are secondary; the physician must be able to inspect the pixels without confidence bars biasing their read.

## Grad-CAM toggle, not Grad-CAM always-on

**Always-on Grad-CAM biases the reader.** Published studies on AI-in-medicine show that attention overlays shift physicians' gaze patterns and can induce anchor bias. Making Grad-CAM opt-in (via the `G` key or button) lets the physician:

1. First form their own impression.
2. Then optionally consult the model's attention.
3. Then decide.

The button is top-right of the image, not embedded in the predictions panel, because its semantic purpose is "modify image view" not "adjust predictions."

## Work list priorities

Urgent studies get a red dot, routine get muted. No red/green pair (red-green colorblind readers exist; avoid color-pair encoding for priority). The red dot is paired with text ("DR high-confidence") so color is redundant, not primary.

Priority is derived from model confidence × class severity × patient history, computed server-side. The clinical UI does not reorder silently; any reordering is surfaced as a priority tag.

## Predictions panel: full distribution, not just top class

Showing only the top class hides the model's uncertainty. When the model is unsure (e.g., 0.52 DR vs 0.45 Glaucoma), the physician needs to see both. The full distribution communicates calibration at a glance.

The top class is highlighted (warning color on the bar) so the physician can quickly spot the model's recommendation — but it's not the only data shown.

## Confidence bars, not percentages alone

Bar lengths convey relative magnitudes preattentively. Numbers alone require cognitive effort to compare. Combining bar + number serves both fast pattern-matching and precise verification.

Bars are short (6px) because they are secondary information; the number is primary.

## Decision buttons

Three buttons, arranged by cognitive commitment:

1. **Agree** (green) — one-click commit. The default path for clear cases.
2. **Disagree** (red) — triggers a disagreement modal asking "what did you see?" to capture the physician's diagnosis + a reason.
3. **Request Second Reader** (blue, full width) — escalation for ambiguous cases. Blue signals "continue the workflow," not "red stop."

Color choices follow the convention: green for confirm, red for reject/stop, blue for continuation. Avoid using red for Disagree alone (some physicians associate red with "clinical urgency" rather than "disagreement"). The verb label and the tooltip clarify.

## Note field with placeholder

Placeholder text anchors expectation: what kind of note, who reads it. Empty note is explicitly OK for the agree path; notes are optional.

## Audit trail visible to the physician

Physicians being monitored for quality metrics prefer seeing the audit trail themselves. Visibility builds trust: the physician knows what's being recorded. This is consistent with the HIPAA §164.530(c)(2) concept of individual awareness of access patterns.

We show the last 3-5 events for the current study only. Full audit querying is a compliance-officer tool, not a physician tool.

## Disclaimer bar

Top-of-screen disclaimer ("Not a medical device, not for clinical use") on this research prototype. In a production UI, the disclaimer would be replaced by a compliance-approved statement ("Decision support tool; final diagnosis rests with the clinician").

This mockup is labeled as a research prototype so no reviewer mistakes it for a clinical tool.

## Keyboard shortcuts

Expert users develop muscle memory. Radiologists in real workflows key-stroke their way through 200+ studies per day. Must-have shortcuts:

- **G** — toggle Grad-CAM. Frequent action; one key.
- **1-5** — select class for agreement. Position-consistent with the predictions panel.
- **D** — disagree. Single letter for the common alternative.
- **R** — request reader. Escalation.
- **N** — focus note field.
- **Enter** — close case, with confirm if dirty.

All shortcuts are single-key. Modifier keys (Ctrl, Alt) are avoided because they slow expert users.

## Accessibility

This mockup has baseline semantic HTML but has not been WCAG 2.2 AA audited. A production UI must:

- Keyboard-only operable (no mouse required).
- Screen-reader friendly for physicians with vision impairment.
- High-contrast mode option.
- Resizable text without layout break.
- Focus indicators visible.
- ARIA labels on interactive controls.
- Error messages programmatically associated with fields.

For the production deployment, partner with a usability engineer familiar with IEC 62366-1 (medical device usability engineering) to conduct formative and summative usability studies.

## What changes in production

- DICOM image rendering via Cornerstone.js or OHIF, hooked to the hospital PACS.
- Work list fetched from `/api/v1/worklist` with filters (assigned-to-me, date range, priority).
- Role-aware rendering: compliance officer sees audit tools, clinician does not.
- EHR integration: clicking patient-ID opens the EHR context.
- DICOM overlay from `dicom/gsps_generator.py` for the Grad-CAM.
- Hospital design-system theming (colors, fonts, logo).
- Accessibility hardening per hospital's standards.

## References

- IEC 62366-1:2015 — Medical devices — Application of usability engineering.
- FDA Guidance on Human Factors Studies for Medical Devices (2016).
- DICOM PS3.5 — Data Structures and Encoding.
- WCAG 2.2: https://www.w3.org/TR/WCAG22/
- OHIF Viewer: https://ohif.org/
