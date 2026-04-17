# Incident Response

## 1. Scope

This playbook covers incidents affecting Retina Scan AI in a clinical deployment. An **incident** is any event that compromises — or has the credible potential to compromise — patient safety, data security, service availability, or regulatory compliance.

Examples:
- Model produces consistently wrong output on a cluster of studies
- Unauthorised access to inference results
- Audit log tampering detected
- Service outage exceeding SLO
- DICOM-link outage
- Model inadvertently trained on or inferencing over data it should not have seen
- Breach of Protected Health Information

Alignment:
- HIPAA § 164.308(a)(6) Security Incident Procedures
- GDPR Articles 33–34 (breach notification)
- MDR Article 87 (vigilance)
- FDA 21 CFR Part 803 (Medical Device Reporting)

## 2. Severity ladder

| Severity | Definition | Notification timer |
|----------|------------|---------------------|
| SEV-1 — Patient safety | Model output contributed to or could have contributed to serious clinical harm | Immediate; regulatory obligations likely triggered |
| SEV-2 — Security breach | Unauthorised access to PHI, data exfiltration, or audit log tampering confirmed | HIPAA 60-day, GDPR 72-hour timer; immediate internal notification |
| SEV-3 — Major service outage | Service unavailable exceeding RTO; clinical workflow fallback required | Internal notification; clinical lead informed |
| SEV-4 — Performance degradation | Sustained drift alert requiring intervention | Change-control cycle initiated |
| SEV-5 — Minor | Localised issue, no patient or data impact | Logged and tracked |

## 3. First-responder actions

For any suspected incident:

1. **Preserve evidence**
   - Freeze the relevant audit log segment (lock against overwrite)
   - Snapshot relevant operational logs
   - Do **not** delete any data

2. **Assess and classify**
   - Determine if patient safety exposure exists
   - Determine if PHI has been accessed, exfiltrated, or altered
   - Determine if any regulatory notification clock has started

3. **Contain**
   - For SEV-1: pause model routing for affected studies; clinician-only reading per fallback
   - For SEV-2: revoke compromised credentials; block affected network paths
   - For SEV-3: failover or acknowledge outage; clinician fallback invoked

4. **Notify**
   - Internal: clinical lead, engineering on-call, DPO, Security Officer, QMS lead
   - External: per notification timers (see §8)

5. **Investigate**
   - Root cause analysis (see §5)
   - Scope assessment — how many studies, patients, users affected?

6. **Remediate**
   - Corrective action appropriate to root cause
   - If Tier C emergency change needed, per [`change-control.md`](change-control.md)

7. **Post-incident**
   - Report; lessons learned
   - Update procedures, FMEA, training materials

## 4. Clinical workflow fallback

When the model is paused or unavailable, the clinician workflow **degrades gracefully**:

1. Studies arrive at the PACS as before (no ingestion dependency on Retina Scan AI)
2. GSPS overlay is absent — clinician reads the original fundus photograph without AI assistance, as was standard practice before deployment
3. Reading speed may slow; staffing plan accommodates this
4. No patient study is lost or delayed due to a Retina Scan AI outage

Practical consequence: clinicians **must remain capable of reading without AI**. This is a deployment requirement, not aspirational. Training coverage verifies clinicians are comfortable with non-assisted reading.

## 5. Root-cause analysis template

For every SEV-1 through SEV-3 incident, a structured RCA is completed.

```
Incident ID: ____
Date detected: ____
Severity: ____
Patient impact: ____ (number of patients; nature of exposure)
Data impact: ____ (records affected; PHI disclosure; data loss)
Service impact: ____ (duration; scope)

TIMELINE
[UTC time]    Event
__________    First signal observed
__________    First responder engaged
__________    Incident declared
__________    Containment action taken
__________    Evidence preserved
__________    Internal notifications sent
__________    External notifications sent (if any)
__________    Service restored / model re-enabled
__________    RCA completed

ROOT CAUSE
(What fundamentally allowed this to occur? 5-whys may help; distinguish cause from symptom.)

CONTRIBUTING FACTORS
(Conditions that made the root cause more likely or more impactful.)

WHY WAS IT NOT PREVENTED
(Which safeguards in FMEA and change-control either didn't exist or didn't work?)

WHY WAS IT NOT DETECTED EARLIER
(Which drift or audit signals should have caught this and didn't?)

REMEDIATION
(Specific changes with owners and deadlines.)
- [ ] __________ (owner: ___, due: ___)
- [ ] __________ (owner: ___, due: ___)

FOLLOW-UP
- [ ] FMEA update
- [ ] Drift monitor update
- [ ] Training material update
- [ ] Clinical SOP update
- [ ] Regulatory reporting (if applicable)

REPORTING
(Which regulators notified; report IDs.)
- HHS OCR (HIPAA): _____
- Supervisory Authority (GDPR): _____
- FDA MedWatch MDR: _____
- EU Competent Authority vigilance: _____
- Notified Body: _____

SIGN-OFF
Clinical Lead: ____ (date)
Security Officer: ____ (date)
DPO: ____ (date)
QMS Lead: ____ (date)
```

