from PIL import Image

import streamlit as st
import pandas as pd
import os
import numpy as np
import json
import plotly.graph_objects as go
from pathlib import Path
import base64


# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Vittā Money OS",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Core imports ────────────────────────────────────────────────────────────────
from modules.parser           import parse_csv, get_summary_stats
from modules.categorizer      import categorize_transactions, get_category_summary, get_top_merchants
from modules.anomaly_detector import detect_anomalies, get_anomaly_summary
from modules.insights         import generate_full_insights, generate_nudges
from modules import charts

# ── New feature imports ─────────────────────────────────────────────────────────
from modules.budget_tracker import (
     compute_budget_status, compute_monthly_overview,get_budget_alerts,
       DEFAULT_BUDGETS, ALL_CATEGORIES )
from modules.forecaster       import forecast_all_categories, get_total_forecast
from modules.deduplicator     import (
    merge_accounts, deduplicate, apply_manual_review,
    get_dedup_report, get_clean_df, get_duplicate_pairs
)
from modules.ai_advisor import (build_financial_context, get_api_client,
                                  chat_stream, chat_once, generate_monthly_summary,
                                  STARTER_QUESTIONS, ANTHROPIC_AVAILABLE, GROQ_AVAILABLE)
from modules.benchmarks       import (compute_benchmarks, get_savings_benchmark,
                                      get_standout_categories)
from modules.merchant_review_ui import render_merchant_review
from modules.csv_format_guide import render_csv_guide


def _img_to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

logo_b64 = _img_to_b64("MoneyOS_Logo.png")
# ── Custom CSS ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap');

:root {
    --bg-primary:   #0f0f1a;
    --bg-card:      #1a1a2e;
    --bg-card2:     #16213e;
    --accent-purple:#6C63FF;
    --accent-teal:  #4ECDC4;
    --accent-red:   #FF6B6B;
    --accent-yellow:#FFD93D;
    --text-primary: #E0E0F0;
    --text-muted:   #8A8AB0;
}

.stApp { 
    background: var(--bg-primary); 
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f0f1a, #141428);
    border-right: 1px solid rgba(108,99,255,0.2);
}

/* Sidebar radio enhancement */
div[data-testid="stSidebar"] label[data-baseweb="radio"] > div {
    padding: 8px 10px;
    border-radius: 8px;
    transition: 0.2s;
}
div[data-testid="stSidebar"] label[data-baseweb="radio"]:hover > div {
    background: rgba(108,99,255,0.15);
}
div[data-testid="stSidebar"] input:checked + div {
    background: rgba(108,99,255,0.25);
    border-left: 3px solid #6C63FF;
}

/* Cards */
.kpi-card {
    background: linear-gradient(145deg, #1a1a2e, #141425);
    border: 1px solid rgba(108,99,255,0.2);
    border-radius: 12px;
    padding: 20px 24px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    transition: 0.2s ease;
}
.kpi-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 30px rgba(108,99,255,0.25);
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--accent-purple), var(--accent-teal));
}

.kpi-value {
    font-family: 'Space Mono', monospace;
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--text-primary);
}

.kpi-label {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.78rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 4px;
}

.kpi-delta {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.82rem;
    margin-top: 6px;
}

/* Section headers */
.section-header {
    font-family: 'DM Sans', sans-serif;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary);
    padding: 8px 0 12px;
    border-bottom: 1px solid rgba(108,99,255,0.15);
    margin-bottom: 16px;
    position: relative;
}
.section-header::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 0;
    width: 40px;
    height: 2px;
    background: #6C63FF;
}

/* Plotly charts container */
div[data-testid="stPlotlyChart"] {
    background: #1a1a2e;
    padding: 10px;
    border-radius: 12px;
    border: 1px solid rgba(108,99,255,0.15);
}

/* Nudge cards */
.nudge-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid rgba(108,99,255,0.25);
    border-left: 3px solid var(--accent-purple);
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 10px;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.88rem;
    color: var(--text-primary);
    line-height: 1.6;
}

