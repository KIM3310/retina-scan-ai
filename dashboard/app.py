"""Streamlit clinician dashboard for Retina-Scan-AI.

Provides a clinician-facing interface for:
- Uploading retinal fundus images
- Viewing disease classification and severity results
- Reviewing patient risk scores
- Reading AI-generated clinical reports
- Batch processing multiple images

HIPAA-aware: no patient PII displayed or stored in session state.
"""

from __future__ import annotations

import io

import numpy as np
import streamlit as st
from PIL import Image

# Import directly (bypasses API for demo mode dashboard)
from app.models.classifier import DiseaseLabel, RetinalClassifier
from app.models.risk_scoring import ClinicalMetadata, RiskScorer
from app.models.severity import SeverityGrader
from app.preprocessing.pipeline import RetinalPreprocessor
from app.reporting.clinical_report import ClinicalReportGenerator

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Retina-Scan-AI | Clinical Dashboard",
    page_icon="👁",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Color palette for disease labels ─────────────────────────────────────────
DISEASE_COLORS = {
    "normal": "#2ecc71",
    "diabetic_retinopathy": "#e74c3c",
    "glaucoma": "#e67e22",
    "amd": "#9b59b6",
    "cataracts": "#3498db",
}

SEVERITY_COLORS = {
    "none": "#2ecc71",
    "mild": "#f1c40f",
    "moderate": "#e67e22",
    "severe": "#e74c3c",
    "proliferative": "#8e44ad",
    "advanced": "#c0392b",
    "vision_threatening": "#641e16",
}

RISK_COLORS = {
    "low": "#2ecc71",
    "moderate": "#f1c40f",
    "high": "#e67e22",
    "critical": "#e74c3c",
}


# ── Component initialization (cached) ────────────────────────────────────────
@st.cache_resource
def load_components():
    return {
        "classifier": RetinalClassifier(demo_mode=True),
        "severity_grader": SeverityGrader(),
        "risk_scorer": RiskScorer(),
        "preprocessor": RetinalPreprocessor(),
        "report_generator": ClinicalReportGenerator(),
    }


def colored_badge(text: str, color: str) -> str:
    return (
        f'<span style="background-color:{color};color:white;padding:4px 10px;'
        f'border-radius:12px;font-weight:bold;font-size:0.9em;">{text.upper()}</span>'
    )


