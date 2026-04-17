# EU MDR — CE Marking Considerations

> **Educational reference only.** EU medical device regulation is evolving rapidly (AI Act entering into force, MDCG guidance updates). A real CE marking campaign requires engagement with a notified body, a qualified Person Responsible for Regulatory Compliance (PRRC) per MDR Article 15, and current-state review of MDCG guidance.

## 1. Applicable regulations

| Regulation | Relevance |
|------------|-----------|
| Regulation (EU) 2017/745 — Medical Device Regulation (MDR) | Primary device regulation; in full application since 26 May 2021 with extended transitional arrangements per Reg. (EU) 2023/607 |
| Regulation (EU) 2017/746 — In Vitro Diagnostic Regulation (IVDR) | Not directly applicable — fundus imaging is in vivo |
| Regulation (EU) 2016/679 — GDPR | Always applicable; see [`gdpr-dpia.md`](gdpr-dpia.md) |
| Regulation (EU) 2024/1689 — AI Act | Applicable; see §5 below |
| MDCG 2019-11 | Qualification and classification of software — MDR/IVDR |
| MDCG 2021-24 | Classification of medical devices |
| MDCG 2022-2 | Guidance on general principles of clinical evidence for MD under MDR |
| MDCG 2020-18 | Clinical evaluation — MD under MDR |

## 2. Is it a device under MDR?

MDR Article 2(1) defines a medical device. Software intended for "diagnosis, prevention, monitoring, prediction, prognosis, treatment or alleviation of disease" is a device. MDCG 2019-11 § 3.3 confirms that software providing clinical decision support through classification of medical images is a Medical Device Software (MDSW).

Retina Scan AI is an MDSW when deployed for clinical decision support.

## 3. Classification under MDR — Rule 11

MDR Annex VIII Rule 11 is the software-specific rule:

> Software intended to provide information which is used to take decisions with diagnosis or therapeutic purposes is classified as class IIa, except if such decisions have an impact that may cause:
> - death or an irreversible deterioration of a person's state of health, in which case it is in class III; or
> - a serious deterioration of a person's state of health or a surgical intervention, in which case it is classified as class IIb.
> Software intended to monitor physiological processes is classified as class IIa, except if it is intended for monitoring of vital physiological parameters, where the nature of variations of those parameters is such that it could result in immediate danger to the patient, in which case it is classified as class IIb.
> All other software is classified as class I.

For Retina Scan AI:

| Class | Fit | Reasoning |
|-------|-----|-----------|
| Class I | No | Clinical decision support excludes Class I per Rule 11 first clause |
| Class IIa | **Likely** | Provides information used for diagnostic decisions; missed findings lead to delayed referral, typically not immediate death |
| Class IIb | Plausible | Untreated proliferative DR or late AMD leads to irreversible sight loss — "serious deterioration" is arguable |
| Class III | Possible under strict reading | If a missed finding would produce "irreversible deterioration" in realistic pathway, Class III |

The conservative defensible position is **Class IIb**. MDCG 2019-11 Annex examples § 4.3 specifically call out "software intended to provide information used to take decisions with diagnostic purposes in ophthalmology" as an MDSW example, and MDCG has clarified in FAQs that sight-threatening conditions push toward IIb rather than IIa.

Class IIa and IIb both require a **notified body** for CE marking.

## 4. Conformity assessment pathway

For Class IIb, MDR Annex IX (full QMS + technical documentation assessment) or Annex XI (QMS + type examination) are the available pathways. Typical industry choice is **Annex IX Chapter I (QMS) + Chapter III (surveillance)**.

### 4.1 Notified body landscape

As of early 2026, the European Commission's NANDO database lists notified bodies designated under MDR with software scope. Capacity is constrained; lead times commonly 12–24 months. Common NBs engaged for medical software: BSI (NL, UK), TÜV SÜD (DE), TÜV Rheinland (DE), DNV (NO), Intertek (UK).

### 4.2 QMS requirement