## 6. Communication

External communication is owned by the Controller (deploying hospital) — they own the patient relationship. Processor (Retina Scan AI operator) supports with:

- Factual statement of the scope
- Technical root cause (non-confidential summary)
- Remediation plan
- Affected-records list for breach notification

Press / media inquiries go through the Controller's communications office. Processor does not comment publicly on a specific incident unless coordinated.

## 7. Patient notification

Required under HIPAA § 164.404 for PHI breaches affecting patients. Letter content per § 164.404(c):

- Brief description of what happened
- Date of breach and date of discovery
- Types of unsecured PHI involved
- Steps individuals should take to protect themselves
- What the covered entity is doing
- Contact procedures

Parallel under GDPR Article 34 for breaches with high risk to rights and freedoms.

## 8. Regulatory reporting timers

| Regulator | Trigger | Timer | Reference |
|-----------|---------|-------|-----------|
| HHS OCR (US) | Breach of unsecured PHI, ≥ 500 individuals | Without unreasonable delay, ≤ 60 days; notify media for affected state(s) | 45 CFR § 164.408 |
| HHS OCR (US) | Breach, < 500 individuals | Log and report annually ≤ 60 days after year-end | 45 CFR § 164.408 |
| Data Protection Authority (EU) | Personal data breach with risk to rights and freedoms | Without undue delay, ≤ 72 hours | GDPR Art. 33 |
| Data subjects (EU) | Breach with high risk | Without undue delay | GDPR Art. 34 |
| FDA (US) | Death or serious injury, or malfunction likely to cause death/serious injury | Death/serious injury: 30 days; 5 days if immediate remedy required | 21 CFR Part 803 |
| FDA (US) | Field correction or removal to reduce health risk | Report initiation | 21 CFR Part 806 |
| EU Competent Authority | Serious incident per MDR Art. 2(65) | 2, 10, or 15 days depending on severity | MDR Arts. 87–89 |
| Notified Body | Changes affecting certification | Per certification terms | MDR Art. 56 |
| Commercial partners / deployed sites | Per contract SLA | Per agreement | N/A |

Any ambiguity about whether a timer is triggered is resolved in favour of notifying. "Better safe than silent" — under-reporting has regulatory consequences.

## 9. Tabletop exercise

Quarterly, the incident response team executes a tabletop with a scripted scenario. Past scenarios:

- Cluster of wrong DR classifications on a specific camera model
- Audit log tamper detection alert
- PACS-side credential compromise exposing study routing
- Model weight drift detected via hash
- Power-loss-induced inference queue corruption

Outcomes feed into FMEA review and playbook updates.

## 10. Standing roster

| Role | Hospital side | Vendor side |
|------|--------------|--------------|
| Clinical Lead | Clinical sponsor | — |
| Security Officer | Hospital CISO or deputy | Vendor Security Lead |
| DPO | Hospital DPO | Vendor DPO |
| Engineering Lead | Site IT lead | Vendor Engineering Manager |
| QMS Lead | Hospital QMS | Vendor QMS |
| Comms | Hospital Communications | Vendor Comms (supporting) |

Contact list maintained and updated quarterly.

## 11. Interaction with FMEA and change control

- Every SEV-1/SEV-2/SEV-3 incident is mapped to one or more FMEA failure modes
- If a new failure mode is identified, FMEA is updated
- If the remediation is a model change, change-control is invoked per tier classification

## 12. References

- NIST SP 800-61 Rev 2 — Computer Security Incident Handling Guide
- HHS OCR Breach Notification Rule
- ENISA guidance on personal data breach notifications
- FDA MedWatch MDR guidance
- MDCG 2023-3 — Q&A on vigilance terms and concepts

## 13. Training expectations

All principal responders complete:
- IR playbook refresher annually
- HIPAA breach notification training
- GDPR breach notification training (where applicable)
- Tabletop participation (at least one per year)
- Technical training on audit log forensics for engineering / security roles
