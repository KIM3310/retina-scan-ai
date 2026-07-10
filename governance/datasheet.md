# Datasheet — ODIR-5K (as used by Retina Scan AI)

> Gebru-style datasheet per Gebru et al. (2021), *Datasheets for Datasets*. This documents the ODIR-5K dataset **as used** by the Retina Scan AI training pipeline, including filtering and re-labelling steps applied on top of the upstream dataset.

## 1. Motivation

### 1.1 For what purpose was the dataset created?

The Ocular Disease Intelligent Recognition (ODIR-5K) dataset was created to support research in automated screening of multiple ocular diseases from colour fundus photography. It was released publicly by Peking University in support of the International Competition on Ocular Disease Intelligent Recognition (2019).

### 1.2 Who created the dataset, and on behalf of which entity?

ODIR-5K was created by Peking University (Beijing, China) as the organiser of the competition. The underlying images were collected from "Shanggong Medical Technology Co., Ltd." across several medical centres in China.

### 1.3 Who funded the creation of the dataset?

Funded via the research / competition programme at Peking University. See the ODIR-5K competition page for details.

### 1.4 Any other comments?

ODIR-5K is a common teaching / reference dataset. It is widely used as a starting point and not, by itself, an adequate basis for clinical validation. Its size (~5000 images) and source homogeneity (single geographic region, small set of fundus cameras) mean that performance metrics on ODIR-5K are a lower-bound sanity check, not a generalisation claim.

## 2. Composition

### 2.1 What do the instances that comprise the dataset represent?

Each instance is a digital colour fundus photograph of a single eye (left or right) of a single adult patient, accompanied by clinician-provided labels covering eight upstream disease categories.

### 2.2 How many instances are there in total?

Approximately 5000 patients, each with two eyes (left and right), producing ~10,000 fundus images. Our re-labelling and filtering to a single primary disease per eye retains approximately 3500 images suitable for the five-class supervised training task.

### 2.3 Does the dataset contain all possible instances, or is it a sample of instances from a larger set?

A sample. The original collection is from a subset of Chinese clinical sites; it is not a census of global fundus imagery or of the full disease spectrum.

### 2.4 What data does each instance consist of?

- Fundus image (JPEG, variable resolution)
- Upstream label(s) across eight categories (Normal, Diabetes, Glaucoma, Cataract, AMD, Hypertension, Myopia, Other)
- Patient sex
- Patient age (years)
- Eye (left / right)

### 2.5 Is there a label or target associated with each instance?

Yes — the upstream eight-class labels. Retina Scan AI re-maps these to the five-class taxonomy:

| Retina Scan class | Derived from ODIR-5K upstream labels |
|-------------------|-------------------------------------|
| Normal | "Normal" |
| Diabetic Retinopathy | "Diabetes" (for images with DR findings per upstream annotation) |
| Glaucoma | "Glaucoma" |
| Cataract | "Cataract" |
| AMD | "AMD" |

Hypertension, Myopia, and Other are excluded from the 5-class training set (filtered out).

### 2.6 Is any information missing from individual instances?

- Ethnicity is not provided (the DICOM tag 0010,2160 is absent from most JPEGs)
- Detailed grading (e.g. ICDR stage for DR) is not provided
- Camera model is not recorded at the per-instance level in the public release
- Time of imaging is not recorded
- Visual acuity and other clinical correlates are not provided
- Co-occurring conditions (e.g. DR + cataract) are represented inconsistently

### 2.7 Are relationships between individual instances made explicit?

Yes — left and right eyes of the same patient share a patient identifier in the upstream dataset. Our patient-level split preserves this grouping so that left and right eyes of the same patient cannot appear across train/val/test boundaries.

### 2.8 Are there recommended data splits?

ODIR-5K competition specified its own splits. We adopt a custom patient-level 70/15/15 split for reproducibility within this repository. The competition splits are not honoured because we have changed the task (5-class rather than 8-class).

### 2.9 Are there any errors, sources of noise, or redundancies in the dataset?

- Label noise: estimated from small-scale re-annotation exercises to be ~3–5% for borderline cases
- Co-occurring conditions: approximately 8% of original images have multiple upstream labels; we resolve to the primary label by a clinical-priority rule
- Image quality varies — some images have significant media opacity, eccentric gaze, or artefacts
- Occasional duplicate images (same patient, same eye, near-duplicate acquisition) — deduplicated in preprocessing

### 2.10 Is the dataset self-contained?

Yes, the public ODIR-5K package is self-contained. No external lookups required for training.

### 2.11 Does the dataset contain data that might be considered confidential?

The upstream release is stated to be de-identified. Patient name, MRN, and hospital identifiers are not present in the public release. The biometric character of fundus vasculature (discussed in [`../compliance/phi-handling.md`](../compliance/phi-handling.md)) remains a residual consideration when combining ODIR-5K with other datasets.

### 2.12 Does the dataset contain data that might be offensive, insulting, threatening, or cause anxiety?