ISO 13485:2016 is the harmonised standard under the MDR for quality management systems. A certified ISO 13485 QMS is de facto required before a notified body will proceed.

### 4.3 Technical documentation (Annex II + III)

Required technical file content. Columns show where this repository starts the documentation.

| Annex II section | Content | This repo |
|------------------|---------|-----------|
| 1. Device description and specification | Description, intended purpose, classification, variants | `governance/model-card.md`, `README.md` |
| 2. Information supplied by manufacturer | Labelling, IFU, UDI | Operational |
| 3. Design and manufacturing information | Design history file, manufacturing sites | QMS artefact |
| 4. General Safety and Performance Requirements | GSPR checklist (Annex I) | See §6 below |
| 5. Benefit-risk analysis and risk management | ISO 14971 file | `risk/fmea.md`, `risk/iso14971-mapping.md` |
| 6. Product verification and validation | V&V file including clinical data | `tests/`, `validation/`, `src/evaluate.py` outputs |
| 6.1 Pre-clinical and clinical data | Bench testing, software V&V, clinical evaluation | `validation/study-protocol.md` |
| 6.2 Additional information for specific device categories | N/A | N/A |

### 4.4 Post-market (Annex III)

| Annex III section | Content | This repo |
|------------------|---------|-----------|
| 1.1 PMS Plan | Post-market surveillance plan | `docs/clinical/drift-monitoring.md`, `docs/clinical/incident-response.md` |
| 1.2 PMS Report / PSUR | Periodic Safety Update Report annually (Class IIb) | Operational |
| 1.3 PMCF Plan and Report | Post-market clinical follow-up | `validation/study-protocol.md` (extension) |

## 5. AI Act interaction

Under Regulation (EU) 2024/1689 Article 6(1), an AI system is classified as "high-risk" if:
1. It is intended to be used as a safety component of a product covered by Annex I Section A (includes MDR), and
2. That product is required to undergo a third-party conformity assessment

Retina Scan AI as a Class IIa or IIb MDSW triggers notified body assessment, therefore it is **high-risk** under the AI Act.

High-risk AI system obligations apply in addition to MDR:

| AI Act Article | Obligation | This repo |
|----------------|-----------|-----------|
| Art. 9 | Risk management system | `risk/iso14971-mapping.md` (extended to AI-specific risks) |
| Art. 10 | Data governance — training, validation, testing data quality | `governance/datasheet.md`, `governance/bias-and-limitations.md` |
| Art. 11 | Technical documentation (Annex IV) | Overlap with MDR technical file |
| Art. 12 | Record-keeping / automatic logs | `audit/logger.py` |
| Art. 13 | Transparency — information to deployers | `governance/model-card.md` |
| Art. 14 | Human oversight | `docs/clinical/clinician-in-the-loop.md` |
| Art. 15 | Accuracy, robustness, cybersecurity | `validation/`, `src/evaluate.py`, security in `access/` |
| Art. 17 | QMS (AI Act) | Can be integrated with ISO 13485 QMS per Art. 17(3) |
| Art. 26 | Deployer obligations — human oversight, log retention | `access/mfa-policy.md`, `audit/retention_policy.md` |
| Art. 43 | Conformity assessment — per MDR notified body (integrated assessment) | Via notified body |
| Art. 72 | Post-market monitoring | `docs/clinical/drift-monitoring.md` |

The AI Act allows integrated assessment with the MDR conformity assessment (Art. 43(3)), so the same notified body reviews both.

AI Act timelines: general-purpose AI obligations from 2 August 2025; high-risk under Annex I (which includes MDR devices) from 2 August 2027. This creates a two-year grace window for existing CE-marked devices to adapt.

## 6. General Safety and Performance Requirements (GSPR) — Annex I

Key GSPRs for software. Column mapping shows the evidence channel.

