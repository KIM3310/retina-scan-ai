# Case Report Form (CRF)

Per-subject data collection form for the Retina Scan AI validation study.

## Identifiers

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| subject_id | String | Yes | Site-local ID; never PHI |
| site_id | String | Yes | Enrolling site code |
| enrollment_date | Date | Yes | YYYY-MM-DD |
| consent_version | String | Yes | Consent form version |
| consent_signed_date | Date | Yes | |

## Demographics

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| age_bucket | Enum | Yes | 18-39, 40-59, 60-79, 80+ |
| sex | Enum | Yes | male, female, other, prefer_not_to_say |
| ethnicity | String | Yes | Site-adapted to local classifications |
| prior_eye_disease_history | Bool | Yes | |
| diabetes_history | Bool | Yes | |
| smoking_status | Enum | No | never, former, current, unknown |

## Imaging

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| eye | Enum | Yes | left, right |
| camera_manufacturer | String | Yes | Topcon, Canon, Zeiss, iCare, Other |
| camera_model | String | Yes | Free text |
| image_capture_date | Date | Yes | |
| image_gradeable | Bool | Yes | Yes means image quality sufficient for grading |
| ungradeable_reason | String | If not gradeable | poor_focus, opacity, misalignment, other |
| dicom_study_uid | String | Yes | For linkage to image store |

## Ground truth (panel adjudication)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| adjudicator_1_id | String | Yes | De-identified grader ID |
| adjudicator_2_id | String | Yes | |
| adjudicator_3_id | String | Yes | |
| grader_1_diagnoses | List | Yes | Subset of {Normal, DR, Glaucoma, Cataract, AMD} |
| grader_2_diagnoses | List | Yes | |
| grader_3_diagnoses | List | Yes | |
| consensus_diagnoses | List | Yes | Final adjudicated set |
| consensus_reached_by | Enum | Yes | unanimous, majority, panel_meeting |
| consensus_date | Date | Yes | |
| any_disagreement | Bool | Yes | |

## Model inference (captured after ground truth is locked)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| model_version | String | Yes | Git SHA |
| weights_sha256 | String | Yes | Weights file hash |
| inference_date | Date | Yes | |
| predicted_probabilities | Object | Yes | {"Normal": 0.02, "DR": 0.87, "Glaucoma": 0.05, "Cataract": 0.04, "AMD": 0.02} |
| predicted_top_class | Enum | Yes | Highest probability class |
| predicted_classes_above_threshold | List | Yes | Classes above operating threshold |
| inference_latency_ms | Float | Yes | |
| gradcam_path | String | No | Path to stored Grad-CAM image |

## Clinical context (standard-of-care outcome, not used for evaluation)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| clinician_final_diagnosis | List | Yes | Treating clinician's diagnosis (for outcome tracking, not for model evaluation) |
| followup_imaging_scheduled | Bool | No | |
| referral_to_specialist | Bool | No | |
| treatment_initiated | Bool | No | |

## Adverse events and protocol deviations

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| adverse_event_occurred | Bool | Yes | |
| adverse_event_description | String | If AE occurred | |
| protocol_deviation | Bool | Yes | |
| protocol_deviation_description | String | If deviation | |

## Quality checks built into the CRF

- `image_gradeable = false` must have an `ungradeable_reason`.
- `consensus_reached_by = majority` is acceptable; `consensus_reached_by = none` blocks submission.
- `predicted_top_class` must be one of 5 allowed classes.
- `consensus_diagnoses` must be a non-empty list (Normal alone is a valid consensus).
- `adverse_event_occurred = true` triggers escalation to PI within 24 hours.

## Timing

- CRF completed within 14 days of image capture for demographics, imaging, clinical context.
- Ground truth section completed within 30 days of imaging.
- Model inference section completed after ground truth is locked.
- All fields locked 90 days after last enrollment.

## Data format

CRF implemented in REDCap (default) or equivalent. Export schema matches `results-template.json`. Site data manager verifies completeness monthly.