/* Badges */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    font-family: 'DM Sans', sans-serif;
}
.badge-high   { background: rgba(255,107,107,0.2); color: #FF6B6B; border: 1px solid #FF6B6B; }
.badge-medium { background: rgba(255,159,67,0.2); color: #FF9F43;  border: 1px solid #FF9F43; }
.badge-low    { background: rgba(255,217,61,0.2); color: #FFD93D;  border: 1px solid #FFD93D; }
.badge-clean  { background: rgba(78,205,196,0.2); color: #4ECDC4;  border: 1px solid #4ECDC4; }

/* Rows */
.sub-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 14px;
    background: var(--bg-card);
    border-radius: 8px;
    margin-bottom: 6px;
    border: 1px solid rgba(255,255,255,0.05);
}

/* Hero */
.hero {
    background: linear-gradient(135deg, #1a1a2e 0%, #0f0f1a 60%, #1a0f2e 100%);
    border: 1px solid rgba(108,99,255,0.2);
    border-radius: 16px;
    padding: 32px 40px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 10px 40px rgba(0,0,0,0.35);
}
.hero::after {
    content: '₹';
    position: absolute;
    right: 40px; top: -10px;
    font-size: 120px;
    font-family: 'Space Mono', monospace;
    color: rgba(108,99,255,0.06);
    font-weight: 700;
}

.hero h1 {
    font-family: 'DM Sans', sans-serif;
    font-size: 1.9rem;
    font-weight: 700;
    color: #E0E0F0;
    margin: 0 0 6px;
}

.hero p {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.95rem;
    color: #8A8AB0;
    margin: 0;
}
.full-width-guide [data-testid="stExpander"] {
    width: 100% !important;
    max-width: 100% !important;
}

/* Layout spacing */
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 1rem;
}

/* Tables */
div[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg-primary); }
::-webkit-scrollbar-thumb { background: rgba(108,99,255,0.4); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(108,99,255,0.7); }

body {
    letter-spacing: 0.2px;
}
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# DATA LOADING  (cached)
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_and_process(file_bytes: bytes = None, use_sample: bool = False,
                         extra_bytes_list: tuple = (), user_id: str = "user_1"):
    import io
    dfs, names = [], []

    if file_bytes:
        raw = parse_csv(io.BytesIO(file_bytes))
        dfs.append(raw); names.append("Primary Account")
    elif use_sample:
        sample_path = Path(__file__).parent / "data" / "sample_transactions.csv"
        raw = parse_csv(str(sample_path))
        dfs.append(raw); names.append("Sample Data")
    else:
        return None

    # Additional accounts
    for i, eb in enumerate(extra_bytes_list):
        try:
            extra_raw = parse_csv(io.BytesIO(eb))
            dfs.append(extra_raw)
            names.append(f"Account {i+2}")
        except Exception:
            pass

    # Merge + dedup
    if len(dfs) > 1:
        merged = merge_accounts(dfs, names)
    else:
        from modules.deduplicator import tag_source
        merged = tag_source(dfs[0], names[0])

    merged = deduplicate(merged)
    clean  = get_clean_df(merged)

    df = categorize_transactions(clean, user_id=user_id)
    df = detect_anomalies(df)
    return df, merged   # return both: clean processed + raw merged with dup flags


# ──────────────────────────────────────────────────────────────────────────────
# LANDING PAGE + DATA LOADING
# ──────────────────────────────────────────────────────────────────────────────

# initialize session state
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
if "user_id" not in st.session_state:    
    st.session_state.user_id = "user_1"

if "uploaded_file_bytes" not in st.session_state:
    st.session_state.uploaded_file_bytes = None

if "extra_bytes" not in st.session_state:
    st.session_state.extra_bytes = ()

if "use_sample_data" not in st.session_state:
    st.session_state.use_sample_data = False

if "data_source" not in st.session_state:
    st.session_state.data_source = "No data"
if "show_merchant_review" not in st.session_state:
    st.session_state.show_merchant_review = False
if "merchant_review_done" not in st.session_state:
    st.session_state.merchant_review_done = False
if "page_override" not in st.session_state:
    st.session_state.page_override = None
if "manual_duplicate_decisions" not in st.session_state:
    st.session_state.manual_duplicate_decisions = {}


# ──────────────────────────────────────────────────────────────────────────────
if not st.session_state.data_loaded:
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] { display: none; }
    .stApp { background: #f7f5f0 !important; }
    .main { background: #f7f5f0 !important; }
    .block-container {
        max-width: 100% !important;
        padding: 2rem 4rem !important;
        background: #f7f5f0 !important;
    }
    [data-testid="stFileUploader"] {
        background: white;
        border-radius: 16px;
        padding: 10px;
        border: 1px solid #ede8e0;
    }
    [data-testid="stFileUploaderDropzone"] {
        background: white !important;
        border: 2px dashed #ded9cf !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Hero via components.html — bypasses sanitizer ─────────────────────────
    import streamlit.components.v1 as components

    hero_html = f"""
    <div style='font-family:"DM Sans",sans-serif; background:#f7f5f0; padding:0;'>

        <div style='display:flex; align-items:center; gap:14px; margin-bottom:40px;'>
            <img src='data:image/png;base64,{logo_b64}' width='46'
                 style='border-radius:8px;'/>
            <div>
                <div style='font-size:1.1rem; font-weight:700; color:#151515;'>Vittā</div>
                <div style='font-size:0.72rem; color:#1769ff; letter-spacing:0.1em;
                            text-transform:uppercase;'>Money OS</div>
            </div>
        </div>

        <div style='display:flex; gap:60px; align-items:flex-start;'>

            <div style='flex:1.2; min-width:0;'>
                <div style='font-size:3rem; font-weight:800; color:#151515;
                            line-height:1.15; margin-bottom:14px;'>
                    Your money<br>has a story.
                </div>
                <div style='font-size:1.2rem; font-weight:600;
                            color:#1769ff; margin-bottom:16px;'>
                    Read where your money goes — and why.
                </div>
                <div style='font-size:0.98rem; color:#6c675f;
                            line-height:1.75; max-width:480px;'>
                    Vittā transforms messy bank/UPI statements into clear
                    financial insights. Track spending leaks, subscriptions,
                    lifestyle drift, savings patterns, and understand your
                    financial behaviour stress free.
                </div>
            </div>

            <div style='flex:1; display:flex; flex-wrap:wrap; gap:12px;
                        align-content:flex-start; padding-top:8px;'>
                {"".join([
                    f"<div style='background:white; border:1px solid #e5ddd0; "
                    f"padding:12px 18px; border-radius:999px; font-size:0.9rem; "
                    f"font-weight:600; color:#151515; "
                    f"box-shadow:0 1px 3px rgba(0,0,0,0.05);'>{chip}</div>"
                    for chip in [
                        "💸 Spending Leak Detection",
                        "📊 Budget Tracking",
                        "🧠 AI Money Coach",
                        "⚠️ Anomaly Detection",
                        "🔁 Subscription Tracker",
                        "📈 Monthly Trends",
                        "🏷️ Smart Categorization",
                        "🔍 Duplicate Detection",
                    ]
                ])}
            </div>

        </div>
    </div>
    """

    components.html(hero_html, height=340, scrolling=False)

    st.divider()
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Upload + Demo row (unchanged) ─────────────────────────────────────────
    col1, col2 = st.columns([1.4, 1], gap="large")

    with col1:
        st.markdown("""
        <div style='font-family:"DM Sans",sans-serif; font-weight:700;
                    font-size:1rem; color:#151515; margin-bottom:12px;'>
            Upload your statement
        </div>
        """, unsafe_allow_html=True)

        uploaded_file = st.file_uploader("Upload primary CSV", type=["csv"])
        extra_files   = st.file_uploader(
            "Add more accounts (optional)",
            type=["csv"],
            accept_multiple_files=True,
        )

    with col2:
        st.markdown("""
        <div style='background:#f0f4ff; border:1px solid #d0dbff;
                    border-radius:16px; padding:32px 28px; text-align:center;'>
            <div style='font-size:2rem; margin-bottom:10px;'>🗂️</div>
            <div style='font-family:"DM Sans",sans-serif; font-weight:700;
                        font-size:1.1rem; color:#151515; margin-bottom:8px;'>
                Try Demo Data
            </div>
            <div style='font-size:0.85rem; color:#6c675f; line-height:1.65; margin-bottom:20px;'>
                Not ready to upload? Explore a 3-month demo statement
                with real spending patterns, anomalies, leaks and insights.
                No account needed.
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        use_sample = st.button(
            "→ Explore with demo data",
            use_container_width=True,
            type="secondary",
        )
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<div class='full-width-guide'>", unsafe_allow_html=True)
    render_csv_guide()
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Logic (unchanged) ─────────────────────────────────────────────────────
    if not uploaded_file and not use_sample:
        st.stop()

    extra_bytes = tuple(f.read() for f in extra_files) if extra_files else ()

    if uploaded_file:
        st.session_state.uploaded_file_bytes = uploaded_file.read()
        st.session_state.extra_bytes         = extra_bytes
        st.session_state.data_source         = f"📁 {uploaded_file.name}"
        st.session_state.use_sample_data     = False
        st.session_state.manual_duplicate_decisions = {}

    if use_sample:
        st.session_state.use_sample_data     = True
        st.session_state.uploaded_file_bytes = None
        st.session_state.data_source         = "🗂️ Sample Data (Demo)"
        st.session_state.manual_duplicate_decisions = {}

    st.session_state.data_loaded = True
    st.session_state.show_merchant_review = True
    st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
# PROCESS DATA
# ──────────────────────────────────────────────────────────────────────────────

if st.session_state.uploaded_file_bytes:
    result = load_and_process(
        file_bytes=st.session_state.uploaded_file_bytes,
        extra_bytes_list=st.session_state.extra_bytes,
        user_id=st.session_state.user_id,
    )

elif st.session_state.use_sample_data:
    result = load_and_process(use_sample=True, user_id=st.session_state.user_id)

else:
    result = None


data_source = st.session_state.data_source

if result is None:
    df = None
    merged_raw = None
else:
    df, merged_raw = result

    if st.session_state.manual_duplicate_decisions:
        merged_raw = apply_manual_review(
            merged_raw,
            st.session_state.manual_duplicate_decisions,
        )
        clean = get_clean_df(merged_raw)
        df = categorize_transactions(clean, user_id=st.session_state.user_id)
        df = detect_anomalies(df)


if df is None:
    st.stop()


# ──────────────────────────────────────────────────────────────────────────────
# SIDEBAR 
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <style>
    /* Hide radio dot */
    div[data-testid="stSidebar"] div[role="radiogroup"] label div:first-child {
        display: none !important;
    }
    /* Nav button style */
    div[data-testid="stSidebar"] div[role="radiogroup"] label {
        display: block !important;
        width: 100% !important;
        padding: 9px 14px !important;
        border-radius: 0 8px 8px 0 !important;
        border-left: 3px solid transparent !important;
        color: #8A8AB0 !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.88rem !important;
        font-weight: 500 !important;
        cursor: pointer !important;
        transition: all 0.15s ease !important;
        margin-bottom: 2px !important;
    }
    div[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background: rgba(108,99,255,0.10) !important;
        color: #C8C8E8 !important;
        border-left: 3px solid rgba(108,99,255,0.3) !important;
    }
    div[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
        background: rgba(108,99,255,0.15) !important;
        color: #E0E0F0 !important;
        border-left: 3px solid #6C63FF !important;
        font-weight: 600 !important;
        border-radius: 0 8px 8px 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    # ... logo ...
    if st.session_state.get("page_override"):
        page = st.session_state.page_override
        st.session_state.page_override = None
    else:
        nav_pages = ["Dashboard", "Learn", "Leaks", "Transactions", "Budget", "Merchants", "AI Coach"]

        # Only show Multi-Account if multiple sources were uploaded
        if merged_raw is not None and merged_raw["source"].nunique() > 1:
            nav_pages.append("Multi-Account")

        page = st.radio(
            "Navigate",
            nav_pages,
            label_visibility="collapsed",
        )

    st.divider()

    try:
        stats_sidebar = get_summary_stats(df)
        st.markdown("""
        <div style='font-family:"DM Sans",sans-serif; font-size:0.78rem; font-weight:600;
                    letter-spacing:.08em; text-transform:uppercase; color:#8A8AB0;
                    margin-bottom:8px; padding-left:4px;'>Quick Stats</div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style='background:#F0EFFF; border:1px solid rgba(108,99,255,0.2);
                    border-radius:10px; padding:10px 14px; margin-bottom:8px;
                    border-top: 2px solid #6C63FF;'>
            <div style='font-family:"DM Sans",sans-serif; font-size:0.67rem;
                        color:#8A8AB0; text-transform:uppercase; letter-spacing:0.1em;
                        margin-bottom:2px;'>Total Spent</div>
            <div style='font-family:"Space Mono",monospace; font-size:1.25rem;
                        font-weight:700; color:#1a1a2e;'>₹{stats_sidebar['total_spent']:,.0f}</div>
        </div>
        <div style='background:#F0EFFF; border:1px solid rgba(108,99,255,0.2);
                    border-radius:10px; padding:10px 14px; margin-bottom:8px;
                    border-top: 2px solid #4ECDC4;'>
            <div style='font-family:"DM Sans",sans-serif; font-size:0.67rem;
                        color:#8A8AB0; text-transform:uppercase; letter-spacing:0.1em;
                        margin-bottom:2px;'>Transactions</div>
            <div style='font-family:"Space Mono",monospace; font-size:1.25rem;
                        font-weight:700; color:#1a1a2e;'>{stats_sidebar['total_transactions']}</div>
        </div>
        """, unsafe_allow_html=True)

        # optional reset button
        if st.button("🔄 Upload New File"):
            for key in [
                "data_loaded",
                "uploaded_file_bytes",
                "extra_bytes",
                "use_sample_data",
                "data_source"
            ]:
                if key in st.session_state:
                    del st.session_state[key]

            st.rerun()

    except:
        pass

# ──────────────────────────────────────────────────────────────────────────────
# COMPUTED DATA
# ──────────────────────────────────────────────────────────────────────────────
stats         = get_summary_stats(df)
cat_summary   = get_category_summary(df)
top_merchants = get_top_merchants(df, n=10)
anomaly_info  = get_anomaly_summary(df)
insights      = generate_full_insights(df)
nudges        = generate_nudges(df, insights["savings_rate"], insights["subscriptions"])


def _inr(amount: float) -> str:
    amount = float(amount or 0)
    if amount >= 100000:
        return f"₹{amount / 100000:.1f}L"
    if amount >= 1000:
        return f"₹{amount / 1000:.1f}K"
    return f"₹{amount:,.0f}"


def compute_money_score(df: pd.DataFrame, insights: dict, anomaly_info: dict) -> dict:
    savings_rate = float(insights["savings_rate"].get("rate", 0) or 0)
    spend = float(insights["savings_rate"].get("spend", 0) or 0)
    subs = insights["subscriptions"]
    monthly_subs = float(subs["monthly_cost"].sum()) if not subs.empty else 0
    bnpl_spend = float(df[(df["type"] == "Debit") & (df["category"] == "BNPL & Credit")]["amount"].sum())
    food_spend = float(df[(df["type"] == "Debit") & (df["category"] == "Food & Dining")]["amount"].sum())
    food_share = (food_spend / spend * 100) if spend else 0
    high_anomalies = int(anomaly_info.get("high_severity", 0) or 0)

    score = 55
    score += min(max(savings_rate, 0), 40) * 0.9
    score -= min(monthly_subs / 600, 12)
    score -= min(bnpl_spend / 2500, 12)
    score -= min(max(food_share - 12, 0) * 0.7, 10)
    score -= min(high_anomalies * 2, 10)
    score = int(max(0, min(100, round(score))))

    if score >= 80:
        label = "Strong"
        summary = "You are saving well. The main job is trimming recurring leaks."
    elif score >= 60:
        label = "Stable"
        summary = "Your basics look okay, but a few habits are quietly raising spend."
    elif score >= 40:
        label = "Watch"
        summary = "Spending needs attention this month, especially repeat charges."
    else:
        label = "At risk"
        summary = "Focus on one immediate spending reset before adding more goals."

    return {
        "score": score,
        "label": label,
        "summary": summary,
        "monthly_subs": monthly_subs,
        "bnpl_spend": bnpl_spend,
        "food_share": food_share,
    }


def build_leak_cards(df: pd.DataFrame, insights: dict) -> list:
    cards = []
    subs = insights["subscriptions"]
    if not subs.empty:
        cancelable = subs[
            subs["merchant"].str.contains(
                "netflix|spotify|prime|hotstar|youtube|zee5|sony|apple|cult|gym",
                case=False,
                na=False,
            )
        ]
        target = cancelable if not cancelable.empty else subs.head(3)
        monthly = float(target["monthly_cost"].sum())
        cards.append({
            "title": "Subscription audit",
            "amount": monthly,
            "detail": f"{len(target)} recurring charges need a yes/no review.",
            "action": f"Review {', '.join(target['merchant'].head(3).tolist())} and cancel one unused plan.",
        })

    food = df[(df["type"] == "Debit") & (df["category"] == "Food & Dining")]
    if not food.empty:
        monthly_food = float(food["amount"].sum() / max(df["month"].nunique(), 1))
        cards.append({
            "title": "Food delivery drift",
            "amount": monthly_food,
            "detail": f"{len(food)} food transactions across {df['month'].nunique()} months.",
            "action": f"Cap food orders next month to save about {_inr(monthly_food * 0.25)}.",
        })

    bnpl = df[(df["type"] == "Debit") & (df["category"] == "BNPL & Credit")]
    if not bnpl.empty:
        cards.append({
            "title": "BNPL / credit pressure",
            "amount": float(bnpl["amount"].sum()),
            "detail": f"{len(bnpl)} pay-later or credit-linked payments found.",
            "action": "Avoid new BNPL transactions until these payments clear.",
        })

    flagged = df[(df["type"] == "Debit") & (df["anomaly_score"] >= 3)].copy()
    if not flagged.empty:
        cards.append({
            "title": "Large unusual payments",
            "amount": float(flagged["amount"].sum()),
            "detail": f"{len(flagged)} high-signal transactions deserve a quick check.",
            "action": f"Verify the largest one: {flagged.sort_values('amount', ascending=False).iloc[0]['merchant']}.",
        })

    return sorted(cards, key=lambda x: x["amount"], reverse=True)


def best_next_action(leaks: list, score: dict) -> str:
    if leaks:
        top = leaks[0]
        if top["title"] == "Large unusual payments":
            return f"{top['action']} Amount to verify: {_inr(top['amount'])}."
        return f"{top['action']} Potential monthly impact: {_inr(top['amount'])}."
    if score["score"] >= 80:
        return "Set an automatic transfer for the first day after salary. Your savings rhythm is already strong."
    return "Set one category cap for the next 7 days and review again after a week."


def build_learning_cards(df: pd.DataFrame, cat_summary: pd.DataFrame, insights: dict, leaks: list) -> list:
    cards = []
    savings = insights["savings_rate"]
    top_cat = cat_summary.iloc[0] if not cat_summary.empty else None
    velocity = insights["spend_velocity"]
    guilt = insights["guilt_merchant"]

    cards.append({
        "title": "Your money personality",
        "lesson": (
            f"You save {savings['rate']}% of incoming money. "
            "That means your baseline discipline is strong; the next level is reducing invisible repeat spends."
            if savings["rate"] >= 25
            else f"You save {savings['rate']}% of incoming money. First focus on one repeatable spending limit, not a full budget overhaul."
        ),
    })

    if top_cat is not None:
        cards.append({
            "title": f"Why {top_cat['category']} matters",
            "lesson": (
                f"This category is {top_cat['percentage']}% of your debit spend. "
                "A small improvement here changes your month more than cutting tiny categories."
            ),
        })

    cards.append({
        "title": "Your daily burn rate",
        "lesson": (
            f"Your average debit burn is {_inr(velocity['avg_daily'])}/day. "
            f"A 10% slowdown is roughly {_inr(velocity['avg_daily'] * 3)} saved every 30 days."
        ),
    })

    if guilt:
        cards.append({
            "title": "Your repeat habit",
            "lesson": (
                f"{guilt['merchant']} appears {guilt['visits']} times and totals {_inr(guilt['total'])}. "
                "This is not about guilt; it is a visible habit loop you can cap."
            ),
        })

    if leaks:
        cards.append({
            "title": "The first lever to pull",
            "lesson": leaks[0]["action"],
        })

    return cards


money_score = compute_money_score(df, insights, anomaly_info)
leak_cards = build_leak_cards(df, insights)
next_action = best_next_action(leak_cards, money_score)
learning_cards = build_learning_cards(df, cat_summary, insights, leak_cards)

# ── Session state init ──────────────────────────────────────────────────────────
if "budgets" not in st.session_state:
    st.session_state.budgets = DEFAULT_BUDGETS.copy()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "ai_context" not in st.session_state:
    st.session_state.ai_context = build_financial_context(
        df, cat_summary, insights, anomaly_info
    )

st.markdown("""
<style>
:root {
    --mos-bg: #f7f5f0;
    --mos-panel: #ffffff;
    --mos-ink: #151515;
    --mos-muted: #6c675f;
    --mos-line: #ded9cf;
    --mos-accent: #1769ff;
}
.stApp { background: var(--mos-bg); color: var(--mos-ink); }
section[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid var(--mos-line);
}
.block-container { max-width: 1180px; padding-top: 1.25rem; }
.hero {
    background: transparent;
    border: 0;
    box-shadow: none;
    padding: 8px 0 20px;
    margin-bottom: 8px;
}
.hero::after { content: none; }
.hero h1 { color: var(--mos-ink); font-size: 2.05rem; letter-spacing: 0; }
.hero p { color: var(--mos-muted); font-size: 0.94rem; }
.kpi-card, .money-card, .insight-card, .action-card, .leak-card {
    background: var(--mos-panel);
    border: 1px solid var(--mos-line);
    border-radius: 8px;
    box-shadow: 0 1px 2px rgba(20,20,20,0.04);
}
.kpi-card::before { content: none; }
.kpi-card:hover { transform: none; box-shadow: 0 1px 2px rgba(20,20,20,0.04); }
.kpi-value { color: var(--mos-ink); font-family: 'DM Sans', sans-serif; font-size: 1.55rem; }
.kpi-label { color: var(--mos-muted); letter-spacing: 0; text-transform: none; }
.section-header { color: var(--mos-ink); border-bottom: 1px solid var(--mos-line); letter-spacing: 0; }
.section-header::after { background: var(--mos-accent); width: 28px; }
div[data-testid="stPlotlyChart"] {
    background: var(--mos-panel);
    border: 1px solid var(--mos-line);
    border-radius: 8px;
}
.money-score {
    font-size: 4.6rem;
    line-height: 1;
    color: var(--mos-ink);
    font-weight: 800;
    letter-spacing: 0;
}
.money-card { padding: 24px; min-height: 230px; }
.insight-card, .leak-card, .action-card { padding: 18px 20px; margin-bottom: 12px; }
.micro-label { color: var(--mos-muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; }
.card-title { color: var(--mos-ink); font-weight: 700; font-size: 1rem; margin-top: 6px; }
.card-detail { color: var(--mos-muted); font-size: 0.9rem; line-height: 1.5; margin-top: 6px; }
.amount-line { color: var(--mos-ink); font-weight: 800; font-size: 1.6rem; margin-top: 8px; }
.action-card { background: #101010; color: #ffffff; border-color: #101010; }
.action-card .micro-label, .action-card .card-detail { color: #cfcfcf; }
.action-card .card-title { color: #ffffff; font-size: 1.08rem; }
div, p, span, label, h1, h2, h3, h4, h5, h6,
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] {
    color: var(--mos-ink);
}
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label {
    color: var(--mos-ink) !important;
}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] div {
    color: var(--mos-ink) !important;
}
.stTextInput input, .stSelectbox div[data-baseweb="select"] > div,
.stNumberInput input {
    background: #ffffff !important;
    color: var(--mos-ink) !important;
    border-color: var(--mos-line) !important;
}
div[data-testid="stDataFrame"] {
    background: #ffffff;
    border: 1px solid var(--mos-line);
    border-radius: 8px;
}
.metric-row {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
}
.mini-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
}
.mini-table td {
    border-bottom: 1px solid var(--mos-line);
    padding: 10px 4px;
    color: var(--mos-ink);
}
.mini-table td:last-child {
    text-align: right;
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# HEADER (always shown)
# ──────────────────────────────────────────────────────────────────────────────
date_start = stats["date_range_start"].strftime("%d %b %Y") if pd.notna(stats["date_range_start"]) else "—"
date_end   = stats["date_range_end"].strftime("%d %b %Y")   if pd.notna(stats["date_range_end"])   else "—"

st.markdown(f"""
<div class='hero'>
    <h1>Vittā Money OS</h1>
    <p>{data_source} &nbsp;·&nbsp; {date_start} → {date_end} &nbsp;·&nbsp; {stats['total_transactions']} transactions</p>
</div>
""", unsafe_allow_html=True)

if st.session_state.get("show_merchant_review") and not st.session_state.get("merchant_review_done"):

    @st.dialog("Before we dive in 👋")
    def merchant_review_dialog():
        st.markdown("""
        <div style='font-family:"DM Sans",sans-serif;'>
            <div style='font-size:1rem; font-weight:600; color:#151515; margin-bottom:8px;'>
                Take 2 minutes for better insights
            </div>
            <div style='font-size:0.88rem; color:#6c675f; line-height:1.7; margin-bottom:20px;'>
                Vittā auto-categorizes your transactions, but reviewing your
                merchants helps us get it right — especially for local vendors,
                transfers to family, and recurring payments.
            </div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✦ Review merchants", type="primary", use_container_width=True):
                st.session_state.show_merchant_review = False
                st.session_state.merchant_review_done = True
                st.session_state.page_override = "Merchants"
                st.rerun()
        with col2:
            if st.button("Skip for now", use_container_width=True):
                st.session_state.show_merchant_review = False
                st.session_state.merchant_review_done = True
                st.rerun()

    merchant_review_dialog()
# ══════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
if page == "Dashboard":
    score_col, action_col = st.columns([0.9, 1.4])

    with score_col:
        st.markdown(f"""
        <div class='money-card'>
            <div class='micro-label'>Money wellness score</div>
            <div class='money-score'>{money_score['score']}</div>
            <div class='card-title'>{money_score['label']}</div>
            <div class='card-detail'>{money_score['summary']}</div>
        </div>
        """, unsafe_allow_html=True)

    with action_col:
        st.markdown(f"""
        <div class='action-card'>
            <div class='micro-label'>Best next action</div>
            <div class='card-title'>{next_action}</div>
            <div class='card-detail'>Chosen from recurring charges, food spend, BNPL exposure, savings rate, and high-signal transactions.</div>
        </div>
        """, unsafe_allow_html=True)

        a, b, c = st.columns(3)
        for col, label, value in [
            (a, "Spent", _inr(stats["total_spent"])),
            (b, "Saved", _inr(insights["savings_rate"]["savings"])),
            (c, "Savings rate", f"{insights['savings_rate']['rate']}%"),
        ]:
            with col:
                st.markdown(f"""
                <div class='kpi-card'>
                    <div class='kpi-value'>{value}</div>
                    <div class='kpi-label'>{label}</div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("<div class='section-header'>What matters this month</div>", unsafe_allow_html=True)
    insight_cols = st.columns(3)
    top_cat = cat_summary.iloc[0] if not cat_summary.empty else None
    insight_items = [
        (
            "Top spend area",
            _inr(top_cat["total_spent"]) if top_cat is not None else "No spend",
            f"{top_cat['category']} is {top_cat['percentage']}% of debit spend." if top_cat is not None else "Upload data to see your spend pattern.",
        ),
        (
            "Silent leaks",
            _inr(sum(card["amount"] for card in leak_cards[:3])),
            f"{len(leak_cards)} leak signals found across subscriptions, food, BNPL, and unusual payments.",
        ),
        (
            "Risk checks",
            str(anomaly_info["high_severity"]),
            "Transactions flagged for unusual amount, duplicate charges, or suspicious patterns.",
        ),
    ]
    for col, (title, amount, detail) in zip(insight_cols, insight_items):
        with col:
            st.markdown(f"""
            <div class='insight-card'>
                <div class='micro-label'>{title}</div>
                <div class='amount-line'>{amount}</div>
                <div class='card-detail'>{detail}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div class='section-header'>Money story</div>", unsafe_allow_html=True)
    story_left, story_right = st.columns([1.2, 1])
    monthly = insights["monthly_trend"].copy()
    recent_month = monthly.iloc[-1] if not monthly.empty else None
    previous_month = monthly.iloc[-2] if len(monthly) > 1 else None
    with story_left:
        if recent_month is not None:
            change_text = "No previous month to compare yet."
            if previous_month is not None:
                diff = recent_month["total_spent"] - previous_month["total_spent"]
                direction = "higher" if diff > 0 else "lower"
                change_text = f"{recent_month['month']} was {_inr(abs(diff))} {direction} than {previous_month['month']}."
            st.markdown(f"""
            <div class='insight-card'>
                <div class='micro-label'>This period in plain English</div>
                <div class='card-title'>You spent {_inr(stats['total_spent'])} across {stats['total_transactions']} transactions.</div>
                <div class='card-detail'>{change_text} Your average debit transaction is {_inr(stats['avg_transaction'])}, and your daily burn is {_inr(insights['spend_velocity']['avg_daily'])}.</div>
            </div>
            """, unsafe_allow_html=True)
    with story_right:
        top_merch = top_merchants.head(4).copy()
        rows = "".join(
            f"<tr><td>{r['merchant']}</td><td>{_inr(r['total_spent'])}</td></tr>"
            for _, r in top_merch.iterrows()
        )
        st.markdown(f"""
        <div class='insight-card'>
            <div class='micro-label'>Top merchants</div>
            <table class='mini-table'>{rows}</table>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div class='section-header'>Spend split</div>", unsafe_allow_html=True)
    chart_col, table_col = st.columns([1.25, 1])
    top_categories = cat_summary.head(6).sort_values("total_spent", ascending=True)
    fig = go.Figure(go.Bar(
        y=top_categories["category"],
        x=top_categories["total_spent"],
        orientation="h",
        marker_color="#1769ff",
        text=[_inr(v) for v in top_categories["total_spent"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>₹%{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#151515"),
        margin=dict(l=10, r=30, t=10, b=10),
        height=280,
        xaxis=dict(showgrid=True, gridcolor="#e7e1d8", title=""),
        yaxis=dict(showgrid=False, title=""),
        showlegend=False,
    )
    with chart_col:
        st.plotly_chart(fig, use_container_width=True)
    with table_col:
        cat_table = cat_summary[["category", "total_spent", "transaction_count", "percentage"]].head(8).copy()
        cat_table["total_spent"] = cat_table["total_spent"].apply(lambda x: f"₹{x:,.0f}")
        cat_table["percentage"] = cat_table["percentage"].apply(lambda x: f"{x}%")
        cat_table.columns = ["Category", "Spent", "Txns", "Share"]
        st.dataframe(cat_table, use_container_width=True, hide_index=True, height=318)

    st.markdown("<div class='section-header'>Recent transaction trail</div>", unsafe_allow_html=True)
    recent = df.sort_values("date", ascending=False).head(8)[
        ["date", "merchant", "category", "amount", "type", "anomaly_severity"]
    ].copy()
    recent["date"] = recent["date"].dt.strftime("%d %b")
    recent["amount"] = recent["amount"].apply(lambda x: f"₹{x:,.0f}")
    recent.columns = ["Date", "Merchant", "Category", "Amount", "Type", "Signal"]
    st.dataframe(recent, use_container_width=True, hide_index=True, height=300)

    st.markdown("<div class='section-header'>Learn from your own money</div>", unsafe_allow_html=True)
    lcols = st.columns(2)
    for i, card in enumerate(learning_cards[:4]):
        with lcols[i % 2]:
            st.markdown(f"""
            <div class='insight-card'>
                <div class='micro-label'>{card['title']}</div>
                <div class='card-detail'>{card['lesson']}</div>
            </div>
            """, unsafe_allow_html=True)


# PAGE: LEARN
elif page == "Learn":
    st.markdown("<div class='section-header'>Money lessons from your transactions</div>", unsafe_allow_html=True)
    for card in learning_cards:
        st.markdown(f"""
        <div class='insight-card'>
            <div class='micro-label'>{card['title']}</div>
            <div class='card-detail'>{card['lesson']}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div class='section-header'>Category lessons</div>", unsafe_allow_html=True)
    for _, row in cat_summary.head(6).iterrows():
        monthly_avg = row["total_spent"] / max(stats["months_covered"], 1)
        st.markdown(f"""
        <div class='leak-card'>
            <div class='micro-label'>{row['category']}</div>
            <div class='amount-line'>{_inr(monthly_avg)}/month</div>
            <div class='card-detail'>{row['transaction_count']} transactions, {row['percentage']}% of spending. Ask whether this category is a need, a lifestyle choice, or a leak.</div>
        </div>
        """, unsafe_allow_html=True)


# PAGE: LEAKS
elif page == "Leaks":
    st.markdown("<div class='section-header'>Silent leaks</div>", unsafe_allow_html=True)
    if leak_cards:
        for card in leak_cards:
            st.markdown(f"""
            <div class='leak-card'>
                <div class='micro-label'>{card['title']}</div>
                <div class='amount-line'>{_inr(card['amount'])}</div>
                <div class='card-detail'>{card['detail']}<br><b>Action:</b> {card['action']}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("No strong leak signals found in this statement.")

    st.markdown("<div class='section-header'>Detected recurring payments</div>", unsafe_allow_html=True)
    subs = insights["subscriptions"].copy()
    if not subs.empty:
        subs["monthly_cost"] = subs["monthly_cost"].apply(lambda x: f"₹{x:,.0f}")
        subs["annual_projection"] = subs["annual_projection"].apply(lambda x: f"₹{x:,.0f}")
        st.dataframe(
            subs.rename(columns={
                "merchant": "Merchant",
                "monthly_cost": "Monthly",
                "months_active": "Months active",
                "annual_projection": "Annual run-rate",
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No recurring subscription pattern detected.")


# PAGE: TRANSACTIONS
elif page == "Transactions":
    st.markdown("<div class='section-header'>Transactions</div>", unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns([1, 1, 2])
    with fc1:
        sel_cat = st.selectbox("Category", ["All"] + sorted(df["category"].unique().tolist()))
    with fc2:
        sel_type = st.selectbox("Type", ["All", "Debit", "Credit"])
    with fc3:
        search = st.text_input("Search", placeholder="Merchant or description")

    fdf = df.copy()
    if sel_cat != "All":
        fdf = fdf[fdf["category"] == sel_cat]
    if sel_type != "All":
        fdf = fdf[fdf["type"] == sel_type]
    if search:
        fdf = fdf[fdf["description"].str.contains(search, case=False, na=False)]

    display = fdf[["date", "description", "merchant", "category", "amount", "type", "anomaly_severity"]].copy()
    display["date"] = display["date"].dt.strftime("%d %b %Y")
    display["amount"] = display["amount"].apply(lambda x: f"₹{x:,.0f}")
    display.columns = ["Date", "Description", "Merchant", "Category", "Amount", "Type", "Signal"]
    st.dataframe(display, use_container_width=True, hide_index=True, height=520)

# PAGE: OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Overview":

    # KPI Row
    k1, k2, k3, k4, k5 = st.columns(5)
    kpis = [
        (k1, "Total Spent",       f"₹{stats['total_spent']:,.0f}",   None),
        (k2, "Total Income",      f"₹{stats['total_received']:,.0f}", None),
        (k3, "Avg Transaction",   f"₹{stats['avg_transaction']:,.0f}", None),
        (k4, "Savings Rate",      f"{insights['savings_rate']['rate']}%", None),
        (k5, "Anomalies Flagged", f"{anomaly_info['total_flagged']}", None),
    ]
    for col, label, value, delta in kpis:
        with col:
            st.markdown(f"""
            <div class='kpi-card'>
                <div class='kpi-value'>{value}</div>
                <div class='kpi-label'>{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Charts row 1
    col_left, col_right = st.columns([1, 1.6])
    with col_left:
        st.markdown("<div class='section-header'>Spend by Category</div>", unsafe_allow_html=True)
        st.plotly_chart(charts.category_donut(cat_summary), use_container_width=True)

    with col_right:
        st.markdown("<div class='section-header'>Monthly Spend Trend</div>", unsafe_allow_html=True)
        st.plotly_chart(charts.monthly_trend_chart(insights["monthly_trend"]), use_container_width=True)

    # Charts row 2
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("<div class='section-header'>Spending by Day of Week</div>", unsafe_allow_html=True)
        st.plotly_chart(charts.dayofweek_bar(insights["dayofweek_pattern"]), use_container_width=True)

    with col_b:
        st.markdown("<div class='section-header'>Savings Rate Gauge</div>", unsafe_allow_html=True)
        st.plotly_chart(charts.savings_gauge(insights["savings_rate"]["rate"]), use_container_width=True)

        v = insights["savings_rate"]
        s1, s2, s3 = st.columns(3)
        for scol, label, val in [
            (s1, "Income",  f"₹{v['income']:,.0f}"),
            (s2, "Spent",   f"₹{v['spend']:,.0f}"),
            (s3, "Savings", f"₹{v['savings']:,.0f}"),
        ]:
            scol.metric(label, val)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: CATEGORIES
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🏷️ Categories":

    # Category breakdown table
    st.markdown("<div class='section-header'>Category Breakdown</div>", unsafe_allow_html=True)

    display_df = cat_summary[["icon", "category", "total_spent", "transaction_count", "avg_transaction", "percentage"]].copy()
    display_df.columns = ["", "Category", "Total Spent (₹)", "# Transactions", "Avg (₹)", "% of Spend"]
    display_df["Total Spent (₹)"] = display_df["Total Spent (₹)"].apply(lambda x: f"₹{x:,.0f}")
    display_df["Avg (₹)"]         = display_df["Avg (₹)"].apply(lambda x: f"₹{x:,.0f}")
    display_df["% of Spend"]      = display_df["% of Spend"].apply(lambda x: f"{x}%")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Stacked monthly by category + top merchants
    col1, col2 = st.columns([1.5, 1])
    with col1:
        st.markdown("<div class='section-header'>Monthly Category Stack</div>", unsafe_allow_html=True)
        st.plotly_chart(charts.category_monthly_stacked(df, cat_summary), use_container_width=True)

    with col2:
        st.markdown("<div class='section-header'>Top 10 Merchants</div>", unsafe_allow_html=True)
        st.plotly_chart(charts.top_merchants_chart(top_merchants), use_container_width=True)

    # Spend calendar heatmap
    st.markdown("<div class='section-header'>Spend Calendar Heatmap</div>", unsafe_allow_html=True)
    st.plotly_chart(charts.spend_calendar_heatmap(df), use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ANOMALIES
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔍 Anomalies":

    # Anomaly KPIs
    a1, a2, a3, a4 = st.columns(4)
    for col, label, val, color in [
        (a1, "Total Flagged",    anomaly_info["total_flagged"],    "#FFD93D"),
        (a2, "High Severity",   anomaly_info["high_severity"],    "#FF6B6B"),
        (a3, "Medium Severity", anomaly_info["medium_severity"],  "#FF9F43"),
        (a4, "Flagged Amount",  f"₹{anomaly_info['flagged_amount']:,.0f}", "#A29BFE"),
    ]:
        with col:
            st.markdown(f"""
            <div class='kpi-card'>
                <div class='kpi-value' style='color:{color};'>{val}</div>
                <div class='kpi-label'>{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Scatter
    st.markdown("<div class='section-header'>Transaction Anomaly Map</div>", unsafe_allow_html=True)
    st.markdown("<small style='color:#8A8AB0'>Hover over dots to see details. Larger/brighter = more flags.</small>", unsafe_allow_html=True)
    st.plotly_chart(charts.anomaly_scatter(df), use_container_width=True)

    # Top flagged table
    st.markdown("<div class='section-header'>Top Flagged Transactions</div>", unsafe_allow_html=True)

    top_flagged = anomaly_info["top_flagged"].copy()
    if not top_flagged.empty:
        top_flagged["flags"] = top_flagged["anomaly_flags"].apply(lambda x: " · ".join(x))
        top_flagged["date"]  = top_flagged["date"].dt.strftime("%d %b %Y")
        top_flagged["amount"] = top_flagged["amount"].apply(lambda x: f"₹{x:,.0f}")

        def sev_badge(sev):
            cls = f"badge-{sev.lower()}"
            return f'<span class="badge {cls}">{sev}</span>'

        top_flagged["severity"] = top_flagged["anomaly_severity"].apply(sev_badge)

        st.dataframe(
            top_flagged[["date", "description", "amount", "anomaly_severity", "flags"]].rename(
                columns={"anomaly_severity": "Severity", "anomaly_flags": "Flags"}
            ),
            use_container_width=True,
            hide_index=True,
        )

    # Flag type breakdown
    st.markdown("<div class='section-header'>Flag Type Distribution</div>", unsafe_allow_html=True)
    flag_counts = {}
    for flags_list in df["anomaly_flags"]:
        for flag in flags_list:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1

    if flag_counts:
        flag_df = pd.DataFrame(list(flag_counts.items()), columns=["Flag", "Count"]).sort_values("Count", ascending=True)
        fig = go.Figure(go.Bar(
            y=flag_df["Flag"], x=flag_df["Count"],
            orientation="h",
            marker_color="#6C63FF",
            text=flag_df["Count"],
            textposition="outside",
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#E0E0E0"), height=280,
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.07)"),
            yaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🧠 Insights":

    st.markdown("<div class='section-header'>💡 Your Money Nudges</div>", unsafe_allow_html=True)

    if nudges:
        for nudge in nudges:
            st.markdown(f"<div class='nudge-card'>{nudge}</div>", unsafe_allow_html=True)
    else:
        st.info("Not enough data to generate personalized nudges. Add more months of transactions.")

    st.markdown("<br>", unsafe_allow_html=True)

    # Behavioral stats row
    vel = insights["spend_velocity"]
    guilt = insights["guilt_merchant"]
    wknd = insights["weekend_vs_weekday"]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("<div class='section-header'>💰 Spend Velocity</div>", unsafe_allow_html=True)
        for label, val in [
            ("Per Day",   f"₹{vel['avg_daily']:,.0f}"),
            ("Per Week",  f"₹{vel['avg_weekly']:,.0f}"),
            ("Per Month", f"₹{vel['avg_monthly']:,.0f}"),
        ]:
            st.markdown(f"""
            <div style='display:flex; justify-content:space-between; padding:10px 0; border-bottom:1px solid rgba(255,255,255,0.06); font-family:DM Sans;'>
                <span style='color:#8A8AB0; font-size:0.88rem;'>{label}</span>
                <span style='color:#E0E0F0; font-weight:600; font-family:Space Mono;'>{val}</span>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown("<div class='section-header'>📅 Weekend vs Weekday</div>", unsafe_allow_html=True)
        for label, val, color in [
            ("Weekdays", f"₹{wknd['weekday_total']:,.0f} ({wknd['weekday_pct']}%)", "#6C63FF"),
            ("Weekends", f"₹{wknd['weekend_total']:,.0f} ({wknd['weekend_pct']}%)", "#4ECDC4"),
        ]:
            st.markdown(f"""
            <div style='padding:14px; background:#1a1a2e; border-radius:8px; margin-bottom:8px; border-left: 3px solid {color};'>
                <div style='font-size:0.78rem; color:#8A8AB0; font-family:DM Sans; text-transform:uppercase;'>{label}</div>
                <div style='font-size:1.1rem; font-weight:700; color:#E0E0F0; font-family:Space Mono;'>{val}</div>
            </div>
            """, unsafe_allow_html=True)

    with col3:
        st.markdown("<div class='section-header'>😅 Guilty Pleasure</div>", unsafe_allow_html=True)
        if guilt:
            st.markdown(f"""
            <div style='padding:20px; background: linear-gradient(135deg, #1a0a2e, #1a1a2e); border-radius:10px; text-align:center; border: 1px solid rgba(255,107,107,0.3);'>
                <div style='font-size:2rem;'>😬</div>
                <div style='font-family:DM Sans; font-weight:700; font-size:1.15rem; color:#E0E0F0; margin:8px 0 4px;'>{guilt['merchant']}</div>
                <div style='font-size:0.82rem; color:#8A8AB0; font-family:DM Sans;'>{guilt['visits']} orders · ₹{guilt['total']:,.0f} total</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("No guilty pleasure detected (yet 😉)")

    st.markdown("<br>", unsafe_allow_html=True)

    # Subscriptions
    st.markdown("<div class='section-header'>📺 Detected Subscriptions</div>", unsafe_allow_html=True)
    subs = insights["subscriptions"]

    if not subs.empty:
        total_sub_monthly = subs["monthly_cost"].sum()
        st.markdown(f"""
        <div style='background:rgba(108,99,255,0.1); border:1px solid rgba(108,99,255,0.3); border-radius:10px; padding:16px 20px; margin-bottom:16px; font-family:DM Sans;'>
            <span style='color:#8A8AB0; font-size:0.85rem;'>Combined monthly subscription cost: </span>
            <span style='color:#6C63FF; font-weight:700; font-size:1.1rem; font-family:Space Mono;'>₹{total_sub_monthly:,.0f}/mo</span>
            <span style='color:#8A8AB0; font-size:0.85rem;'> → ₹{total_sub_monthly*12:,.0f}/year</span>
        </div>
        """, unsafe_allow_html=True)

        for _, row in subs.iterrows():
            st.markdown(f"""
            <div class='sub-row'>
                <div>
                    <div style='font-family:DM Sans; font-weight:600; color:#E0E0F0;'>{row['merchant']}</div>
                    <div style='font-size:0.75rem; color:#8A8AB0;'>Active {row['months_active']} months</div>
                </div>
                <div style='text-align:right;'>
                    <div style='font-family:Space Mono; font-weight:700; color:#4ECDC4;'>₹{row['monthly_cost']:,.0f}/mo</div>
                    <div style='font-size:0.75rem; color:#8A8AB0;'>₹{row['annual_projection']:,.0f}/yr</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No recurring subscriptions detected.")

    # Biggest month-over-month jump
    jump = insights["biggest_jump"]
    if jump:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<div class='section-header'>📈 Biggest MoM Spend Jump</div>", unsafe_allow_html=True)
        direction = "📈" if jump["change"] > 0 else "📉"
        st.markdown(f"""
        <div class='nudge-card' style='border-left-color: #FF6B6B;'>
            {direction} In <b>{jump['month']}</b>, your spending jumped by <b>₹{abs(jump['change']):,.0f}</b>
            ({'+' if jump['pct_change'] > 0 else ''}{jump['pct_change']:.1f}%) compared to <b>{jump['prev_month']}</b>.
            That went from ₹{jump['prev_amount']:,.0f} to ₹{jump['amount']:,.0f}.
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: TRANSACTIONS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Transactions":

    st.markdown("<div class='section-header'>Transaction Log</div>", unsafe_allow_html=True)

    # Filters
    fc1, fc2, fc3, fc4 = st.columns([1, 1, 1, 1])
    with fc1:
        all_cats = ["All"] + sorted(df["category"].unique().tolist())
        sel_cat = st.selectbox("Category", all_cats)
    with fc2:
        sel_type = st.selectbox("Type", ["All", "Debit", "Credit"])
    with fc3:
        sel_severity = st.selectbox("Anomaly Severity", ["All", "Clean", "Low", "Medium", "High"])
    with fc4:
        search = st.text_input("Search description", placeholder="e.g. Zomato, Uber…")

    # Apply filters
    fdf = df.copy()
    if sel_cat     != "All":      fdf = fdf[fdf["category"] == sel_cat]
    if sel_type    != "All":      fdf = fdf[fdf["type"] == sel_type]
    if sel_severity != "All":     fdf = fdf[fdf["anomaly_severity"] == sel_severity]
    if search:                    fdf = fdf[fdf["description"].str.contains(search, case=False, na=False)]

    st.markdown(f"<small style='color:#8A8AB0;'>Showing {len(fdf):,} of {len(df):,} transactions</small>", unsafe_allow_html=True)

    # Display
    display = fdf[["date", "description", "merchant", "category", "amount", "type", "anomaly_severity", "anomaly_flags"]].copy()
    display["date"]   = display["date"].dt.strftime("%d %b %Y")
    display["amount"] = display["amount"].apply(lambda x: f"₹{x:,.0f}")
    display["anomaly_flags"] = display["anomaly_flags"].apply(lambda x: " · ".join(x) if x else "—")
    display.columns  = ["Date", "Description", "Merchant", "Category", "Amount", "Type", "Severity", "Flags"]

    st.dataframe(display, use_container_width=True, hide_index=True, height=500)

    # Download
    csv_data = fdf.copy()
    csv_data["date"] = csv_data["date"].dt.strftime("%d/%m/%Y")
    csv_data["anomaly_flags"] = csv_data["anomaly_flags"].apply(lambda x: "; ".join(x))
    st.download_button(
        "⬇️ Download Filtered CSV",
        data=csv_data.to_csv(index=False),
        file_name="upi_analyzed.csv",
        mime="text/csv",
    )

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Merchants
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Merchants":
 
        render_merchant_review(
            df,
            user_id=st.session_state.user_id,
            load_and_process_fn=load_and_process,   # clears cache on save
        )

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: BUDGET TRACKER  🎯
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Budget":

    st.markdown("<div class='section-header'>Budget Tracker</div>", unsafe_allow_html=True)
    st.markdown(
        "<small style='color:#6c675f;'>Set your monthly budget. "
        "Spend is pulled automatically from your statement.</small>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Session state ─────────────────────────────────────────────────────────
    if "budgets" not in st.session_state:
        st.session_state.budgets = {
            k: {"amount": v["amount"], "period": v["period"]}
            for k, v in DEFAULT_BUDGETS.items()
        }
    if "monthly_budget" not in st.session_state:
        st.session_state.monthly_budget = 50000.0

    # ── Step 1 — Overall monthly budget ───────────────────────────────────────
    st.markdown("""
    <div style='font-family:"DM Sans",sans-serif; font-weight:700;
                font-size:1rem; color:#151515; margin-bottom:8px;'>
        What's your total monthly spending budget?
    </div>
    """, unsafe_allow_html=True)

    budget_col, _ = st.columns([1, 2])
    with budget_col:
        monthly_budget = st.number_input(
            "Monthly budget",
            min_value=0,
            max_value=50_00_000,
            value=int(st.session_state.monthly_budget),
            step=1000,
            label_visibility="collapsed",
            help="Your total monthly spending limit across all categories",
        )
        st.session_state.monthly_budget = float(monthly_budget)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 2 — Month overview grid ──────────────────────────────────────────
    if monthly_budget > 0:
        st.markdown("<div class='section-header'>Monthly Overview</div>", unsafe_allow_html=True)
        monthly_overview = compute_monthly_overview(df, monthly_budget)
        rows = [monthly_overview.iloc[i:i+6] for i in range(0, len(monthly_overview), 6)]

        for chunk in rows:
            month_cols = st.columns(len(chunk))
            for i, (_, mrow) in enumerate(chunk.iterrows()):
                with month_cols[i]:
                    pct   = min(mrow["pct_used"], 100)
                    color = mrow["color"]
                    st.markdown(f"""
                    <div style='background:#ffffff; border:2px solid {color}; border-radius:12px;
                                padding:16px 10px; text-align:center;'>
                        <div style='font-family:"DM Sans",sans-serif; font-size:0.72rem;
                                    color:#6c675f; text-transform:uppercase; letter-spacing:0.06em;'>
                            {mrow["month"]}
                        </div>
                        <div style='font-family:"DM Sans",sans-serif; font-weight:800;
                                    font-size:1.4rem; color:{color}; margin:6px 0;'>
                            {pct:.0f}%
                        </div>
                        <div style='font-size:0.75rem; color:#151515; font-family:"DM Sans",sans-serif;'>
                            ₹{mrow["spent"]:,.0f}
                        </div>
                        <div style='font-size:0.7rem; color:#6c675f; margin-top:2px;'>
                            of ₹{mrow["budget"]:,.0f}
                        </div>
                        <div style='background:#f7f5f0; border-radius:99px; height:4px; margin-top:8px;'>
                            <div style='width:{pct}%; height:4px; background:{color}; border-radius:99px;'></div>
                        </div>
                        <div style='font-size:0.68rem; color:{color}; font-weight:600;
                                    font-family:"DM Sans",sans-serif; margin-top:6px;'>
                            {mrow["status"]}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 3 — Select month to drill into ───────────────────────────────────
    available_months = sorted(
        df[df["type"] == "Debit"]["month"].unique().tolist(), reverse=True
    )
    st.markdown("<div class='section-header'>Category Breakdown</div>", unsafe_allow_html=True)

    sel_col, _ = st.columns([1, 2])
    with sel_col:
        selected_month = st.selectbox("Select month", available_months, index=0)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Compute category status ───────────────────────────────────────────────
    budget_status = compute_budget_status(
        df,
        st.session_state.budgets,
        selected_month=selected_month,
        monthly_budget=monthly_budget,
    )
    alerts = get_budget_alerts(budget_status)

    # ── KPI row ───────────────────────────────────────────────────────────────
    total_spent   = budget_status["spent"].sum()
    total_budget  = budget_status["monthly_budget"].sum()
    over_count    = int((budget_status["status"] == "Over Budget").sum())
    warn_count    = int((budget_status["status"] == "Warning").sum())

    k1, k2, k3, k4 = st.columns(4)
    for col, label, val, color in [
        (k1, "Total budgeted",        f"₹{total_budget:,.0f}",  "#151515"),
        (k2, "Total spent",           f"₹{total_spent:,.0f}",   "#FF6B6B"),
        (k3, "Remaining",             f"₹{max(total_budget - total_spent, 0):,.0f}", "#1769ff"),
        (k4, "Categories over limit", str(over_count),           "#FF9F43"),
    ]:
        with col:
            st.markdown(f"""
            <div class='kpi-card'>
                <div class='kpi-value' style='color:{color}; font-size:1.35rem;'>{val}</div>
                <div class='kpi-label'>{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Alerts ────────────────────────────────────────────────────────────────
    if alerts:
        st.markdown("<div class='section-header'>⚠️ Alerts</div>", unsafe_allow_html=True)
        for severity, cat, msg in alerts:
            bc = "#FF6B6B" if "Over" in severity else "#FF9F43" if "Breach" in severity else "#FFD93D"
            st.markdown(f"""
            <div class='nudge-card' style='border-left-color:{bc};'>
                <b style='color:{bc};'>{severity} — {cat}</b><br>
                <span style='font-size:0.85rem; color:#6c675f;'>{msg}</span>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

    # ── Category progress bars ────────────────────────────────────────────────
    view_mode = st.radio(
        "Display as",
        ["Progress bars", "Gauge cards"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if view_mode == "Progress bars":
        for _, row in budget_status.iterrows():
            if row["monthly_budget"] == 0 and row["spent"] == 0:
                continue
            pct   = min(row["pct_used"], 100)
            color = row["color"]
            per   = row["budget_period"].lower()
            proj_text = f" · 🔺 Projected ₹{row['projected_eom']:,.0f}" if row["will_breach"] and row["days_remaining"] > 0 else ""

            # Use st.columns to avoid HTML nesting issues
            left_col, right_col = st.columns([3, 1])
            with left_col:
                st.markdown(f"**{row['category']}**")
            with right_col:
                st.markdown(
                    f"<div style='text-align:right; font-size:0.85rem; color:{color};'>"
                    f"₹{row['spent']:,.0f} / ₹{row['monthly_budget']:,.0f}"
                    f"&nbsp;&nbsp;<span style='background:#f0f0f0; padding:2px 8px; "
                    f"border-radius:99px; font-size:0.72rem;'>{row['status']}</span></div>",
                    unsafe_allow_html=True,
                )

            # Progress bar
            st.markdown(f"""
            <div style='background:#f7f5f0; border-radius:99px; height:7px;
                        margin-bottom:4px; overflow:hidden;'>
                <div style='width:{pct}%; height:7px; background:{color}; border-radius:99px;'></div>
            </div>
            <div style='font-size:0.72rem; color:#6c675f; margin-bottom:16px;'>
                {row['pct_used']:.0f}% used &nbsp;·&nbsp;
                Budget ₹{row['budget_amount']:,.0f}/{per} &nbsp;·&nbsp;
                ₹{row['daily_burn']:,.0f}/day{proj_text}
            </div>
            """, unsafe_allow_html=True)

    else:
        # Gauge cards — 3 per row using st.columns (no nested HTML)
        rows_data = budget_status.to_dict("records")
        for i in range(0, len(rows_data), 3):
            chunk = rows_data[i:i+3]
            cols  = st.columns(3)
            for j, row in enumerate(chunk):
                color = row["color"]
                pct   = min(row["pct_used"], 100)
                r, cx, cy = 36, 44, 44
                circ  = 2 * 3.14159 * r
                dash  = circ * (pct / 100)
                gap   = circ - dash
                per   = row["budget_period"].lower()

                with cols[j]:
                    st.markdown(f"""
                    <div style='background:#ffffff; border:1px solid #ede8e0;
                                border-radius:12px; padding:16px;
                                text-align:center; margin-bottom:12px;'>
                        <svg width="88" height="88" viewBox="0 0 88 88">
                            <circle cx="{cx}" cy="{cy}" r="{r}"
                                fill="none" stroke="#f7f5f0" stroke-width="8"/>
                            <circle cx="{cx}" cy="{cy}" r="{r}"
                                fill="none" stroke="{color}" stroke-width="8"
                                stroke-dasharray="{dash:.1f} {gap:.1f}"
                                stroke-linecap="round"
                                transform="rotate(-90 {cx} {cy})"/>
                            <text x="{cx}" y="{cy+5}" text-anchor="middle"
                                font-family="DM Sans" font-size="13"
                                font-weight="700" fill="{color}">{pct:.0f}%</text>
                        </svg>
                        <div style='font-family:"DM Sans",sans-serif; font-weight:600;
                                    font-size:0.85rem; color:#151515; margin-top:4px;'>
                            {row["category"]}
                        </div>
                        <div style='font-size:0.75rem; color:#6c675f; margin-top:2px;'>
                            ₹{row["spent"]:,.0f} of ₹{row["monthly_budget"]:,.0f}
                        </div>
                        <div style='font-size:0.7rem; color:#8A8AB0; margin-top:2px;'>
                            Budget ₹{row["budget_amount"]:,.0f}/{per}
                        </div>
                        <div style='font-size:0.72rem; font-weight:600; color:{color};
                                    margin-top:4px;'>{row["status"]}</div>
                    </div>
                    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Budget editor ─────────────────────────────────────────────────────────
    with st.expander("Edit category budgets", expanded=False):
        st.markdown(
            "<small style='color:#6c675f;'>Set amount and period per category. "
            "Leave at 0 to skip a category.</small>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

        new_budgets = {}
        for i in range(0, len(ALL_CATEGORIES), 2):
            pair = ALL_CATEGORIES[i:i+2]
            cols = st.columns(4)
            for j, cat in enumerate(pair):
                cur = st.session_state.budgets.get(
                    cat, DEFAULT_BUDGETS.get(cat, {"amount": 0, "period": "Monthly"})
                )
                with cols[j * 2]:
                    amt = st.number_input(
                        cat,
                        min_value=0,
                        max_value=10_00_000,
                        value=int(cur.get("amount", 0)),
                        step=100,
                        key=f"bamt_{cat}",
                    )
                with cols[j * 2 + 1]:
                    per = st.selectbox(
                        f"Period",
                        ["Daily", "Weekly", "Monthly", "Yearly"],
                        index=["Daily", "Weekly", "Monthly", "Yearly"].index(
                            cur.get("period", "Monthly")
                        ),
                        key=f"bper_{cat}",
                        label_visibility="collapsed",
                    )
                new_budgets[cat] = {"amount": float(amt), "period": per}

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Save category budgets", type="primary"):
            st.session_state.budgets = new_budgets
            st.success("Saved!")
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Burn rate chart ───────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>Spend vs Budget — Category Chart</div>", unsafe_allow_html=True)

    valid = budget_status[budget_status["monthly_budget"] > 0]
    if not valid.empty:
        fig_b = go.Figure()
        fig_b.add_trace(go.Bar(
            name="Spent",
            x=valid["category"], y=valid["spent"],
            marker_color="#1769ff", opacity=0.9,
        ))
        fig_b.add_trace(go.Bar(
            name="Projected month end",
            x=valid["category"], y=valid["projected_eom"],
            marker_color="#FF9F43", opacity=0.45,
        ))
        fig_b.add_trace(go.Scatter(
            name="Budget limit",
            x=valid["category"], y=valid["monthly_budget"],
            mode="markers",
            marker=dict(symbol="line-ew", size=20, color="#FF6B6B",
                        line=dict(width=2, color="#FF6B6B")),
        ))
        fig_b.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#151515"), barmode="overlay",
            xaxis=dict(showgrid=False, tickangle=-30, tickfont=dict(size=10)),
            yaxis=dict(showgrid=True, gridcolor="#ede8e0", title="₹"),
            legend=dict(orientation="h", y=1.12),
            margin=dict(l=20, r=20, t=40, b=90), height=360,
        )
        st.plotly_chart(fig_b, use_container_width=True)
# ══════════════════════════════════════════════════════════════════════════════
# PAGE: FORECAST  🔮
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔮 Forecast":

    st.markdown("<div class='section-header'>🔮 Next Month Spend Forecast</div>", unsafe_allow_html=True)
    st.markdown("<small style='color:#8A8AB0'>Uses Auto-ARIMA / Holt-Winters / Linear Trend based on your history length</small>", unsafe_allow_html=True)

    with st.spinner("Running forecast models…"):
        forecast_df   = forecast_all_categories(df)
        total_forecast = get_total_forecast(forecast_df)

    if total_forecast:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class='nudge-card' style='border-left-color:#6C63FF; font-size:1rem; padding:20px 24px;'>
            🔮 <b>Total Forecast for {total_forecast['month']}:</b><br><br>
            {total_forecast['narrative']}
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

    # ── Forecast bar chart with confidence interval ───────────────────────────
    st.markdown("<div class='section-header'>Forecast by Category</div>", unsafe_allow_html=True)

    fig_f = go.Figure()

    fig_f.add_trace(go.Bar(
        name="Forecast (Point)",
        x=forecast_df["category"],
        y=forecast_df["point"],
        marker_color="#6C63FF",
        opacity=0.85,
        error_y=dict(
            type="data",
            symmetric=False,
            array=(forecast_df["upper_80"] - forecast_df["point"]).tolist(),
            arrayminus=(forecast_df["point"] - forecast_df["lower_80"]).tolist(),
            color="#FFD93D",
            thickness=2,
            width=6,
        ),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Forecast: ₹%{y:,.0f}<br>"
            "<extra></extra>"
        ),
    ))

    fig_f.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E0E0E0"),
        xaxis=dict(showgrid=False, tickangle=-25),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.07)", title="Forecast ₹"),
        margin=dict(l=20, r=20, t=40, b=80),
        height=380,
    )
    st.plotly_chart(fig_f, use_container_width=True)

    # ── Per-category history + forecast sparklines ───────────────────────────
    st.markdown("<div class='section-header'>History + Forecast per Category</div>", unsafe_allow_html=True)

    cols = st.columns(3)
    for i, (_, row) in enumerate(forecast_df.iterrows()):
        with cols[i % 3]:
            hist_y = row.get("history_series", [])
            hist_x = row.get("history_index", [])
            if not hist_y:
                continue

            # Trend color
            trend_color = {"increasing": "#FF6B6B", "decreasing": "#4ECDC4", "stable": "#FFD93D"}.get(
                row["trend"], "#6C63FF"
            )

            fig_s = go.Figure()
            fig_s.add_trace(go.Scatter(
                x=hist_x + [row["forecast_month"]],
                y=hist_y + [row["point"]],
                mode="lines+markers",
                line=dict(color="#6C63FF", width=2),
                marker=dict(size=5),
                showlegend=False,
            ))
            # Confidence band (just the forecast point with error bar)
            fig_s.add_trace(go.Scatter(
                x=[row["forecast_month"]],
                y=[row["point"]],
                mode="markers",
                marker=dict(size=10, color=trend_color, symbol="diamond"),
                error_y=dict(
                    type="data", symmetric=False,
                    array=[row["upper_80"] - row["point"]],
                    arrayminus=[row["point"] - row["lower_80"]],
                    color=trend_color,
                ),
                showlegend=False,
                name="Forecast",
            ))
            fig_s.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#E0E0E0", size=9),
                margin=dict(l=5, r=5, t=30, b=5),
                xaxis=dict(showgrid=False, tickfont=dict(size=8)),
                yaxis=dict(showgrid=False, tickfont=dict(size=8)),
                title=dict(text=f"{row['category']}", font=dict(size=11)),
                height=160,
            )
            st.plotly_chart(fig_s, use_container_width=True)
            st.markdown(
                f"<div style='font-size:0.72rem; color:#8A8AB0; font-family:DM Sans; "
                f"margin-top:-10px; margin-bottom:14px;'>₹{row['lower_80']:,.0f}–₹{row['upper_80']:,.0f} "
                f"· {row['method']}</div>",
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: MULTI-ACCOUNT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Multi-Account":

    st.markdown("<div class='section-header'>Multi-Account Deduplication</div>", unsafe_allow_html=True)
    st.markdown(
        "<small style='color:#6c675f;'>Detects duplicate transactions across multiple "
        "UPI apps — so your spend totals aren't double-counted.</small>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    if merged_raw is not None:
        dedup_report = get_dedup_report(merged_raw)

        # ── KPIs ──────────────────────────────────────────────────────────────
        d1, d2, d3, d4 = st.columns(4)
        for col, label, val, color in [
            (d1, "Accounts merged",    len(dedup_report["sources"]),                     "#1769ff"),
            (d2, "Total transactions", len(merged_raw),                                  "#151515"),
            (d3, "Flagged for review", dedup_report["total_duplicates"],                 "#FF9F43"),
            (d4, "Confirmed removed",  f"₹{dedup_report['amount_deduplicated']:,.0f}",  "#6BCB77"),
        ]:
            with col:
                st.markdown(f"""
                <div class='kpi-card'>
                    <div class='kpi-value' style='color:{color}; font-size:1.4rem;'>{val}</div>
                    <div class='kpi-label'>{label}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Source breakdown ───────────────────────────────────────────────────
        st.markdown("<div class='section-header'>Account Sources</div>", unsafe_allow_html=True)

        source_counts = merged_raw.groupby("source").size().reset_index(name="transactions")
        source_counts["debit_amount"] = merged_raw.groupby("source").apply(
            lambda g: g[g["type"] == "Debit"]["amount"].sum()
        ).values

        for _, sr in source_counts.iterrows():
            st.markdown(f"""
            <div style='display:flex; justify-content:space-between; padding:12px 16px;
                        background:#ffffff; border-radius:8px; margin-bottom:6px;
                        border:1px solid #ede8e0;'>
                <span style='font-family:"DM Sans",sans-serif; font-weight:600;
                             color:#151515;'>🏦 {sr['source']}</span>
                <span style='font-family:"DM Sans",sans-serif; font-size:0.85rem; color:#6c675f;'>
                    {sr['transactions']} txns &nbsp;·&nbsp; ₹{sr['debit_amount']:,.0f} spent
                </span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Duplicate breakdown ────────────────────────────────────────────────
        st.markdown("<div class='section-header'>Duplicate Summary</div>", unsafe_allow_html=True)

        e1, e2 = st.columns(2)
        with e1:
            st.markdown(f"""
            <div class='kpi-card'>
                <div class='kpi-value' style='color:#1769ff; font-size:1.3rem;'>
                    {dedup_report['exact_ref_dups']}
                </div>
                <div class='kpi-label'>Exact reference matches</div>
                <div style='font-size:0.75rem; color:#6c675f; margin-top:4px;'>
                    Same UPI transaction ID found in both accounts
                </div>
            </div>
            """, unsafe_allow_html=True)
        with e2:
            st.markdown(f"""
            <div class='kpi-card'>
                <div class='kpi-value' style='color:#FF9F43; font-size:1.3rem;'>
                    {dedup_report['fuzzy_dups']}
                </div>
                <div class='kpi-label'>Fuzzy description matches</div>
                <div style='font-size:0.75rem; color:#6c675f; margin-top:4px;'>
                    Same amount + date + similar description across accounts
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Duplicate rows table ───────────────────────────────────────────────
        duplicate_pairs = get_duplicate_pairs(merged_raw)

        if duplicate_pairs:
            st.markdown("<div class='section-header'>Detected Duplicate Candidates</div>", unsafe_allow_html=True)
            dup_display = dedup_report["review_rows"].copy()
            dup_display["date"] = pd.to_datetime(dup_display["date"]).dt.strftime("%d %b %Y")
            dup_display["amount"] = dup_display["amount"].apply(lambda x: f"₹{x:,.0f}")
            dup_display.columns = ["Date", "Description", "Amount", "Source", "Reason", "Decision"]
            st.dataframe(dup_display, use_container_width=True, hide_index=True)
        else:
            st.success("✅ No duplicate transactions found across your accounts!")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<div class='section-header'>Review Duplicate Pairs</div>", unsafe_allow_html=True)

        if duplicate_pairs:
            st.caption("Pending rows stay in analytics until you explicitly remove them.")

        for pair in duplicate_pairs:
            pair_id = str(pair["pair_id"])
            original = pair["original"]
            duplicate = pair["duplicate"]
            previous_decision = st.session_state.manual_duplicate_decisions.get(pair_id)
            current_decision = previous_decision or "Pending"
            radio_key = f"dup_action_{pair_id}"

            st.markdown(f"#### {pair_id}")

            c1, c2 = st.columns(2, gap="large")

            with c1:
                st.markdown("**Original Transaction**")

                st.dataframe(pd.DataFrame([{
                    "Date": pd.to_datetime(original["date"]).strftime("%d %b %Y"),
                    "Description": original["description"],
                    "Amount": f"₹{original['amount']:,.0f}",
                    "Source": original["source"],
                }]), use_container_width=True, hide_index=True)

            with c2:
                st.markdown("**Flagged Transaction**")

                st.dataframe(pd.DataFrame([{
                    "Date": pd.to_datetime(duplicate["date"]).strftime("%d %b %Y"),
                    "Description": duplicate["description"],
                    "Amount": f"₹{duplicate['amount']:,.0f}",
                    "Source": duplicate["source"],
                }]), use_container_width=True, hide_index=True)

            decision_options = ["Pending review", "Remove duplicate", "Keep both"]
            default_index = {
                "Pending": 0,
                "Duplicate": 1,
                "Keep": 2,
            }.get(current_decision, 0)
            choice = st.radio(
                f"Decision for {pair_id}",
                decision_options,
                index=default_index,
                horizontal=True,
                key=radio_key,
            )

            if choice == "Remove duplicate":
                new_decision = "Duplicate"
            elif choice == "Keep both":
                new_decision = "Keep"
            else:
                new_decision = None

            if new_decision is None and previous_decision is not None:
                st.session_state.manual_duplicate_decisions.pop(pair_id, None)
                st.rerun()
            elif new_decision is not None and previous_decision != new_decision:
                st.session_state.manual_duplicate_decisions[pair_id] = new_decision
                st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)
            
        # ── How it works ──────────────────────────────────────────────────────
        with st.expander("ℹ️ How deduplication works"):
            st.markdown("""
            Duplicates are detected in two stages:

            **Stage 1 — Exact reference match** (high confidence)
            Same UPI transaction reference number (e.g. S96714620) + same amount
            across two different accounts → definitive duplicate.

            **Stage 2 — Fuzzy match** (fallback)
            When no reference number is available:
            - Amount matches within ±₹1
            - Date within ±1 day
            - Description similarity ≥ 72/100

            The transaction with the richer description is always kept.
            The other is excluded from all spend analytics.
            """)
    else:
        st.info("Upload your primary CSV, then add extra account CSVs using 'Add more accounts' in the sidebar.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: AI ADVISOR  🤖
# ══════════════════════════════════════════════════════════════════════════════
elif page == "AI Coach":

    # ── Guard checks ──────────────────────────────────────────────────────────
    if not ANTHROPIC_AVAILABLE:
        st.error("Groq SDK not installed. Run: `pip install groq`")
        st.stop()

    client = get_api_client()
    if client is None:
        st.warning("API key not configured. Set GROQ_API_KEY environment variable.")
        st.stop()

    # ── Session state ─────────────────────────────────────────────────────────
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "questions_asked" not in st.session_state:
        st.session_state.questions_asked = 0
    if "last_reset_date" not in st.session_state:
        st.session_state.last_reset_date = pd.Timestamp.now().date()
    

    # Reset daily limit at midnight
    if st.session_state.last_reset_date != pd.Timestamp.now().date():
        st.session_state.questions_asked = 0
        st.session_state.last_reset_date = pd.Timestamp.now().date()

    DAILY_LIMIT = 10
    remaining = DAILY_LIMIT - st.session_state.questions_asked

    # ── Page header ───────────────────────────────────────────────────────────
    st.markdown("""
    <div style='padding: 8px 0 4px;'>
        <div style='font-family:"DM Sans",sans-serif; font-size:1.6rem; font-weight:700; color:#151515;'>
            Ask your money anything
        </div>
        <div style='font-size:0.88rem; color:#6c675f; margin-top:4px; font-family:"DM Sans",sans-serif;'>
            Powered by your actual transaction data · Not generic advice
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Rate limit bar ────────────────────────────────────────────────────────
    pct = (remaining / DAILY_LIMIT) * 100
    bar_color = "#1769ff" if remaining > 4 else "#FF9F43" if remaining > 2 else "#FF6B6B"
    st.markdown(f"""
    <div style='display:flex; align-items:center; gap:12px; margin:12px 0 20px;'>
        <div style='flex:1; background:#ede8e0; border-radius:99px; height:4px;'>
            <div style='width:{pct}%; height:4px; background:{bar_color}; border-radius:99px; transition:width 0.4s;'></div>
        </div>
        <div style='font-size:0.75rem; color:#6c675f; font-family:"DM Sans",sans-serif; white-space:nowrap;'>
            {remaining} of {DAILY_LIMIT} questions left today
        </div>
    </div>
    """, unsafe_allow_html=True)

    if remaining <= 0:
        st.markdown("""
        <div style='background:#fff8f0; border:1px solid #FF9F43; border-radius:12px;
                    padding:20px 24px; text-align:center; font-family:"DM Sans",sans-serif;'>
            <div style='font-size:1.3rem; margin-bottom:8px;'>🧠</div>
            <div style='font-weight:600; color:#151515;'>You've used all 10 questions today</div>
            <div style='color:#6c675f; font-size:0.88rem; margin-top:4px;'>Come back tomorrow — your limit resets at midnight.</div>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    # ── Monthly summary button ────────────────────────────────────────────────
    col_btn, col_space = st.columns([1, 3])
    with col_btn:
        gen_summary = st.button(
            "✦ Monthly snapshot",
            use_container_width=True,
            type="secondary",
        )
    if gen_summary:
        if st.session_state.questions_asked < DAILY_LIMIT:
            with st.spinner(""):
                summary = generate_monthly_summary(client, st.session_state.ai_context)
            st.session_state.questions_asked += 1
            st.markdown(f"""
            <div style='background:#f0f4ff; border:1px solid #d0dbff; border-radius:12px;
                        padding:18px 22px; font-family:"DM Sans",sans-serif; font-size:0.9rem;
                        color:#151515; line-height:1.8; margin-bottom:16px;'>
                {summary}
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='margin:8px 0 10px;'></div>", unsafe_allow_html=True)

    st.markdown("""
    <div style='font-size:0.75rem; text-transform:uppercase; letter-spacing:0.08em;
                color:#6c675f; font-family:"DM Sans",sans-serif; margin-bottom:10px;'>
        Quick questions
    </div>
    """, unsafe_allow_html=True)

    # Render chips in rows of 4
    for row_start in range(0, len(STARTER_QUESTIONS), 4):
        cols = st.columns(4)
        for i, col in enumerate(cols):
            idx = row_start + i
            if idx < len(STARTER_QUESTIONS):
                with col:
                    if st.button(
                        STARTER_QUESTIONS[idx],
                        key=f"chip_{idx}",
                        use_container_width=True,
                    ):
                        if st.session_state.questions_asked < DAILY_LIMIT:
                            st.session_state.chat_history.append({
                                "role": "user",
                                "content": STARTER_QUESTIONS[idx]
                            })
                            st.session_state.questions_asked += 1
                            st.rerun()

    # ── Chip styling ──────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    /* Chip style for starter questions */
    div[data-testid="stHorizontalBlock"] button[kind="secondary"] {
        background: #ffffff !important;
        border: 1px solid #ded9cf !important;
        border-radius: 99px !important;
        color: #151515 !important;
        font-size: 0.8rem !important;
        font-family: "DM Sans", sans-serif !important;
        padding: 6px 14px !important;
        transition: all 0.15s !important;
    }
    div[data-testid="stHorizontalBlock"] button[kind="secondary"]:hover {
        background: #f0f4ff !important;
        border-color: #1769ff !important;
        color: #1769ff !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<div style='margin:20px 0 8px;'></div>", unsafe_allow_html=True)

    # ── Chat history ──────────────────────────────────────────────────────────
    if st.session_state.chat_history:
        for msg in st.session_state.chat_history:
            role    = msg["role"]
            content = msg["content"]
            if role == "user":
                st.markdown(f"""
                <div style='display:flex; justify-content:flex-end; margin-bottom:16px;'>
                    <div style='background:#151515; color:#ffffff; padding:12px 18px;
                                border-radius:18px 18px 4px 18px; max-width:65%;
                                font-family:"DM Sans",sans-serif; font-size:0.88rem;
                                line-height:1.55;'>
                        {content}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style='display:flex; justify-content:flex-start; margin-bottom:16px; gap:10px;'>
                    <div style='width:28px; height:28px; border-radius:50%; background:#1769ff;
                                display:flex; align-items:center; justify-content:center;
                                font-size:0.7rem; color:white; flex-shrink:0; margin-top:4px;
                                font-family:"DM Sans",sans-serif; font-weight:700;'>A</div>
                    <div style='background:#ffffff; color:#151515; padding:12px 18px;
                                border-radius:4px 18px 18px 18px; max-width:70%;
                                font-family:"DM Sans",sans-serif; font-size:0.88rem;
                                line-height:1.65; border:1px solid #ede8e0;'>
                        {content}
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        # Empty state
        st.markdown("""
        <div style='text-align:center; padding:40px 20px; color:#6c675f;
                    font-family:"DM Sans",sans-serif;'>
            <div style='font-size:2rem; margin-bottom:12px;'>💬</div>
            <div style='font-weight:600; color:#151515; font-size:1rem;'>
                Your financial data is loaded and ready
            </div>
            <div style='font-size:0.85rem; margin-top:6px;'>
                Pick a quick question above or type anything below
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Auto-respond with streaming ───────────────────────────────────────────
    if st.session_state.chat_history and st.session_state.chat_history[-1]["role"] == "user":
        last_user_msg    = st.session_state.chat_history[-1]["content"]
        history_for_api  = st.session_state.chat_history[-10:]  # cap at last 10

        # Show streaming response
        with st.chat_message("assistant", avatar="💙"):
            response = st.write_stream(
                chat_stream(client, st.session_state.ai_context, history_for_api[:-1], last_user_msg)
            )

        st.session_state.chat_history.append({"role": "assistant", "content": response})
        st.rerun()

    # ── Input bar ─────────────────────────────────────────────────────────────
    if "input_key" not in st.session_state:
        st.session_state.input_key = 0

    st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)
    col_input, col_send, col_clear = st.columns([7, 1.2, 0.9])

    with col_input:
        user_input = st.text_input(
            "chat_input_label",
            placeholder="Ask anything about your spending…",
            label_visibility="collapsed",
            key=f"chat_input_{st.session_state.input_key}",
        )
    with col_send:
        send = st.button("Send →", type="primary", use_container_width=True)
    with col_clear:
        if st.button("Clear", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.input_key += 1
            st.rerun()

    if send and user_input.strip():
        if st.session_state.questions_asked < DAILY_LIMIT:
            st.session_state.chat_history.append({
                "role": "user",
                "content": user_input.strip()
            })
            st.session_state.questions_asked += 1
            st.session_state.input_key += 1
            st.rerun()
        else:
            st.warning("You've reached today's limit of 10 questions.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: BENCHMARKS  📈
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📈 Benchmarks":

    st.markdown("<div class='section-header'>📈 Peer Benchmarking</div>", unsafe_allow_html=True)
    st.markdown("<small style='color:#8A8AB0'>Compare your spending to India city-tier averages by income bracket</small>", unsafe_allow_html=True)

    # ── User profile inputs ───────────────────────────────────────────────────
    p1, p2 = st.columns(2)
    with p1:
        city_tier = st.selectbox("Your city tier",
            ["Tier 1 (Metro)", "Tier 2 (Mid-size)", "Tier 3 (Small city/town)"],
            index=0)
        city_tier_key = city_tier.split(" ")[0] + " " + city_tier.split(" ")[1]   # "Tier 1"
    with p2:
        monthly_income = st.number_input(
            "Monthly take-home income (₹)",
            min_value=10_000, max_value=10_00_000,
            value=60_000, step=5_000,
        )

    # ── Compute ───────────────────────────────────────────────────────────────
    bench_df       = compute_benchmarks(cat_summary, stats["months_covered"], city_tier_key, monthly_income)
    savings_bench  = get_savings_benchmark(insights["savings_rate"]["rate"], city_tier_key, monthly_income)
    over_cats, under_cats = get_standout_categories(bench_df)

    # ── Savings rate vs peers ─────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class='nudge-card' style='border-left-color:{savings_bench["color"]};'>
        <b style='color:{savings_bench["color"]};'>{savings_bench["label"]}</b><br>
        {savings_bench["message"]}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Standouts ────────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='section-header'>🔺 Overspending vs Peers</div>", unsafe_allow_html=True)
        for _, row in over_cats.iterrows():
            st.markdown(f"""
            <div style='padding:12px 16px; background:#1a1a2e; border-radius:8px; margin-bottom:6px;
                        border-left:3px solid #FF6B6B;'>
                <div style='font-family:DM Sans; font-weight:600; color:#E0E0F0;'>{row['category']}</div>
                <div style='font-size:0.8rem; color:#8A8AB0; margin-top:3px;'>
                    You: ₹{row['user_monthly_avg']:,.0f}/mo · Peers: ₹{row['benchmark']:,.0f}/mo ·
                    <span style='color:#FF6B6B;'>{row['ratio']:.1f}x</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='section-header'>✅ Spending Less Than Peers</div>", unsafe_allow_html=True)
        for _, row in under_cats.iterrows():
            st.markdown(f"""
            <div style='padding:12px 16px; background:#1a1a2e; border-radius:8px; margin-bottom:6px;
                        border-left:3px solid #4ECDC4;'>
                <div style='font-family:DM Sans; font-weight:600; color:#E0E0F0;'>{row['category']}</div>
                <div style='font-size:0.8rem; color:#8A8AB0; margin-top:3px;'>
                    You: ₹{row['user_monthly_avg']:,.0f}/mo · Peers: ₹{row['benchmark']:,.0f}/mo ·
                    <span style='color:#4ECDC4;'>{row['ratio']:.1f}x</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Full comparison chart ─────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<div class='section-header'>You vs Peers — Full Comparison</div>", unsafe_allow_html=True)

    fig_bench = go.Figure()
    fig_bench.add_trace(go.Bar(
        name="Your Avg (monthly)",
        x=bench_df["category"],
        y=bench_df["user_monthly_avg"],
        marker_color="#6C63FF",
        opacity=0.9,
    ))
    fig_bench.add_trace(go.Bar(
        name="Peer Avg (monthly)",
        x=bench_df["category"],
        y=bench_df["benchmark"],
        marker_color="#4ECDC4",
        opacity=0.6,
    ))
    fig_bench.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E0E0E0"), barmode="group",
        xaxis=dict(showgrid=False, tickangle=-25),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.07)", title="₹/month"),
        legend=dict(orientation="h", y=1.1),
        margin=dict(l=20, r=20, t=40, b=80),
        height=380,
    )
    st.plotly_chart(fig_bench, use_container_width=True)

    # ── Ratio heatmap (how many x vs peers) ──────────────────────────────────
    st.markdown("<div class='section-header'>Spend Ratio vs Peers</div>", unsafe_allow_html=True)

    fig_ratio = go.Figure(go.Bar(
        x=bench_df["category"],
        y=bench_df["ratio"],
        marker_color=bench_df["color"].tolist(),
        text=[f"{r:.1f}x" for r in bench_df["ratio"]],
        textposition="outside",
        textfont=dict(size=10),
        hovertemplate="<b>%{x}</b><br>Ratio: %{y:.2f}x<extra></extra>",
    ))
    fig_ratio.add_hline(y=1.0, line_dash="dash", line_color="#FFD93D",
                         annotation_text="Peer Average", annotation_position="top right")
    fig_ratio.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E0E0E0"),
        xaxis=dict(showgrid=False, tickangle=-25),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.07)", title="Ratio (1.0 = peer avg)"),
        margin=dict(l=20, r=20, t=40, b=80),
        height=350,
    )
    st.plotly_chart(fig_ratio, use_container_width=True)

    # ── Category insights table ───────────────────────────────────────────────
    st.markdown("<div class='section-header'>Category Insights</div>", unsafe_allow_html=True)
    insight_display = bench_df[["category", "user_monthly_avg", "benchmark", "ratio", "vs_peers", "insight"]].copy()
    insight_display.columns = ["Category", "Your Monthly (₹)", "Peer Avg (₹)", "Ratio", "vs Peers", "Insight"]
    insight_display["Your Monthly (₹)"] = insight_display["Your Monthly (₹)"].apply(lambda x: f"₹{x:,.0f}")
    insight_display["Peer Avg (₹)"]     = insight_display["Peer Avg (₹)"].apply(lambda x: f"₹{x:,.0f}")
    insight_display["Ratio"]            = insight_display["Ratio"].apply(lambda x: f"{x:.2f}x")
    st.dataframe(insight_display, use_container_width=True, hide_index=True)