| GSPR | Requirement | Evidence |
|------|-------------|----------|
| Ch. I §1 | Devices shall achieve the performance intended | `validation/study-protocol.md` |
| Ch. I §3 | Reduce risks as far as possible | `risk/fmea.md` mitigations |
| Ch. I §4 | Risk management system in place | `risk/iso14971-mapping.md` |
| Ch. I §5 | Unacceptable risks reduced to acceptable | `risk/fmea.md` residual risk analysis |
| Ch. I §8 | Compatibility with other devices | DICOM conformance statement (outside repo) |
| Ch. II §14 | Construction and interaction with environment | N/A for pure software |
| Ch. II §17 | **Electronic programmable systems and software** — full section applies | Detailed below |
| Ch. III §18 | Diagnostic and therapeutic devices — performance | `validation/study-protocol.md` |
| Ch. III §20 | Protection against risks posed by devices intended for use by lay persons | N/A — professional use only |
| Ch. III §23 | Information supplied with the device (labelling, IFU) | `governance/model-card.md`, `clinical_ui/` |

### GSPR Annex I Ch. II §17 — Software

§17.1 requires software to be designed and manufactured in accordance with the state of the art considering principles of development lifecycle, risk management, verification and validation. Evidence: IEC 62304 lifecycle (documented in ISO 13485 QMS).

§17.2 requires software to be developed to ensure repeatability, reliability and performance. Evidence: deterministic inference (seeded if stochastic), regression tests.

§17.4 for software intended to run with mobile platforms — not applicable, deployed server-side.

## 7. Unique Device Identifier (UDI)

MDR Articles 27–29 require each device to carry a UDI. For software (MDSW), UDI applies at the level of the software release. The UDI-DI changes with each major software version; the UDI-PI may include version number and manufacture date. For Class IIb software, UDI data must be submitted to EUDAMED.

## 8. Person Responsible for Regulatory Compliance (PRRC)

MDR Article 15 requires manufacturers to have within their organisation at least one PRRC with specified qualifications (diploma plus experience in regulatory or quality). Micro and small enterprises may use a PRRC permanently available via contract.

## 9. EUDAMED

Several EUDAMED modules are live as of 2026 (Actors, UDI/Devices, Certificates, Vigilance). Full mandatory use is being phased in; PRRC should monitor current status.

## 10. Clinical evaluation

Per MDR Article 61 and Annex XIV, clinical evaluation is required. For novel AI devices with limited equivalent devices on the market, clinical investigation under MDR Article 62 (with associated ISO 14155 compliance) is usually required.

Clinical evaluation plan (CEP) elements:
1. Identification of clinical data needs
2. Scope of evaluation
3. Identification of equivalent devices (if any)
4. Clinical investigation design — see `validation/study-protocol.md`
5. Review of scientific literature
6. Risk-benefit analysis
7. PMCF (post-market clinical follow-up) approach

The scope parallels the FDA pathway in `fda-samd-considerations.md` §10; data can often be re-used between submissions with care.

## 11. Language requirements

Labelling and IFU must be in the official language(s) of each Member State of placement on market, subject to individual Member State transposition. For a pan-EU launch, 24+ language versions may be required.

## 12. Surveillance & Vigilance

MDR Articles 87–92 set out the vigilance system:

- Serious incidents must be reported within defined timelines (10 days, 15 days, or 2 days depending on severity and public-health implications)
- Field Safety Corrective Actions (FSCA) reported immediately
- Periodic Safety Update Report (PSUR) annually for Class IIb

## 13. UK-specific — UKCA

Post-Brexit, GB placing-on-market requires UKCA mark. MHRA has extended CE mark recognition through December 2030 but a domestic pathway (UK MDR 2002 as amended; forthcoming UK MDR 2025) is emerging. Track MHRA guidance for timeline.

## 14. Revision history

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-04 | Initial draft |

## 15. What this file is not

This file is not a regulatory strategy, not a clinical evaluation plan, not a QMS procedure, and not legal advice. It describes the shape of the regulatory envelope so that engineering decisions in this repository align with the direction that any real commercialisation would take.
