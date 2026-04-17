# Compliance Posture — Retina Scan AI

> **This repository is research / educational code. It is NOT an FDA-cleared, CE-marked, or otherwise regulatory-approved medical device.** The compliance artifacts in this folder demonstrate the governance scaffolding a production deployment would require. They are not a legal opinion.

## Purpose

Retinal image classification touches almost every high-bar regulatory regime an AI system can encounter:

- **Clinical use** implicates HIPAA (US) and GDPR (EU) because fundus images with a linkable identifier are Protected Health Information (PHI) / special-category personal data under GDPR Article 9.
- **Decision support at the point of care** implicates FDA Software as a Medical Device (SaMD) framing, EU MDR (Medical Device Regulation 2017/745) CE marking, and the UK MHRA's equivalent.
- **AI-specific risk** implicates the EU AI Act (Annex III, Point 5 Class IIa/IIb medical device AI = high-risk) and emerging US state laws on algorithmic decision-making.

This folder maps each regime to the design and operational controls that a production deployment of this service would need. It is organised so that a regulatory reviewer or auditor can map our evidence to their required artifacts.

## Contents

| File | Purpose |
|------|---------|
| [`hipaa-mapping.md`](hipaa-mapping.md) | HIPAA Security Rule 45 CFR §164.308/310/312 — safeguard-by-safeguard mapping |
| [`fda-samd-considerations.md`](fda-samd-considerations.md) | SaMD classification, 510(k) vs De Novo, change control, Predetermined Change Control Plan (PCCP) |
| [`mdr-ce-considerations.md`](mdr-ce-considerations.md) | EU MDR 2017/745, IVDR adjacency, GSPR mapping, notified body engagement |
| [`phi-handling.md`](phi-handling.md) | Data classification, de-identification pipeline (Safe Harbor + Expert Determination), audit logging requirements |
| [`gdpr-dpia.md`](gdpr-dpia.md) | Data Protection Impact Assessment (Article 35) filled in for this system |

## Who should read which file

| Reader | Start here |
|--------|-----------|
| Regulatory affairs | `fda-samd-considerations.md`, `mdr-ce-considerations.md` |
| Hospital Information Security | `hipaa-mapping.md`, `phi-handling.md` |
| Data Protection Officer | `gdpr-dpia.md`, `phi-handling.md` |
| Clinical Engineering | `fda-samd-considerations.md`, `../risk/iso14971-mapping.md` |
| ML engineering | `../governance/model-card.md`, `../governance/datasheet.md` |

## Framework references

Standards and statutes referenced across this folder:

| Scope | Reference |
|-------|-----------|
| US privacy | HIPAA Privacy Rule 45 CFR §§ 164.500–164.534, Security Rule §§ 164.302–164.318, Breach Notification §§ 164.400–164.414 |
| US device regulation | 21 CFR Part 820 (QSR, transitioning to 21 CFR Part 820 QMSR harmonised with ISO 13485), 21 CFR Part 11 (electronic records) |
| US FDA AI/ML guidance | *Marketing Submission Recommendations for a Predetermined Change Control Plan for Artificial Intelligence-Enabled Device Software Functions* (Dec 2024 final), *Good Machine Learning Practice for Medical Device Development: Guiding Principles* (Oct 2021) |
| EU device regulation | Regulation (EU) 2017/745 (MDR), Regulation (EU) 2017/746 (IVDR where applicable) |
| EU AI | Regulation (EU) 2024/1689 (AI Act) |
| EU privacy | Regulation (EU) 2016/679 (GDPR) |
| Risk management | ISO 14971:2019, ISO/TR 24971:2020 |
| Quality management | ISO 13485:2016 |
| Software lifecycle | IEC 62304:2006 + A1:2015, IEC 82304-1:2016 |
| Usability | IEC 62366-1:2015 + A1:2020 |
| Clinical evaluation (AI) | DECIDE-AI, CONSORT-AI, SPIRIT-AI, TRIPOD+AI |
| Model reporting | *Model Cards for Model Reporting* (Mitchell et al., 2019), *Datasheets for Datasets* (Gebru et al., 2021) |

## Non-goals of this folder

- It does not constitute a regulatory submission dossier.
- It does not pre-determine the classification or pathway that a notified body or the FDA would assign to a commercial version.
- It does not replace engagement with qualified regulatory counsel or a clinical evaluator.
