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

import csv
import io
import io as _io
import sys
from pathlib import Path

# Ensure project root is on sys.path (needed for Streamlit Cloud deployment)
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

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

# ── Premium CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* ── Google Fonts ── */
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=DM+Serif+Display:ital@0;1&display=swap');

  /* ── CSS Variables ── */
  :root {
    --navy:            #0F1E35;
    --navy-mid:        #1B2A4A;
    --navy-light:      #243558;
    --clinical:        #4A90D9;
    --clinical-bright: #5BA3E8;
    --clinical-pale:   #A8CDEF;
    --accent:          #00C9A7;
    --urgent:          #FF4757;
    --warn:            #FFA502;
    --success:         #2ED573;
    --white:           #FFFFFF;
    --gray-100:        #F4F7FB;
    --gray-200:        #E8EDF5;
    --gray-300:        #CBD5E1;
    --gray-500:        #7A8BA8;
    --gray-700:        #3D4F6E;
    --card-bg:         #1A2B47;
    --card-border:     #253D63;
    --radius:          14px;
    --radius-sm:       8px;
    --shadow-card:     0 4px 24px rgba(0,0,0,0.28), 0 1px 4px rgba(0,0,0,0.18);
    --shadow-glow:     0 0 32px rgba(74,144,217,0.18);
    --transition:      all 0.22s cubic-bezier(0.4,0,0.2,1);
  }

  /* ── Base typography ── */
  html, body, [class*="css"] {
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    color: #CBD5E1;
  }

  /* ── App background ── */
  .stApp {
    background: linear-gradient(160deg, #0A1628 0%, #0F1E35 40%, #0D1B30 100%);
    min-height: 100vh;
  }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: #0F1E35; }
  ::-webkit-scrollbar-thumb { background: #2D4470; border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #4A90D9; }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0C1829 0%, #111E35 100%) !important;
    border-right: 1px solid #1E3054 !important;
  }
  [data-testid="stSidebar"] * { color: #CBD5E1 !important; }
  [data-testid="stSidebar"] h1,
  [data-testid="stSidebar"] h2,
  [data-testid="stSidebar"] h3 { color: #E8EDF5 !important; }
  [data-testid="stSidebar"] .stTextInput input,
  [data-testid="stSidebar"] .stNumberInput input {
    background: #1A2B47 !important;
    border: 1px solid #253D63 !important;
    border-radius: 8px !important;
    color: #E8EDF5 !important;
    padding: 8px 12px !important;
    font-family: 'DM Sans', sans-serif !important;
    transition: var(--transition);
  }
  [data-testid="stSidebar"] .stTextInput input:focus,
  [data-testid="stSidebar"] .stNumberInput input:focus {
    border-color: #4A90D9 !important;
    box-shadow: 0 0 0 3px rgba(74,144,217,0.18) !important;
    outline: none !important;
  }
  [data-testid="stSidebar"] label {
    color: #7A8BA8 !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
  }
  [data-testid="stSidebar"] .stCheckbox label {
    text-transform: none !important;
    font-size: 0.88rem !important;
    letter-spacing: normal !important;
    color: #A8B8CC !important;
  }

  /* ── Main content ── */
  .main .block-container {
    padding: 0 !important;
    max-width: 100% !important;
  }

  /* ── Tabs ── */
  .stTabs [data-baseweb="tab-list"] {
    background: rgba(15,30,53,0.85) !important;
    border-bottom: 1px solid #1E3054 !important;
    padding: 0 2rem !important;
    gap: 0 !important;
    backdrop-filter: blur(10px);
  }
  .stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    color: #7A8BA8 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    padding: 0.85rem 1.5rem !important;
    margin: 0 !important;
    transition: var(--transition);
  }
  .stTabs [aria-selected="true"] {
    color: #4A90D9 !important;
    border-bottom-color: #4A90D9 !important;
    background: transparent !important;
  }
  .stTabs [data-baseweb="tab"]:hover { color: #CBD5E1 !important; }
  .stTabs [data-baseweb="tab-panel"] {
    background: transparent !important;
    padding: 2rem !important;
  }

  /* ── Buttons ── */
  .stButton > button {
    background: linear-gradient(135deg, #4A90D9, #2B6CB0) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    padding: 0.6rem 1.4rem !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    letter-spacing: 0.02em !important;
    transition: var(--transition) !important;
    box-shadow: 0 2px 12px rgba(74,144,217,0.35) !important;
  }
  .stButton > button:hover {
    background: linear-gradient(135deg, #5BA3E8, #3A7CC5) !important;
    box-shadow: 0 4px 20px rgba(74,144,217,0.5) !important;
    transform: translateY(-1px) !important;
  }
  .stButton > button:active { transform: translateY(0) !important; }

  /* ── Download buttons ── */
  .stDownloadButton > button {
    background: rgba(0,201,167,0.1) !important;
    color: #00C9A7 !important;
    border: 1px solid rgba(0,201,167,0.3) !important;
    border-radius: var(--radius-sm) !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    transition: var(--transition) !important;
  }
  .stDownloadButton > button:hover {
    background: rgba(0,201,167,0.2) !important;
    border-color: rgba(0,201,167,0.6) !important;
    box-shadow: 0 2px 14px rgba(0,201,167,0.25) !important;
  }

  /* ── File uploader ── */
  [data-testid="stFileUploader"] {
    background: rgba(26,43,71,0.6) !important;
    border: 2px dashed #253D63 !important;
    border-radius: var(--radius) !important;
    padding: 1.5rem !important;
    transition: var(--transition) !important;
  }
  [data-testid="stFileUploader"]:hover {
    border-color: #4A90D9 !important;
    background: rgba(74,144,217,0.06) !important;
    box-shadow: var(--shadow-glow) !important;
  }

  /* ── Metrics (native) ── */
  [data-testid="stMetric"] {
    background: var(--card-bg) !important;
    border: 1px solid var(--card-border) !important;
    border-radius: var(--radius) !important;
    padding: 1.2rem 1.4rem !important;
    box-shadow: var(--shadow-card) !important;
  }
  [data-testid="stMetricLabel"] {
    color: #7A8BA8 !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
  }
  [data-testid="stMetricValue"] {
    color: #E8EDF5 !important;
    font-size: 1.5rem !important;
    font-weight: 700 !important;
  }

  /* ── Progress bar ── */
  .stProgress > div > div {
    background: linear-gradient(90deg, #4A90D9, #00C9A7) !important;
    border-radius: 4px !important;
  }
  .stProgress > div {
    background: #1A2B47 !important;
    border-radius: 4px !important;
  }

  /* ── Expander ── */
  .streamlit-expanderHeader {
    background: var(--card-bg) !important;
    border: 1px solid var(--card-border) !important;
    border-radius: var(--radius-sm) !important;
    color: #CBD5E1 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
  }
  .streamlit-expanderContent {
    background: rgba(26,43,71,0.5) !important;
    border: 1px solid #1E3054 !important;
    border-top: none !important;
    border-radius: 0 0 var(--radius-sm) var(--radius-sm) !important;
  }

  /* ── Code block ── */
  .stCodeBlock, pre, code {
    background: #0A1628 !important;
    border: 1px solid #1E3054 !important;
    border-radius: var(--radius-sm) !important;
    color: #A8CDEF !important;
    font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
    font-size: 0.79rem !important;
  }

  /* ── Divider ── */
  hr {
    border: none !important;
    border-top: 1px solid #1E3054 !important;
    margin: 1.5rem 0 !important;
  }

  /* ── JSON ── */
  [data-testid="stJson"] {
    background: #0A1628 !important;
    border-radius: var(--radius-sm) !important;
    border: 1px solid #1E3054 !important;
  }

  /* ── Caption ── */
  .stCaption, [data-testid="stCaptionContainer"] {
    color: #7A8BA8 !important;
    font-size: 0.78rem !important;
  }

  /* ── Text input / textarea ── */
  .stTextInput input, .stTextArea textarea {
    background: #1A2B47 !important;
    border: 1px solid #253D63 !important;
    border-radius: var(--radius-sm) !important;
    color: #E8EDF5 !important;
    font-family: 'DM Sans', sans-serif !important;
    transition: var(--transition);
  }
  .stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #4A90D9 !important;
    box-shadow: 0 0 0 3px rgba(74,144,217,0.15) !important;
  }

  /* ══════════════════════════════════════════
     CUSTOM COMPONENT CLASSES
  ══════════════════════════════════════════ */

  /* Hero */
  .hero-section {
    background: linear-gradient(135deg, #0C1829 0%, #1B2A4A 45%, #1A3052 100%);
    border-bottom: 1px solid #1E3054;
    padding: 2.5rem 2rem 2rem;
    position: relative;
    overflow: hidden;
  }
  .hero-section::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 320px; height: 320px;
    background: radial-gradient(circle, rgba(74,144,217,0.12) 0%, transparent 70%);
    pointer-events: none;
  }
  .hero-section::after {
    content: '';
    position: absolute;
    bottom: -40px; left: 30%;
    width: 280px; height: 280px;
    background: radial-gradient(circle, rgba(0,201,167,0.07) 0%, transparent 70%);
    pointer-events: none;
  }
  .hero-title {
    font-family: 'DM Serif Display', Georgia, serif !important;
    font-size: 2.4rem !important;
    font-weight: 400 !important;
    color: #F0F4F8 !important;
    letter-spacing: -0.02em !important;
    line-height: 1.15 !important;
    margin: 0 0 0.5rem 0 !important;
    text-shadow: 0 2px 20px rgba(0,0,0,0.4);
  }
  .hero-subtitle {
    font-size: 1rem;
    color: #7A8BA8;
    font-weight: 400;
    letter-spacing: 0.01em;
    margin-bottom: 1.8rem;
  }
  .hero-subtitle span { color: #4A90D9; font-weight: 500; }
  .stats-row { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-top: 1.2rem; }
  .stat-chip {
    background: rgba(74,144,217,0.1);
    border: 1px solid rgba(74,144,217,0.25);
    border-radius: 20px;
    padding: 0.35rem 0.85rem;
    font-size: 0.78rem;
    font-weight: 600;
    color: #A8CDEF;
    letter-spacing: 0.04em;
    backdrop-filter: blur(8px);
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }
  .stat-chip.accent {
    background: rgba(0,201,167,0.1);
    border-color: rgba(0,201,167,0.25);
    color: #00C9A7;
  }
  .stat-chip.warn {
    background: rgba(255,165,2,0.1);
    border-color: rgba(255,165,2,0.25);
    color: #FFA502;
  }

  /* Glass card */
  .glass-card {
    background: rgba(26,43,71,0.7);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid #253D63;
    border-radius: var(--radius);
    padding: 1.4rem;
    box-shadow: var(--shadow-card);
    transition: var(--transition);
  }
  .glass-card:hover {
    border-color: #3A5A8A;
    box-shadow: var(--shadow-card), 0 0 24px rgba(74,144,217,0.08);
  }
  .glass-card.urgent {
    border-color: rgba(255,71,87,0.4);
    background: rgba(255,71,87,0.06);
  }
  .glass-card.warn-card {
    border-color: rgba(255,165,2,0.3);
    background: rgba(255,165,2,0.05);
  }
  .glass-card.success {
    border-color: rgba(46,213,115,0.3);
    background: rgba(46,213,115,0.05);
  }

  /* Metric card (custom) */
  .metric-card {
    background: linear-gradient(145deg, #1A2B47, #162440);
    border: 1px solid #253D63;
    border-radius: var(--radius);
    padding: 1.4rem 1.5rem;
    box-shadow: var(--shadow-card);
    position: relative;
    overflow: hidden;
    transition: var(--transition);
    height: 100%;
  }
  .metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: var(--radius) var(--radius) 0 0;
  }
  .metric-card.blue::before  { background: linear-gradient(90deg, #4A90D9, #2B6CB0); }
  .metric-card.green::before { background: linear-gradient(90deg, #2ED573, #00A86B); }
  .metric-card.amber::before { background: linear-gradient(90deg, #FFA502, #E67E22); }
  .metric-card.red::before   { background: linear-gradient(90deg, #FF4757, #C0392B); }
  .metric-card.teal::before  { background: linear-gradient(90deg, #00C9A7, #009B7D); }
  .metric-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-card), 0 8px 32px rgba(0,0,0,0.2);
  }
  .metric-card-label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: #7A8BA8;
    margin-bottom: 0.5rem;
  }
  .metric-card-value {
    font-size: 1.55rem;
    font-weight: 700;
    color: #F0F4F8;
    line-height: 1.15;
  }
  .metric-card-sub {
    font-size: 0.76rem;
    color: #7A8BA8;
    margin-top: 0.3rem;
  }
  .metric-card-icon {
    position: absolute;
    top: 1.2rem; right: 1.2rem;
    font-size: 1.3rem;
    opacity: 0.3;
  }

  /* Disease badge */
  .disease-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.28rem 0.75rem;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  /* Section header */
  .section-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 1rem;
  }
  .section-header-icon {
    width: 26px; height: 26px;
    background: rgba(74,144,217,0.15);
    border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.85rem;
    flex-shrink: 0;
  }
  .section-header-text {
    font-size: 0.82rem;
    font-weight: 700;
    color: #E8EDF5;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  /* Timeline items */
  .timeline-item {
    display: flex;
    gap: 0.75rem;
    margin-bottom: 0.6rem;
    padding: 0.75rem 1rem;
    background: rgba(26,43,71,0.5);
    border-left: 3px solid #4A90D9;
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    font-size: 0.85rem;
    color: #A8B8CC;
    line-height: 1.55;
    transition: var(--transition);
  }
  .timeline-item:hover { background: rgba(74,144,217,0.08); }
  .timeline-item.urgent  { border-left-color: #FF4757; }
  .timeline-item.warn    { border-left-color: #FFA502; }
  .timeline-item.success { border-left-color: #2ED573; }
  .timeline-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #4A90D9;
    flex-shrink: 0;
    margin-top: 5px;
  }

  /* Sidebar elements */
  .sidebar-logo {
    background: linear-gradient(135deg, rgba(74,144,217,0.12), rgba(0,201,167,0.07));
    border: 1px solid rgba(74,144,217,0.2);
    border-radius: var(--radius);
    padding: 1rem 1.2rem;
    margin-bottom: 1rem;
    text-align: center;
  }
  .sidebar-logo-icon { font-size: 2rem; margin-bottom: 0.3rem; display: block; }
  .sidebar-logo-title {
    font-family: 'DM Serif Display', Georgia, serif;
    font-size: 1.15rem;
    color: #E8EDF5;
    letter-spacing: -0.01em;
  }
  .sidebar-logo-version {
    font-size: 0.7rem;
    color: #4A90D9;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-top: 0.2rem;
  }
  .sidebar-disclaimer {
    background: rgba(255,165,2,0.06);
    border: 1px solid rgba(255,165,2,0.18);
    border-radius: var(--radius-sm);
    padding: 0.85rem;
    font-size: 0.75rem;
    color: #A8956A;
    line-height: 1.5;
    margin-top: 0.5rem;
  }
  .sidebar-disclaimer strong { color: #FFA502; }

  /* Disease info card */
  .disease-info-card {
    background: linear-gradient(145deg, #1A2B47, #162440);
    border: 1px solid #253D63;
    border-radius: var(--radius);
    padding: 1.2rem;
    height: 100%;
    transition: var(--transition);
    margin-bottom: 0.75rem;
  }
  .disease-info-card:hover {
    border-color: #4A90D9;
    box-shadow: 0 4px 20px rgba(74,144,217,0.1);
    transform: translateY(-1px);
  }
  .disease-info-icon  { font-size: 1.4rem; margin-bottom: 0.45rem; }
  .disease-info-name  { font-weight: 700; color: #E8EDF5; font-size: 0.88rem; margin-bottom: 0.2rem; }
  .disease-info-icd   { font-size: 0.7rem; font-weight: 600; letter-spacing: 0.06em; margin-bottom: 0.45rem; }
  .disease-info-desc  { font-size: 0.77rem; color: #7A8BA8; line-height: 1.5; }

  /* Batch summary */
  .batch-summary-card {
    background: linear-gradient(145deg, #1A2B47, #162440);
    border: 1px solid #253D63;
    border-radius: var(--radius);
    padding: 1.2rem;
    text-align: center;
    transition: var(--transition);
  }
  .batch-summary-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-card); }
  .batch-num {
    font-size: 2.2rem;
    font-weight: 800;
    color: #F0F4F8;
    line-height: 1;
    font-family: 'DM Sans', sans-serif;
  }
  .batch-label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: #7A8BA8;
    margin-top: 0.3rem;
  }

  /* Compliance badge */
  .compliance-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: rgba(0,201,167,0.1);
    border: 1px solid rgba(0,201,167,0.25);
    border-radius: var(--radius-sm);
    padding: 0.4rem 0.85rem;
    font-size: 0.76rem;
    font-weight: 700;
    color: #00C9A7;
    letter-spacing: 0.05em;
  }

  /* Chat UI */
  .chat-container {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 1rem 0;
    max-height: 400px;
    overflow-y: auto;
  }
  .chat-bubble {
    max-width: 80%;
    padding: 0.75rem 1rem;
    border-radius: 16px;
    font-size: 0.86rem;
    line-height: 1.55;
  }
  .chat-bubble.user {
    background: linear-gradient(135deg, #2B6CB0, #4A90D9);
    color: white;
    align-self: flex-end;
    border-bottom-right-radius: 4px;
    box-shadow: 0 2px 12px rgba(74,144,217,0.3);
  }
  .chat-bubble.assistant {
    background: #1A2B47;
    color: #CBD5E1;
    align-self: flex-start;
    border-bottom-left-radius: 4px;
    border: 1px solid #253D63;
  }
  .chat-meta {
    font-size: 0.7rem;
    color: #4A6B8A;
    margin-top: 0.2rem;
  }
  .chat-meta.user { text-align: right; margin-right: 0.5rem; }
  .chat-meta.assistant { margin-left: 0.5rem; }

  /* Footer */
  .footer-bar {
    background: linear-gradient(90deg, #0C1829, #111E35, #0C1829);
    border-top: 1px solid #1E3054;
    padding: 1rem 2rem;
    text-align: center;
    font-size: 0.74rem;
    color: #4A6B8A;
    letter-spacing: 0.04em;
    margin-top: 2rem;
  }
  .footer-sep { color: #1E3054; margin: 0 0.5rem; }

  /* ══ Animations ══ */
  @keyframes fadeInUp {
    from { opacity: 0; transform: translateY(18px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes fadeInDown {
    from { opacity: 0; transform: translateY(-12px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes fadeInLeft {
    from { opacity: 0; transform: translateX(-20px); }
    to   { opacity: 1; transform: translateX(0); }
  }
  @keyframes fadeInRight {
    from { opacity: 0; transform: translateX(20px); }
    to   { opacity: 1; transform: translateX(0); }
  }
  @keyframes fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
  }
  @keyframes scaleIn {
    from { opacity: 0; transform: scale(0.92); }
    to   { opacity: 1; transform: scale(1); }
  }
  @keyframes slideUp {
    from { opacity: 0; transform: translateY(30px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes pulseGlow {
    0%, 100% { box-shadow: 0 0 0 0 rgba(255,71,87,0.4); }
    50%       { box-shadow: 0 0 0 10px rgba(255,71,87,0); }
  }
  @keyframes shimmer {
    0%   { background-position: -200% 0; }
    100% { background-position: 200% 0; }
  }
  @keyframes borderGlow {
    0%, 100% { border-color: rgba(74,144,217,0.2); }
    50%       { border-color: rgba(74,144,217,0.5); }
  }
  @keyframes float {
    0%, 100% { transform: translateY(0); }
    50%       { transform: translateY(-6px); }
  }
  @keyframes gradientShift {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
  }
  @keyframes typewriter {
    from { width: 0; }
    to   { width: 100%; }
  }

  /* Staggered fade-in-up */
  .anim-1 { animation: fadeInUp 0.55s cubic-bezier(0.22,1,0.36,1) both; }
  .anim-2 { animation: fadeInUp 0.55s 0.1s cubic-bezier(0.22,1,0.36,1) both; }
  .anim-3 { animation: fadeInUp 0.55s 0.2s cubic-bezier(0.22,1,0.36,1) both; }
  .anim-4 { animation: fadeInUp 0.55s 0.3s cubic-bezier(0.22,1,0.36,1) both; }
  .anim-fade { animation: fadeIn 0.5s ease both; }
  .anim-scale { animation: scaleIn 0.5s cubic-bezier(0.22,1,0.36,1) both; }
  .anim-left { animation: fadeInLeft 0.5s cubic-bezier(0.22,1,0.36,1) both; }
  .anim-right { animation: fadeInRight 0.5s cubic-bezier(0.22,1,0.36,1) both; }
  .anim-slide { animation: slideUp 0.6s cubic-bezier(0.22,1,0.36,1) both; }
  .urgent-pulse { animation: pulseGlow 2s ease-in-out infinite; }

  /* Hero gradient animation */
  .hero-section {
    background: linear-gradient(135deg, #0C1829 0%, #1B2A4A 45%, #1A3052 100%);
    background-size: 200% 200%;
    animation: gradientShift 8s ease infinite;
    border-bottom: 1px solid #1E3054;
    padding: 2.5rem 2rem 2rem;
    position: relative;
    overflow: hidden;
  }

  /* Floating orbs in hero */
  .hero-section::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 320px; height: 320px;
    background: radial-gradient(circle, rgba(74,144,217,0.14) 0%, transparent 70%);
    pointer-events: none;
    animation: float 6s ease-in-out infinite;
  }
  .hero-section::after {
    content: '';
    position: absolute;
    bottom: -40px; left: 30%;
    width: 280px; height: 280px;
    background: radial-gradient(circle, rgba(0,201,167,0.08) 0%, transparent 70%);
    pointer-events: none;
    animation: float 8s ease-in-out 1s infinite;
  }

  /* Hero title animation */
  .hero-title {
    animation: fadeInDown 0.7s cubic-bezier(0.22,1,0.36,1) both;
  }
  .hero-subtitle {
    animation: fadeIn 0.8s 0.2s ease both;
  }
  .stats-row {
    animation: fadeInUp 0.6s 0.4s cubic-bezier(0.22,1,0.36,1) both;
  }

  /* Stat chips hover */
  .stat-chip {
    transition: all 0.25s cubic-bezier(0.22,1,0.36,1);
    cursor: default;
  }
  .stat-chip:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(74,144,217,0.2);
  }

  /* Glass card hover lift */
  .glass-card {
    transition: all 0.3s cubic-bezier(0.22,1,0.36,1);
  }
  .glass-card:hover {
    transform: translateY(-2px);
    border-color: #3A5A8A;
    box-shadow: var(--shadow-card), 0 8px 32px rgba(74,144,217,0.1);
  }

  /* Disease info cards stagger + hover */
  .disease-info-card {
    transition: all 0.3s cubic-bezier(0.22,1,0.36,1);
    animation: scaleIn 0.4s cubic-bezier(0.22,1,0.36,1) both;
  }
  .disease-info-card:hover {
    transform: translateY(-4px) scale(1.01);
    border-color: #4A90D9;
    box-shadow: 0 8px 28px rgba(74,144,217,0.15);
  }

  /* Timeline items stagger */
  .timeline-item {
    animation: fadeInLeft 0.4s cubic-bezier(0.22,1,0.36,1) both;
    transition: all 0.25s cubic-bezier(0.22,1,0.36,1);
  }
  .timeline-item:hover {
    transform: translateX(4px);
    background: rgba(74,144,217,0.08);
  }

  /* Batch summary cards */
  .batch-summary-card {
    animation: scaleIn 0.45s cubic-bezier(0.22,1,0.36,1) both;
    transition: all 0.3s cubic-bezier(0.22,1,0.36,1);
  }
  .batch-summary-card:hover {
    transform: translateY(-4px) scale(1.02);
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  }

  /* Chat bubbles */
  .chat-bubble {
    animation: fadeInUp 0.35s cubic-bezier(0.22,1,0.36,1) both;
    transition: all 0.2s ease;
  }
  .chat-bubble.user:hover { transform: translateX(-3px); }
  .chat-bubble.assistant:hover { transform: translateX(3px); }

  /* Sidebar logo float */
  .sidebar-logo {
    animation: fadeIn 0.6s ease both;
    transition: all 0.3s ease;
  }
  .sidebar-logo:hover {
    transform: scale(1.02);
    box-shadow: 0 4px 20px rgba(74,144,217,0.15);
  }
  .sidebar-logo-icon {
    animation: float 4s ease-in-out infinite;
  }

  /* Compliance badges */
  .compliance-badge {
    animation: fadeInUp 0.4s cubic-bezier(0.22,1,0.36,1) both;
    transition: all 0.25s ease;
  }
  .compliance-badge:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,201,167,0.2);
  }

  /* Button shimmer effect */
  .stButton > button::after {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent);
    background-size: 200% 100%;
    animation: shimmer 3s ease-in-out infinite;
    border-radius: inherit;
    pointer-events: none;
  }
  .stButton > button { position: relative; overflow: hidden; }

  /* Footer subtle animation */
  .footer-bar {
    animation: fadeIn 0.8s 0.5s ease both;
  }

  /* Scrollbar glow on hover */
  ::-webkit-scrollbar-thumb:hover {
    background: #4A90D9;
    box-shadow: 0 0 8px rgba(74,144,217,0.4);
  }

  /* File uploader border animation */
  [data-testid="stFileUploader"] {
    animation: borderGlow 3s ease-in-out infinite;
  }
</style>
""", unsafe_allow_html=True)

import plotly.graph_objects as go

# ── Design tokens ─────────────────────────────────────────────────────────────
DISEASE_COLORS = {
    "normal":               "#2ED573",
    "diabetic_retinopathy": "#FF4757",
    "glaucoma":             "#FFA502",
    "amd":                  "#A78BFA",
    "cataracts":            "#4A90D9",
}
DISEASE_ICONS = {
    "normal":               "✓",
    "diabetic_retinopathy": "⚠",
    "glaucoma":             "◉",
    "amd":                  "◈",
    "cataracts":            "◎",
}
SEVERITY_COLORS = {
    "none":               "#2ED573",
    "mild":               "#B8E04A",
    "moderate":           "#FFA502",
    "severe":             "#FF6B35",
    "proliferative":      "#FF4757",
    "advanced":           "#C0392B",
    "vision_threatening": "#641E16",
}
RISK_COLORS = {
    "low":      "#2ED573",
    "moderate": "#FFA502",
    "high":     "#FF6B35",
    "critical": "#FF4757",
}


# ── Cached component init ─────────────────────────────────────────────────────
@st.cache_resource
def load_components():
    return {
        "classifier":       RetinalClassifier(demo_mode=True),
        "severity_grader":  SeverityGrader(),
        "risk_scorer":      RiskScorer(),
        "preprocessor":     RetinalPreprocessor(),
        "report_generator": ClinicalReportGenerator(),
    }


# ── Plotly helpers ────────────────────────────────────────────────────────────
_BASE_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="DM Sans, -apple-system, sans-serif", color="#7A8BA8"),
    margin=dict(l=0, r=0, t=30, b=0),
)


def make_donut_chart(probs: dict[str, float]) -> go.Figure:
    labels = [k.replace("_", " ").title() for k in probs]
    values = list(probs.values())
    colors = [DISEASE_COLORS.get(k, "#4A90D9") for k in probs]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.62,
        marker=dict(colors=colors, line=dict(color="#0F1E35", width=2)),
        textinfo="label+percent",
        textfont=dict(size=10, color="#CBD5E1"),
        hovertemplate="<b>%{label}</b><br>%{percent}<extra></extra>",
        sort=True,
    ))
    fig.update_layout(
        **_BASE_LAYOUT, showlegend=False, height=260,
        annotations=[dict(
            text="Classes", x=0.5, y=0.5,
            font_size=11, font_color="#4A6B8A", showarrow=False,
        )],
    )
    return fig


def make_gauge_chart(score: float, risk_level: str) -> go.Figure:
    color = RISK_COLORS.get(risk_level, "#4A90D9")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(score * 100, 1),
        number=dict(suffix="%", font=dict(size=24, color="#F0F4F8")),
        gauge=dict(
            axis=dict(range=[0, 100], tickwidth=1, tickcolor="#253D63",
                      tickfont=dict(color="#4A6B8A", size=9), nticks=5),
            bar=dict(color=color, thickness=0.65),
            bgcolor="#0F1E35",
            borderwidth=0,
            steps=[
                dict(range=[0, 25],   color="#0F2915"),
                dict(range=[25, 55],  color="#1F1A0A"),
                dict(range=[55, 80],  color="#211308"),
                dict(range=[80, 100], color="#1F0808"),
            ],
            threshold=dict(line=dict(color=color, width=2), thickness=0.8, value=score * 100),
        ),
    ))
    fig.update_layout(**_BASE_LAYOUT, height=200, margin=dict(l=20, r=20, t=10, b=0))
    return fig


def make_disease_pie(data: list[dict]) -> go.Figure:
    from collections import Counter
    counts = Counter(d["Disease"] for d in data)
    labels = list(counts.keys())
    vals   = list(counts.values())
    colors = [DISEASE_COLORS.get(k.lower().replace(" ", "_"), "#4A90D9") for k in labels]
    fig = go.Figure(go.Pie(
        labels=labels, values=vals, hole=0.5,
        marker=dict(colors=colors, line=dict(color="#0F1E35", width=2)),
        textinfo="label+percent",
        textfont=dict(size=10, color="#CBD5E1"),
        hovertemplate="<b>%{label}</b><br>%{value} cases (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        **_BASE_LAYOUT, showlegend=False, height=260,
        title=dict(text="Disease Distribution", font=dict(size=12, color="#7A8BA8"), x=0),
    )
    return fig


def make_severity_bar(data: list[dict]) -> go.Figure:
    from collections import Counter
    order  = ["none","mild","moderate","severe","proliferative","advanced"]
    counts = Counter(d["Severity"] for d in data)
    labels = [s.title() for s in order if s in counts]
    vals   = [counts[s] for s in order if s in counts]
    colors = [SEVERITY_COLORS.get(s, "#4A90D9") for s in order if s in counts]
    fig = go.Figure(go.Bar(
        x=labels, y=vals,
        marker=dict(color=colors, line=dict(color="#0F1E35", width=1.5)),
        text=vals, textposition="outside",
        textfont=dict(color="#CBD5E1", size=11),
        hovertemplate="<b>%{x}</b>: %{y}<extra></extra>",
    ))
    fig.update_layout(
        **_BASE_LAYOUT, height=260,
        title=dict(text="Severity Distribution", font=dict(size=12, color="#7A8BA8"), x=0),
        xaxis=dict(showgrid=False, tickfont=dict(color="#7A8BA8", size=10), linecolor="#1E3054"),
        yaxis=dict(showgrid=True, gridcolor="#1E3054", tickfont=dict(color="#7A8BA8", size=10), zeroline=False),
    )
    return fig


# ── Small UI helpers ──────────────────────────────────────────────────────────
def section_header(icon: str, text: str) -> str:
    return (
        f'<div class="section-header">'
        f'<div class="section-header-icon">{icon}</div>'
        f'<div class="section-header-text">{text}</div>'
        f'</div>'
    )


def disease_badge(label: str, color: str) -> str:
    icon = DISEASE_ICONS.get(label, "•")
    display = label.replace("_", " ").title()
    return (
        f'<span class="disease-badge" '
        f'style="background:{color}22;border:1px solid {color}55;color:{color};">'
        f'{icon} {display}</span>'
    )


def timeline_item(text: str, kind: str = "", dot_color: str = "#4A90D9") -> str:
    return (
        f'<div class="timeline-item {kind}">'
        f'<div class="timeline-dot" style="background:{dot_color};"></div>'
        f'<span>{text}</span></div>'
    )


def _sev_class(sv: str) -> str:
    return {"none":"green","mild":"teal","moderate":"amber",
            "severe":"red","proliferative":"red","advanced":"red"}.get(sv, "blue")


def _risk_class(rl: str) -> str:
    return {"low":"green","moderate":"amber","high":"red","critical":"red"}.get(rl, "blue")


# ── Analysis pipeline ─────────────────────────────────────────────────────────
def run_analysis(
    image: Image.Image,
    components: dict,
    metadata: ClinicalMetadata | None = None,
    study_id: str = "DEMO-001",
) -> dict:
    preprocessor: RetinalPreprocessor     = components["preprocessor"]
    classifier:   RetinalClassifier       = components["classifier"]
    grader:       SeverityGrader          = components["severity_grader"]
    scorer:       RiskScorer              = components["risk_scorer"]
    reporter:     ClinicalReportGenerator = components["report_generator"]

    prep           = preprocessor.process(image)
    arr            = np.array(prep.processed_image)
    features       = RetinalPreprocessor.extract_image_features(arr)
    classification = classifier.classify(prep.processed_image)
    severity       = grader.grade(classification, features)
    risk           = scorer.compute(classification, severity, metadata)
    report         = reporter.generate(
        study_id=study_id,
        classification=classification,
        severity=severity,
        risk=risk,
        image_quality=prep.to_dict(),
    )
    return {"prep": prep, "classification": classification,
            "severity": severity, "risk": risk, "report": report}


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    components = load_components()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-logo">
          <span class="sidebar-logo-icon">👁</span>
          <div class="sidebar-logo-title">Retina-Scan-AI</div>
          <div class="sidebar-logo-version">v1.0 · Clinical Screening</div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("Clinical Metadata", expanded=True):
            st.caption("Optional — improves risk stratification")
            study_id         = st.text_input("Study ID", value="STUDY-001", max_chars=32)
            patient_age      = st.number_input("Patient Age", min_value=0, max_value=120, value=0, step=1)
            diabetes_duration= st.number_input("Diabetes Duration (yrs)", min_value=0, max_value=80, value=0, step=1)
            hba1c            = st.number_input("HbA1c (%)", min_value=0.0, max_value=20.0, value=0.0, step=0.1)
            has_hypertension = st.checkbox("Hypertension")
            is_smoker        = st.checkbox("Current Smoker")
            family_history   = st.checkbox("Family History of Eye Disease")

        st.markdown("""
        <div class="sidebar-disclaimer">
          <strong>⚠ Clinical Disclaimer</strong><br>
          AI screening tool only. Not for diagnostic use.
          All findings require review by a qualified ophthalmologist.
        </div>
        """, unsafe_allow_html=True)

    # ── Hero ──────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="hero-section">
      <div style="display:flex;align-items:flex-start;gap:2.5rem;flex-wrap:wrap;">
        <div style="flex:1;min-width:260px;">
          <h1 class="hero-title">Retinal Disease<br>Intelligence</h1>
          <p class="hero-subtitle">
            Automated fundus analysis &mdash;
            <span>Diabetic Retinopathy</span> &middot;
            <span>Glaucoma</span> &middot;
            <span>AMD</span> &middot;
            <span>Cataracts</span>
          </p>
          <div class="stats-row">
            <span class="stat-chip">🔬 5 Disease Classes</span>
            <span class="stat-chip">📊 ETDRS Grading</span>
            <span class="stat-chip accent">🏥 ICD-10 Coded</span>
            <span class="stat-chip accent">⚡ FHIR R4</span>
            <span class="stat-chip warn">🔒 HIPAA Aware</span>
          </div>
        </div>
        <div style="flex-shrink:0;opacity:0.88;border-radius:10px;overflow:hidden;border:1px solid #253D63;">
          <img src="https://media.giphy.com/media/l0HlNQ03J5JxX2rza/giphy.gif"
               style="width:155px;height:116px;object-fit:cover;display:block;"
               onerror="this.style.display='none'" alt="Retinal scan" />
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔬  Single Analysis",
        "📊  Batch Processing",
        "💬  AI Assistant",
        "⚙  System Info",
    ])

    # =========================================================================
    # TAB 1 — Single analysis
    # =========================================================================
    with tab1:
        up_col, prev_col = st.columns([1, 1], gap="large")

        with up_col:
            st.markdown(section_header("📤", "Upload Fundus Image"), unsafe_allow_html=True)
            st.markdown(
                '<div style="text-align:center;font-size:1.8rem;opacity:0.5;margin-bottom:0.3rem;">🏥</div>'
                '<div style="text-align:center;font-size:0.78rem;color:#4A6B8A;margin-bottom:0.6rem;">'
                'JPEG · PNG · TIFF · BMP &nbsp;|&nbsp; Ideally ≥ 800×800 px</div>',
                unsafe_allow_html=True,
            )
            uploaded = st.file_uploader(
                "Drag & drop or browse",
                type=["jpg", "jpeg", "png", "tiff", "bmp"],
                help="Fundus photograph, ideally ≥ 800×800 px",
            )

        if uploaded:
            image = Image.open(io.BytesIO(uploaded.read())).convert("RGB")

            with prev_col:
                st.markdown(section_header("🖼", "Original Image"), unsafe_allow_html=True)
                st.image(image, caption=f"{image.size[0]} × {image.size[1]} px",
                         use_container_width=True)

            metadata = ClinicalMetadata(
                age=patient_age if patient_age > 0 else None,
                diabetes_duration_years=diabetes_duration if diabetes_duration > 0 else None,
                hba1c_percent=hba1c if hba1c > 0 else None,
                has_hypertension=has_hypertension,
                is_smoker=is_smoker,
                family_history_eye_disease=family_history,
            )

            st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

            if st.button("▶  Run Full Analysis", type="primary"):
                with st.spinner("Analyzing retinal image…"):
                    results = run_analysis(image, components, metadata, study_id)

                r_class  = results["classification"]
                r_sev    = results["severity"]
                r_risk   = results["risk"]
                r_report = results["report"]
                r_prep   = results["prep"]

                # Urgent alert
                if r_class.requires_urgent_review:
                    st.markdown("""
                    <div class="glass-card urgent urgent-pulse anim-fade"
                         style="display:flex;align-items:center;gap:0.8rem;margin:1rem 0;">
                      <span style="font-size:1.4rem;flex-shrink:0;">🚨</span>
                      <div>
                        <div style="color:#FF4757;font-weight:700;font-size:0.88rem;letter-spacing:0.05em;">
                          URGENT CLINICAL REVIEW REQUIRED
                        </div>
                        <div style="color:#A8796A;font-size:0.78rem;margin-top:0.15rem;">
                          This finding warrants immediate ophthalmologist review. Do not delay referral.
                        </div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                st.divider()

                # ── Three metric cards ────────────────────────────────────────
                st.markdown(section_header("📋", "Analysis Results"), unsafe_allow_html=True)
                mc1, mc2, mc3 = st.columns(3, gap="medium")

                diag_color = DISEASE_COLORS.get(r_class.predicted_label.value, "#4A90D9")
                sev_color  = SEVERITY_COLORS.get(r_sev.severity.value, "#4A90D9")
                risk_color = RISK_COLORS.get(r_risk.risk_level.value, "#4A90D9")
                diag_icon  = DISEASE_ICONS.get(r_class.predicted_label.value, "•")
                etdrs_note = f" · ETDRS {r_sev.etdrs_level}" if r_sev.etdrs_level else ""

                with mc1:
                    st.markdown(f"""
                    <div class="metric-card blue anim-1">
                      <div class="metric-card-icon">{diag_icon}</div>
                      <div class="metric-card-label">Diagnosis</div>
                      <div class="metric-card-value">{r_class.display_name}</div>
                      <div class="metric-card-sub">ICD-10: {r_class.icd10_code}</div>
                      <div style="margin-top:0.65rem;">
                        {disease_badge(r_class.predicted_label.value, diag_color)}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                with mc2:
                    sev_cls = _sev_class(r_sev.severity.value)
                    st.markdown(f"""
                    <div class="metric-card {sev_cls} anim-2">
                      <div class="metric-card-icon">📊</div>
                      <div class="metric-card-label">Severity Grade</div>
                      <div class="metric-card-value">{r_sev.severity.value.title()}</div>
                      <div class="metric-card-sub">Score: {r_sev.severity_score:.2f}{etdrs_note}</div>
                      <div style="margin-top:0.65rem;background:#0F1E35;border-radius:4px;height:6px;overflow:hidden;">
                        <div style="width:{int(r_sev.severity_score*100)}%;height:100%;
                             background:{sev_color};border-radius:4px;"></div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                with mc3:
                    risk_cls = _risk_class(r_risk.risk_level.value)
                    st.markdown(f"""
                    <div class="metric-card {risk_cls} anim-3">
                      <div class="metric-card-icon">⚡</div>
                      <div class="metric-card-label">Risk Level</div>
                      <div class="metric-card-value">{r_risk.risk_level.value.title()}</div>
                      <div class="metric-card-sub">
                        Rescreen in {r_risk.screening_interval_months} mo · Score {r_risk.raw_score:.2f}
                      </div>
                      <div style="margin-top:0.65rem;">
                        <span class="disease-badge"
                              style="background:{risk_color}22;border:1px solid {risk_color}55;color:{risk_color};">
                          {r_risk.risk_level.value.upper()}
                        </span>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

                # ── Charts ────────────────────────────────────────────────────
                st.markdown(section_header("📈", "Diagnostic Metrics"), unsafe_allow_html=True)
                ch1, ch2 = st.columns(2, gap="large")

                with ch1:
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    st.caption("CLASSIFICATION PROBABILITIES")
                    st.plotly_chart(
                        make_donut_chart(r_class.probabilities),
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
                    st.caption(f"Model confidence: **{r_class.confidence:.1%}**")
                    st.markdown('</div>', unsafe_allow_html=True)

                with ch2:
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    st.caption("COMPOSITE RISK SCORE")
                    st.plotly_chart(
                        make_gauge_chart(r_risk.raw_score, r_risk.risk_level.value),
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
                    st.caption(f"Follow-up urgency: **{r_sev.follow_up_urgency}**")
                    st.markdown('</div>', unsafe_allow_html=True)

                st.divider()

                # ── Preprocessed image + quality ──────────────────────────────
                st.markdown(section_header("🔍", "Image Processing"), unsafe_allow_html=True)
                img_col, qual_col = st.columns([1, 1], gap="large")

                with img_col:
                    st.image(r_prep.processed_image,
                             caption="After CLAHE + vessel enhancement",
                             use_container_width=True)

                with qual_col:
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    st.markdown('<div class="metric-card-label" style="margin-bottom:0.6rem;">IMAGE QUALITY</div>', unsafe_allow_html=True)
                    q = r_prep.quality_score
                    q_color = "#2ED573" if q >= 0.7 else "#FFA502" if q >= 0.4 else "#FF4757"
                    st.markdown(f"""
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.4rem;">
                      <span style="font-size:0.78rem;color:#7A8BA8;font-weight:600;letter-spacing:0.04em;">QUALITY SCORE</span>
                      <span style="font-size:1.1rem;font-weight:700;color:{q_color};">{q:.0%}</span>
                    </div>
                    <div style="background:#0F1E35;border-radius:6px;height:10px;overflow:hidden;margin-bottom:0.8rem;">
                      <div style="width:{int(q*100)}%;height:100%;
                           background:linear-gradient(90deg,{q_color}88,{q_color});border-radius:6px;"></div>
                    </div>
                    """, unsafe_allow_html=True)
                    if r_prep.quality_flags:
                        for flag in r_prep.quality_flags:
                            st.markdown(timeline_item(flag, "warn", "#FFA502"), unsafe_allow_html=True)
                    else:
                        st.markdown(timeline_item("No quality issues detected", "success", "#2ED573"), unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                st.divider()

                # ── Clinical findings ─────────────────────────────────────────
                st.markdown(section_header("🩺", "Clinical Findings"), unsafe_allow_html=True)
                findings_class = "urgent" if r_class.requires_urgent_review else ""
                st.markdown(f"""
                <div class="glass-card {findings_class}">
                  <div style="font-size:0.83rem;color:#A8B8CC;line-height:1.7;">
                    {r_sev.clinical_description}
                  </div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

                # ── Follow-up timeline ────────────────────────────────────────
                st.markdown(section_header("📅", "Follow-up & Recommendations"), unsafe_allow_html=True)

                urgency_kind_map = {
                    "routine":               "success",
                    "routine (12 months)":   "success",
                    "soon (3 months)":       "warn",
                    "urgent (4 weeks)":      "urgent",
                    "emergency (1 week)":    "urgent",
                    "emergency (same day)":  "urgent",
                }
                u_kind  = urgency_kind_map.get(r_sev.follow_up_urgency, "")
                u_color = {"urgent":"#FF4757","warn":"#FFA502","success":"#2ED573"}.get(u_kind, "#4A90D9")
                st.markdown(timeline_item(f"<strong>Follow-up:</strong> {r_sev.follow_up_urgency}", u_kind, u_color), unsafe_allow_html=True)

                for rec in r_risk.recommendations:
                    st.markdown(timeline_item(rec), unsafe_allow_html=True)

                if r_risk.contributing_factors:
                    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
                    st.markdown(section_header("⚠", "Contributing Risk Factors"), unsafe_allow_html=True)
                    for factor in r_risk.contributing_factors:
                        st.markdown(timeline_item(factor, "warn", "#FFA502"), unsafe_allow_html=True)

                st.divider()

                # ── Clinical report ───────────────────────────────────────────
                st.markdown(section_header("📄", "Clinical Report"), unsafe_allow_html=True)
                with st.expander("View Full Clinical Report", expanded=False):
                    st.code(r_report.to_text(), language=None)

                report_text = r_report.to_text()
                dl_col, _ = st.columns([1, 3])
                with dl_col:
                    st.download_button(
                        "⬇  Download Report (.txt)",
                        data=report_text,
                        file_name=f"retina_report_{r_report.report_id[:8]}.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )

    # =========================================================================
    # TAB 2 — Batch processing
    # =========================================================================
    with tab2:
        st.markdown(section_header("📊", "Batch Fundus Image Processing"), unsafe_allow_html=True)
        st.markdown("""
        <div class="glass-card" style="margin-bottom:1.5rem;">
          <div style="font-size:0.83rem;color:#7A8BA8;line-height:1.6;">
            Upload multiple fundus images for simultaneous screening.
            Results include disease and severity breakdowns, urgent flags, and CSV export.
          </div>
        </div>
        """, unsafe_allow_html=True)

        batch_files = st.file_uploader(
            "Upload multiple fundus images",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
        )

        if batch_files:
            if st.button("▶  Run Batch Analysis", type="primary"):
                results_list: list[dict] = []
                bar = st.progress(0, text="Initializing…")

                for i, f in enumerate(batch_files):
                    bar.progress((i + 1) / len(batch_files),
                                 text=f"Processing {f.name} ({i+1}/{len(batch_files)})…")
                    img = Image.open(io.BytesIO(f.read())).convert("RGB")
                    res = run_analysis(img, components, study_id=f"BATCH-{i+1:03d}")
                    results_list.append({
                        "File":       f.name,
                        "Disease":    res["classification"].display_name,
                        "Severity":   res["severity"].severity.value,
                        "Risk":       res["risk"].risk_level.value,
                        "Confidence": f"{res['classification'].confidence:.1%}",
                        "Urgent":     res["classification"].requires_urgent_review,
                        "_res":       res,
                    })
                bar.empty()

                # Summary cards
                total  = len(results_list)
                normal = sum(1 for r in results_list if r["Disease"] == "Normal")
                urgent = sum(1 for r in results_list if r["Urgent"])
                rescan = sum(1 for r in results_list if r["_res"]["prep"].quality_score < 0.4)

                sc1, sc2, sc3, sc4 = st.columns(4, gap="medium")
                for col, num, label, accent in [
                    (sc1, total,  "Total Scans",   "blue"),
                    (sc2, normal, "Normal",         "green"),
                    (sc3, urgent, "Urgent Review",  "red"),
                    (sc4, rescan, "Re-scan Needed", "amber"),
                ]:
                    with col:
                        st.markdown(f"""
                        <div class="batch-summary-card metric-card {accent}">
                          <div class="batch-num">{num}</div>
                          <div class="batch-label">{label}</div>
                        </div>
                        """, unsafe_allow_html=True)

                st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

                # Charts
                chart_data = [{"Disease": r["Disease"], "Severity": r["Severity"]} for r in results_list]
                pc1, pc2 = st.columns(2, gap="large")
                with pc1:
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    st.plotly_chart(make_disease_pie(chart_data), use_container_width=True,
                                    config={"displayModeBar": False})
                    st.markdown('</div>', unsafe_allow_html=True)
                with pc2:
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    st.plotly_chart(make_severity_bar(chart_data), use_container_width=True,
                                    config={"displayModeBar": False})
                    st.markdown('</div>', unsafe_allow_html=True)

                st.divider()
                st.markdown(section_header("📋", "Detailed Results"), unsafe_allow_html=True)

                for row in results_list:
                    res        = row["_res"]
                    risk_col   = RISK_COLORS.get(row["Risk"], "#4A90D9")
                    sev_col    = SEVERITY_COLORS.get(row["Severity"], "#4A90D9")
                    diag_col   = DISEASE_COLORS.get(res["classification"].predicted_label.value, "#4A90D9")
                    label_pfx  = "🚨 " if row["Urgent"] else "📄 "

                    with st.expander(f"{label_pfx}{row['File']} — {row['Disease']}"):
                        ec1, ec2, ec3, ec4 = st.columns(4)
                        for ec, heading, value, color in [
                            (ec1, "Disease",    row["Disease"],           diag_col),
                            (ec2, "Severity",   row["Severity"].title(),  sev_col),
                            (ec3, "Risk Level", row["Risk"].title(),      risk_col),
                            (ec4, "Confidence", row["Confidence"],        "#CBD5E1"),
                        ]:
                            with ec:
                                st.markdown(f"""
                                <div style="font-size:0.7rem;color:#7A8BA8;font-weight:600;
                                     letter-spacing:0.06em;text-transform:uppercase;margin-bottom:0.3rem;">
                                  {heading}
                                </div>
                                <div style="font-size:0.92rem;font-weight:700;color:{color};">{value}</div>
                                """, unsafe_allow_html=True)
                        if row["Urgent"]:
                            st.markdown("""
                            <div class="timeline-item urgent" style="margin-top:0.75rem;">
                              <div class="timeline-dot" style="background:#FF4757;"></div>
                              <span>Urgent ophthalmology review required</span>
                            </div>
                            """, unsafe_allow_html=True)

                # CSV export
                st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
                csv_buf = _io.StringIO()
                writer  = csv.DictWriter(csv_buf, fieldnames=["File","Disease","Severity","Risk","Confidence","Urgent"])
                writer.writeheader()
                for row in results_list:
                    writer.writerow({k: v for k, v in row.items() if k != "_res"})

                export_col, _ = st.columns([1, 3])
                with export_col:
                    st.download_button(
                        "⬇  Export Results (.csv)",
                        data=csv_buf.getvalue(),
                        file_name="batch_results.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

    # =========================================================================
    # TAB 3 — AI Assistant
    # =========================================================================
    with tab3:
        st.markdown(section_header("💬", "Clinical AI Assistant"), unsafe_allow_html=True)

        st.markdown("""
        <div class="glass-card warn-card" style="margin-bottom:1.5rem;display:flex;align-items:center;gap:0.75rem;">
          <span style="font-size:1.2rem;flex-shrink:0;">⚠️</span>
          <div style="font-size:0.79rem;color:#A8956A;line-height:1.5;">
            <strong style="color:#FFA502;">Research Use Only.</strong>
            This assistant provides general ophthalmology information only. It is not a substitute
            for professional medical advice, diagnosis, or treatment.
          </div>
        </div>
        """, unsafe_allow_html=True)

        info_col, chat_col = st.columns([1, 2], gap="large")

        with info_col:
            st.markdown("""
            <div class="glass-card">
              <div class="metric-card-label" style="margin-bottom:0.8rem;">SESSION INFO</div>
              <div style="display:flex;flex-direction:column;gap:0.5rem;">
                <div style="display:flex;justify-content:space-between;font-size:0.8rem;">
                  <span style="color:#7A8BA8;">Model</span>
                  <span style="color:#CBD5E1;font-weight:600;">Retina-GPT v1</span>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:0.8rem;">
                  <span style="color:#7A8BA8;">Domain</span>
                  <span style="color:#CBD5E1;font-weight:600;">Ophthalmology</span>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:0.8rem;">
                  <span style="color:#7A8BA8;">Status</span>
                  <span style="color:#2ED573;font-weight:600;">● Demo Mode</span>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
            st.markdown('<div class="metric-card-label" style="margin-bottom:0.5rem;">SUGGESTED QUESTIONS</div>', unsafe_allow_html=True)

            suggested = [
                "What is diabetic retinopathy?",
                "Explain ETDRS grading",
                "When is anti-VEGF indicated?",
                "AMD screening guidelines",
                "Glaucoma risk factors",
                "IOP targets in glaucoma",
            ]
            for q in suggested:
                if st.button(q, key=f"chip_{q}", use_container_width=True):
                    if "chat_history" not in st.session_state:
                        st.session_state.chat_history = []
                    st.session_state.chat_history.append({"role": "user", "content": q})
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": (
                            f"This is a demo response to your question about **{q}**.\n\n"
                            "In production, this connects to a clinical AI model trained on "
                            "ophthalmology literature. For immediate guidance, please consult "
                            "current AAO, NICE, or RCOphth guidelines."
                        ),
                    })
                    st.rerun()

        with chat_col:
            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []

            # Chat bubbles
            chat_html = '<div class="chat-container">'
            if not st.session_state.chat_history:
                chat_html += (
                    '<div style="text-align:center;color:#4A6B8A;font-size:0.83rem;padding:2.5rem 1rem;">'
                    'Ask a question about retinal diseases, screening protocols,<br>or treatment guidelines.'
                    '</div>'
                )
            else:
                for msg in st.session_state.chat_history:
                    role   = msg["role"]
                    cls    = "user" if role == "user" else "assistant"
                    label  = "You" if role == "user" else "AI Assistant"
                    chat_html += (
                        f'<div style="display:flex;flex-direction:column;'
                        f'align-items:{"flex-end" if role=="user" else "flex-start"};">'
                        f'<div class="chat-bubble {cls}">{msg["content"]}</div>'
                        f'<div class="chat-meta {role}">{label}</div>'
                        f'</div>'
                    )
            chat_html += '</div>'
            st.markdown(chat_html, unsafe_allow_html=True)

            # Input
            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
            with st.form("chat_form", clear_on_submit=True):
                inp_c, btn_c = st.columns([5, 1])
                with inp_c:
                    user_input = st.text_input(
                        "Message", label_visibility="collapsed",
                        placeholder="Ask about retinal disease, screening, or treatment…",
                    )
                with btn_c:
                    sent = st.form_submit_button("Send", use_container_width=True)

                if sent and user_input.strip():
                    st.session_state.chat_history.append({"role": "user", "content": user_input})
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": (
                            f"Thank you for your question about "
                            f"**{user_input[:60]}{'…' if len(user_input) > 60 else ''}**.\n\n"
                            "This is a demo interface. In production, this connects to a clinical AI "
                            "model trained on ophthalmology literature. Please consult current "
                            "AAO, NICE, or RCOphth guidelines for authoritative guidance."
                        ),
                    })
                    st.rerun()

            if st.session_state.chat_history:
                if st.button("Clear Conversation", key="clear_chat"):
                    st.session_state.chat_history = []
                    st.rerun()

    # =========================================================================
    # TAB 4 — System Info
    # =========================================================================
    with tab4:
        st.markdown(section_header("⚙", "System Information"), unsafe_allow_html=True)

        # Compliance row
        st.markdown("""
        <div style="display:flex;gap:0.65rem;flex-wrap:wrap;margin-bottom:1.5rem;">
          <span class="compliance-badge">🔒 HIPAA Aware</span>
          <span class="compliance-badge">⚡ FHIR R4</span>
          <span class="compliance-badge">📋 ICD-10-CM</span>
          <span class="compliance-badge">🔬 ETDRS Grading</span>
          <span class="compliance-badge" style="background:rgba(74,144,217,0.1);border-color:rgba(74,144,217,0.25);color:#4A90D9;">
            🤖 ResNet18
          </span>
        </div>
        """, unsafe_allow_html=True)

        # Disease cards — 2 rows of 3
        st.markdown(section_header("🏥", "Supported Disease Classes"), unsafe_allow_html=True)

        diseases = [
            {"icon": "✅", "name": "Normal", "icd": "Z01.01", "color": "#2ED573",
             "desc": "No retinal pathology. Healthy optic disc and macula. Routine annual screening."},
            {"icon": "🩸", "name": "Diabetic Retinopathy", "icd": "E11.319", "color": "#FF4757",
             "desc": "Microvascular complications of diabetes. ETDRS grading: mild NPDR → PDR."},
            {"icon": "👁", "name": "Glaucoma", "icd": "H40.10X0", "color": "#FFA502",
             "desc": "Optic neuropathy with characteristic disc cupping. CDR analysis and RNFL assessment."},
            {"icon": "🟡", "name": "Age-related Macular Degeneration", "icd": "H35.30", "color": "#A78BFA",
             "desc": "Drusen deposits and RPE changes in macula. Anti-VEGF for wet AMD."},
            {"icon": "💧", "name": "Cataracts", "icd": "H26.9", "color": "#4A90D9",
             "desc": "Lens opacity causing visual impairment. Incipient to dense grades."},
            {"icon": "🔬", "name": "Model Architecture", "icd": "ResNet18", "color": "#00C9A7",
             "desc": "Transfer learning on fundus datasets. Demo heuristic + PyTorch production mode. Grad-CAM attention maps."},
        ]

        row1_cols = st.columns(3, gap="medium")
        row2_cols = st.columns(3, gap="medium")

        for idx, d in enumerate(diseases):
            cols_row = row1_cols if idx < 3 else row2_cols
            with cols_row[idx % 3]:
                st.markdown(f"""
                <div class="disease-info-card" style="border-top:3px solid {d['color']}55;">
                  <div class="disease-info-icon">{d['icon']}</div>
                  <div class="disease-info-name">{d['name']}</div>
                  <div class="disease-info-icd" style="color:{d['color']};">{d['icd']}</div>
                  <div class="disease-info-desc">{d['desc']}</div>
                </div>
                """, unsafe_allow_html=True)

        st.divider()

        # Architecture + model JSON
        arch_col, model_col = st.columns([1, 1], gap="large")

        with arch_col:
            st.markdown(section_header("🏗", "Pipeline Architecture"), unsafe_allow_html=True)
            pipeline_steps = [
                ("🖼", "Preprocessing",    "CLAHE · vessel enhancement · FOV masking"),
                ("🤖", "Classification",   "ResNet18 + temperature-scaled softmax"),
                ("📊", "Severity Grading", "ETDRS-like DR · CDR-based glaucoma · AMD drusen"),
                ("⚡", "Risk Scoring",     "Composite score: disease + severity + metadata"),
                ("📄", "Reporting",        "Structured clinical report · FHIR R4 export"),
                ("🔍", "Explainability",   "Disease-specific Grad-CAM attention maps"),
            ]
            for icon, title, desc in pipeline_steps:
                st.markdown(f"""
                <div class="timeline-item" style="margin-bottom:0.45rem;">
                  <span style="flex-shrink:0;font-size:1rem;">{icon}</span>
                  <div>
                    <div style="font-weight:600;color:#CBD5E1;font-size:0.82rem;">{title}</div>
                    <div style="font-size:0.76rem;color:#7A8BA8;margin-top:0.08rem;">{desc}</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

        with model_col:
            st.markdown(section_header("📦", "Model Information"), unsafe_allow_html=True)
            classifier: RetinalClassifier = components["classifier"]
            arch = classifier.get_model_architecture_summary()
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.json(arch)
            st.markdown('</div>', unsafe_allow_html=True)

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="footer-bar">
      Powered by <strong style="color:#7A8BA8;">Retina-Scan-AI v1.0</strong>
      <span class="footer-sep">·</span>
      Clinical Research Tool
      <span class="footer-sep">·</span>
      Not for Diagnostic Use
      <span class="footer-sep">·</span>
      HIPAA Aware
      <span class="footer-sep">·</span>
      <span style="color:#253D63;">© 2024 Retina-Scan-AI Research</span>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