def render_probability_bars(probs: dict[str, float]) -> None:
    """Render horizontal probability bars for each disease class."""
    sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    for label, prob in sorted_probs:
        display = label.replace("_", " ").title()
        color = DISEASE_COLORS.get(label, "#95a5a6")
        st.markdown(
            f"""
            <div style="margin:4px 0">
              <span style="display:inline-block;width:220px;font-size:0.85em">{display}</span>
              <span style="display:inline-block;width:{int(prob*300)}px;height:16px;
                background:{color};border-radius:3px;vertical-align:middle"></span>
              <span style="margin-left:6px;font-size:0.85em;font-weight:bold">{prob:.1%}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def run_analysis(
    image: Image.Image,
    components: dict,
    metadata: ClinicalMetadata | None = None,
    study_id: str = "DEMO-001",
) -> dict:
    """Run full analysis pipeline and return results dict."""
    preprocessor: RetinalPreprocessor = components["preprocessor"]
    classifier: RetinalClassifier = components["classifier"]
    grader: SeverityGrader = components["severity_grader"]
    scorer: RiskScorer = components["risk_scorer"]
    reporter: ClinicalReportGenerator = components["report_generator"]

    prep = preprocessor.process(image)
    arr = np.array(prep.processed_image)
    features = RetinalPreprocessor.extract_image_features(arr)

    classification = classifier.classify(prep.processed_image)
    severity = grader.grade(classification, features)
    risk = scorer.compute(classification, severity, metadata)
    report = reporter.generate(
        study_id=study_id,
        classification=classification,
        severity=severity,
        risk=risk,
        image_quality=prep.to_dict(),
    )

    return {
        "prep": prep,
        "classification": classification,
        "severity": severity,
        "risk": risk,
        "report": report,
    }


def main() -> None:
    components = load_components()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/retina-scan.png", width=80)
        st.title("Retina-Scan-AI")
        st.caption("v1.0 · Clinical Screening Tool")
        st.divider()

        st.subheader("Clinical Metadata")
        st.caption("Optional — improves risk stratification")
        study_id = st.text_input("Study ID (opaque)", value="STUDY-001", max_chars=32)
        patient_age = st.number_input("Patient Age", min_value=0, max_value=120, value=0, step=1)
        diabetes_duration = st.number_input(
            "Diabetes Duration (years)", min_value=0, max_value=80, value=0, step=1
        )
        hba1c = st.number_input("HbA1c (%)", min_value=0.0, max_value=20.0, value=0.0, step=0.1)
        has_hypertension = st.checkbox("Hypertension")
        is_smoker = st.checkbox("Current Smoker")
        family_history = st.checkbox("Family History of Eye Disease")

        st.divider()
        st.caption(
            "⚠ **Disclaimer**: AI screening tool only. "
            "Not for diagnostic use. Requires clinician review."
        )

    # ── Main content ──────────────────────────────────────────────────────────
    st.title("👁 Retina-Scan-AI — Clinical Dashboard")
    st.markdown(
        "Automated retinal disease screening · "
        "Diabetic Retinopathy · Glaucoma · AMD · Cataracts"
    )

    tab1, tab2, tab3 = st.tabs(["🔬 Single Analysis", "📊 Batch Processing", "ℹ System Info"])

    # ── Tab 1: Single image analysis ─────────────────────────────────────────
    with tab1:
        col_upload, col_preview = st.columns([1, 1])

        with col_upload:
            st.subheader("Upload Fundus Image")
            uploaded = st.file_uploader(
                "Upload retinal fundus image",
                type=["jpg", "jpeg", "png", "tiff", "bmp"],
                help="JPEG or PNG fundus photograph, ideally ≥ 800×800 px",
            )

            if uploaded:
                image = Image.open(io.BytesIO(uploaded.read())).convert("RGB")
                with col_preview:
                    st.subheader("Preview")
                    st.image(image, caption=f"Original: {image.size[0]}×{image.size[1]} px", use_container_width=True)

                # Build metadata
                metadata = ClinicalMetadata(
                    age=patient_age if patient_age > 0 else None,
                    diabetes_duration_years=diabetes_duration if diabetes_duration > 0 else None,
                    hba1c_percent=hba1c if hba1c > 0 else None,
                    has_hypertension=has_hypertension,
                    is_smoker=is_smoker,
                    family_history_eye_disease=family_history,
                )

                if st.button("Run Analysis", type="primary", use_container_width=True):
                    with st.spinner("Analyzing retinal image..."):
                        results = run_analysis(image, components, metadata, study_id)

                    st.success("Analysis complete!")

                    # ── Results ────────────────────────────────────────────
                    r_class = results["classification"]
                    r_sev = results["severity"]
                    r_risk = results["risk"]
                    r_report = results["report"]
                    r_prep = results["prep"]

                    st.divider()

                    # Classification card
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric("Diagnosis", r_class.display_name)
                        badge_color = DISEASE_COLORS.get(r_class.predicted_label.value, "#95a5a6")
                        st.markdown(
                            colored_badge(r_class.predicted_label.value.replace("_", " "), badge_color),
                            unsafe_allow_html=True,
                        )

                    with c2:
                        st.metric("Severity", r_sev.severity.value.title())
                        sev_color = SEVERITY_COLORS.get(r_sev.severity.value, "#95a5a6")
                        st.markdown(
                            colored_badge(r_sev.severity.value, sev_color),
                            unsafe_allow_html=True,
                        )

                    with c3:
                        st.metric("Risk Level", r_risk.risk_level.value.title())
                        risk_color = RISK_COLORS.get(r_risk.risk_level.value, "#95a5a6")
                        st.markdown(
                            colored_badge(r_risk.risk_level.value, risk_color),
                            unsafe_allow_html=True,
                        )

                    st.divider()

                    # Probabilities + details
                    left, right = st.columns(2)
                    with left:
                        st.subheader("Classification Probabilities")
                        render_probability_bars(r_class.probabilities)
                        st.caption(f"Confidence: {r_class.confidence:.1%} · ICD-10: {r_class.icd10_code}")
                        if r_class.requires_urgent_review:
                            st.error("⚠ Urgent clinical review required")

                    with right:
                        st.subheader("Risk Assessment")
                        st.progress(r_risk.raw_score, text=f"Risk Score: {r_risk.raw_score:.2f}")
                        st.caption(f"Recommended rescreening: {r_risk.screening_interval_months} months")
                        if r_risk.contributing_factors:
                            st.markdown("**Contributing factors:**")
                            for factor in r_risk.contributing_factors:
                                st.markdown(f"- {factor}")

                    st.divider()
                    st.subheader("Follow-up")
                    st.info(f"**Urgency:** {r_sev.follow_up_urgency}")
                    for rec in r_risk.recommendations:
                        st.markdown(f"• {rec}")

                    if r_class.predicted_label != DiseaseLabel.NORMAL and r_sev.etdrs_level:
                        st.caption(f"ETDRS Level: {r_sev.etdrs_level}")

                    # Preprocessed image
                    st.divider()
                    col_proc, col_qual = st.columns(2)
                    with col_proc:
                        st.subheader("Preprocessed Image")
                        st.image(
                            r_prep.processed_image,
                            caption="After CLAHE + vessel enhancement",
                            use_container_width=True,
                        )

                    with col_qual:
                        st.subheader("Image Quality")
                        st.progress(r_prep.quality_score, text=f"Quality: {r_prep.quality_score:.2f}")
                        if r_prep.quality_flags:
                            st.warning(f"Quality flags: {', '.join(r_prep.quality_flags)}")
                        else:
                            st.success("No quality issues detected")

                    # Full clinical report
                    st.divider()
                    st.subheader("Clinical Report")
                    with st.expander("View Full Clinical Report", expanded=False):
                        st.code(r_report.to_text(), language=None)

                    report_text = r_report.to_text()
                    st.download_button(
                        "Download Report (.txt)",
                        data=report_text,
                        file_name=f"retina_report_{r_report.report_id[:8]}.txt",
                        mime="text/plain",
                    )

    # ── Tab 2: Batch processing ───────────────────────────────────────────────
    with tab2:
        st.subheader("Batch Fundus Image Processing")
        st.info("Upload multiple fundus images for batch screening.")

        batch_files = st.file_uploader(
            "Upload multiple fundus images",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
        )

        if batch_files and st.button("Run Batch Analysis", type="primary"):
            results_list = []
            progress = st.progress(0)

            for i, f in enumerate(batch_files):
                img = Image.open(io.BytesIO(f.read())).convert("RGB")
                res = run_analysis(img, components, study_id=f"BATCH-{i+1:03d}")
                results_list.append((f.name, res))
                progress.progress((i + 1) / len(batch_files))

            st.success(f"Processed {len(results_list)} images")

            for fname, res in results_list:
                with st.expander(f"📄 {fname} — {res['classification'].display_name}"):
                    cols = st.columns(3)
                    cols[0].metric("Disease", res["classification"].display_name)
                    cols[1].metric("Severity", res["severity"].severity.value.title())
                    cols[2].metric("Risk", res["risk"].risk_level.value.title())
                    if res["classification"].requires_urgent_review:
                        st.error("⚠ Urgent review required")

    # ── Tab 3: System info ────────────────────────────────────────────────────
    with tab3:
        st.subheader("System Information")
        classifier: RetinalClassifier = components["classifier"]
        arch = classifier.get_model_architecture_summary()

        col_a, col_b = st.columns(2)
        with col_a:
            st.json(arch)
        with col_b:
            st.markdown("""
            **Supported Diseases**
            - Normal (Z01.01)
            - Diabetic Retinopathy (E11.319)
            - Glaucoma (H40.10X0)
            - AMD (H35.30)
            - Cataracts (H26.9)

            **Severity Grading**
            - DR: ETDRS-like (mild NPDR → PDR)
            - Glaucoma: mild → advanced
            - AMD: early → advanced
            - Cataracts: incipient → dense

            **Privacy & Compliance**
            - HIPAA-aware audit logging
            - No PII stored in system
            - Study ID only (opaque reference)
            """)


if __name__ == "__main__":
    main()