Clinical findings are described in neutral medical terms. No content that is gratuitously disturbing beyond normal medical imagery.

### 2.13 Does the dataset identify subpopulations?

Sex and age are recorded. Ethnicity is not.

### 2.14 Is it possible to identify individuals from the dataset?

Direct identifiers (name, MRN) are stripped. Indirect re-identification via the biometric character of retinal vasculature is theoretically possible if another identified fundus image of the same individual is available. This is a known limitation across fundus datasets.

### 2.15 Does the dataset contain data that might be considered sensitive?

Health data is sensitive under GDPR Article 9. Biometric identifiers are also special category. ODIR-5K is distributed under the premise of research use; any clinical deployment requires a separate clinical dataset under appropriate consent.

## 3. Collection Process

### 3.1 How was the data associated with each instance acquired?

Collected from participating Chinese clinics and hospitals as part of routine ophthalmic imaging. Images were labelled by ophthalmologists at the contributing institutions; details of inter-rater agreement are not published.

### 3.2 What mechanisms or procedures were used to collect the data?

Fundus cameras in routine clinical use at the contributing sites. Specific camera models not published at per-instance level.

### 3.3 If the dataset is a sample from a larger set, what was the sampling strategy?

Undocumented in the public release beyond "representative clinical cases." This is a limitation; the sample is likely shaped by availability and selection by the contributing institutions.

### 3.4 Who was involved in the data collection process?

Ophthalmologists at participating institutions (data collection); the upstream organisers (aggregation and curation).

### 3.5 Over what timeframe was the data collected?

Not specified in public release; inferred to be 2010s-era clinical imaging.

### 3.6 Were any ethical review processes conducted?

Stated to have been conducted by the upstream organisers. Formal IRB protocol not published in the public release.

### 3.7 Did you collect the data from the individuals directly, or obtain it via third parties?

Obtained via the public ODIR-5K release (third-party source; originally collected from patients by clinical sites).

### 3.8 Were the individuals notified about the data collection?

Not independently verifiable for downstream users. Clinical imaging is typically covered by general consent for care; use for model training would typically require additional consent or appropriate ethics approval.

### 3.9 Did the individuals consent to the collection and use of their data?

Per upstream release framing, research use is assumed to be covered. Specific consent documentation is not redistributed with the dataset.

### 3.10 If consent was obtained, were individuals provided with a mechanism to revoke consent?

Not independently verifiable at the downstream user's layer.

### 3.11 Has an analysis of the potential impact of the dataset and its use on data subjects been conducted?

Not published with the upstream release. Retina Scan AI's DPIA [`../compliance/gdpr-dpia.md`](../compliance/gdpr-dpia.md) covers the downstream processing impact, not the upstream collection.

## 4. Preprocessing / Cleaning / Labeling

### 4.1 Was any preprocessing/cleaning/labeling of the data done?

Yes. Our pipeline applies:

1. **Filtering** — images with upstream labels outside the 5-class scope are excluded
2. **Multi-label resolution** — images with multiple upstream findings: resolved to primary class by clinical-priority rule (e.g. DR dominates over comorbid cataract for training purposes; a separate "comorbid" flag is maintained for analysis)
3. **Quality filtering** — images rejected by an automatic quality heuristic (very low contrast, completely black, or > 60% non-fundus pixels) are excluded
4. **Deduplication** — near-duplicate images by perceptual hash are removed
5. **Resolution normalisation** — resize to 224×224 with aspect-ratio-preserving crop to the circular fundus region
6. **Colour normalisation** — ImageNet mean/std normalisation
7. **Label encoding** — sparse integer encoding into the 5-class taxonomy

### 4.2 Was the "raw" data saved in addition to the preprocessed/cleaned/labeled data?

The raw ODIR-5K archive is retained separately and referenced by checksum; preprocessed tensors are derived at training time (not persistently stored) to avoid an extra copy of PHI-adjacent data.

### 4.3 Is the software used to preprocess/clean/label the data available?

Yes — `src/dataset.py` in this repository performs the training-time preprocessing and augmentation. Labelling is encoded in `scripts/download_data.py`.

### 4.4 Any other comments?

The choice to collapse to 5 classes reduces clinical fidelity (no DR severity grading, no myopia, no hypertensive retinopathy). This is an explicit trade-off for pipeline simplicity; production deployment would typically expand the taxonomy.

## 5. Uses

### 5.1 Has the dataset been used for any tasks already?

ODIR-5K has been widely used in academic literature. Our reference model (Retina Scan AI v1.0) is the use within this repository.

### 5.2 Is there a repository that links to any or all papers or systems that use the dataset?

The ODIR-5K competition page and academic search tools (Google Scholar) surface numerous citations.

### 5.3 What (other) tasks could the dataset be used for?

- Disease-specific binary classification (e.g. DR vs. not-DR)
- Severity grading (if supplementary annotations are obtained)
- Self-supervised pretraining for downstream fundus tasks
- Segmentation (if segmentation masks are obtained)
- Image quality estimation

### 5.4 Is there anything about the composition of the dataset or the way it was collected and preprocessed/cleaned/labeled that might impact future uses?

Yes — the geographic concentration (East Asian) and camera-model distribution (not published but likely narrow) limits generalisation. Models trained on ODIR-5K alone tend to underperform on other populations. This is documented in [`bias-and-limitations.md`](bias-and-limitations.md).

### 5.5 Are there tasks for which the dataset should not be used?

- Deployment as a clinical tool without additional validation on the deployment population
- Claims of performance on populations not represented in the dataset
- Inferring epidemiological prevalence of disease
- Use in legal or forensic contexts
- Biometric identification tasks

### 5.6 Any other comments?

ODIR-5K is a starting point, not a finishing line, for any clinical-grade training.

## 6. Distribution

### 6.1 Will the dataset be distributed to third parties outside of the entity on behalf of which it was created?

ODIR-5K is already publicly distributed by the upstream organisers.

### 6.2 How will the dataset be distributed?

Upstream: public release.
Our preprocessing pipeline: embedded in the repository.

### 6.3 When will the dataset be distributed?

Already distributed upstream.

### 6.4 Will the dataset be distributed under a copyright or other intellectual property licence, and/or under applicable terms of use?

Refer to the ODIR-5K competition licence terms at the upstream source. Our repository's licence covers our preprocessing code, not the upstream images.

### 6.5 Have any third parties imposed IP-based or other restrictions on the data associated with the instances?

Refer to upstream licence terms.

### 6.6 Do any export controls or other regulatory restrictions apply?

General export controls on cryptographic software apply to the repository code; the dataset itself (non-government, research medical imaging) is not typically export controlled.

## 7. Maintenance

### 7.1 Who will be supporting/hosting/maintaining the dataset?

Upstream: Peking University and competition organisers.
Our preprocessing: the Retina Scan AI repository maintainers.

### 7.2 How can the owner/curator/manager of the dataset be contacted?

ODIR-5K: via the competition page.
Our pipeline: GitHub issues on the repository.

### 7.3 Is there an erratum?

Not published by upstream as of writing. Our issues tracker serves as the erratum channel for the preprocessing pipeline.

### 7.4 Will the dataset be updated?

Upstream: no known update schedule.
Our pipeline: updated as preprocessing improves.

### 7.5 If the dataset relates to people, are there applicable limits on the retention of the data?

For any deployment using real patient data, retention must follow the hospital's data retention policy and applicable regulation. For ODIR-5K training use, the public release terms apply.

### 7.6 Will older versions of the dataset continue to be supported?

Upstream: not specified.
Our pipeline: versioned via the repository.

### 7.7 If others want to extend/augment/build on/contribute to the dataset, is there a mechanism for them to do so?

Upstream: not typically; the release is a snapshot.
Our pipeline: standard repository contribution flow.

## 8. Retina Scan AI-specific datasheet addenda

### 8.1 External validation cohort

A separate ~300-image external test set is assembled for sanity-checking generalisation. This cohort is described in summary terms for this repository and is not included in the public repository. Composition:

| Attribute | Distribution |
|-----------|--------------|
| Geography | Not South/East Asia |
| Camera models | At least one non-overlapping with ODIR-5K |
| Age | 40–85, skewing older |
| Sex | Approx 50/50 |
| Class distribution | Approximately stratified |

### 8.2 Synthetic data utility for pipeline testing

The repository includes `scripts/download_data.py --synthetic` to generate synthetic noise images under the expected folder structure. These are for pipeline smoke-testing only; model outputs on synthetic images have no clinical meaning.

### 8.3 Class distribution (training)

Illustrative, from the reference ODIR-5K 5-class filtering:

| Class | Count |
|-------|-------|
| Normal | 1200 |
| Diabetic Retinopathy | 850 |
| Glaucoma | 520 |
| Cataract | 480 |
| AMD | 450 |
| Total | 3500 |

Class imbalance is addressed by weighted sampling during training; precise weights are in `src/train.py`.

### 8.4 Subgroup distribution

| Subgroup | Distribution |
|----------|--------------|
| Age < 40 | 8% |
| Age 40–59 | 32% |
| Age 60–74 | 44% |
| Age ≥ 75 | 16% |
| Sex Male | 52% |
| Sex Female | 47% |
| Sex Not recorded | 1% |

### 8.5 Known problems in the dataset

- Multi-finding cases resolved by rule, introducing minor label noise
- Occasional mislabelling evidenced during clinical review
- Near-duplicate pairs across train/test boundary in the raw release (mitigated by patient-level split)

## 9. Review

Datasheet is reviewed:
- On any change to filtering or preprocessing
- On any addition of external data
- Annually at minimum

## 10. References

- Gebru, T. et al. (2021). *Datasheets for Datasets.* Communications of the ACM.
- ODIR-5K competition page (Peking University / Shanggong Medical Technology Co., Ltd.)
- Rogers, T. W. et al. (2019). *Predicting progression of age-related macular degeneration from fundus images using deep learning.* (Reference for AMD baseline.)
