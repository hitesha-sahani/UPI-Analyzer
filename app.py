import streamlit as st
import pandas as pd
from pathlib import Path
import base64
import html


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

# ── New feature imports ─────────────────────────────────────────────────────────
from modules.budget_tracker import (
       DEFAULT_BUDGETS )
from modules.deduplicator     import (
    merge_accounts, deduplicate, apply_manual_review,
    get_clean_df
)
from modules.pages import PAGE_RENDERERS
from modules.pages.common import PageContext
from modules.pages.duplicate_review import render_duplicate_review
from modules.ai_advisor import (build_financial_context)
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
    background: #ffffff;
    border: 1px solid #e8eaf2;
    border-left: 4px solid #6C63FF;
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 10px;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.88rem;
    color: #2d3748;
    line-height: 1.6;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
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

/* All Streamlit buttons */
div.stButton > button {
    background: linear-gradient(135deg, #6C63FF, #4ECDC4);
    color: white;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    padding: 0.6rem 1rem;
    transition: all 0.2s ease;
}

/* Hover effect */
div.stButton > button:hover {
    background: linear-gradient(135deg, #5a52e0, #3dbbb2);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(108,99,255,0.3);
}

/* Optional: remove ugly focus border */
div.stButton > button:focus {
    outline: none;
    box-shadow: none;
}            

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
                    Know your money.<br>Fix the leaks.
                </div>
                <div style='font-size:1.2rem; font-weight:600;
                            color:#1769ff; margin-bottom:16px;'>
                    A personal money checkup from your own UPI data.
                </div>
                <div style='font-size:0.98rem; color:#6c675f;
                            line-height:1.75; max-width:480px;'>
                    Upload a CSV and see what is quietly shaping your month:
                    repeat spends, avoidable leaks, unusual payments, and the
                    habits that deserve a tiny reset. No judgment. Just clarity.
                </div>
            </div>

            <div style='flex:1; display:flex; flex-wrap:wrap; gap:16px;
                        align-content:flex-start; padding-top:8px;'>
                {"".join([
                    f"<div style='background:white; border:1px solid #e5ddd0; "
                    f"padding:12px 18px; border-radius:999px; font-size:0.9rem; "
                    f"font-weight:600; color:#151515; "
                    f"box-shadow:0 1px 3px rgba(0,0,0,0.05);'>{chip}</div>"
                    for chip in [
                        "Find silent leaks",
                        "Spot repeat charges",
                        "Catch unusual payments",
                        "See spending habits",
                        "Ask your AI coach",
                        "Clean duplicate entries",
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
            Start with your statement
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
                Try it with demo data
            </div>
            <div style='font-size:0.85rem; color:#6c675f; line-height:1.65; margin-bottom:20px;'>
                Want to look around first? Open a sample month and see the
                leaks, habits, and coaching flow before using your own CSV.
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        use_sample = st.button(
            "Explore demo first",
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

        # Only show Duplicate Review if multiple sources were uploaded
        if merged_raw is not None and merged_raw["source"].nunique() > 1:
            nav_pages.append("Duplicate Review")

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
.dashboard-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    background: linear-gradient(135deg, #ffffff 0%, #f7f5f0 100%);
    border: 1px solid var(--mos-line);
    border-radius: 8px;
    padding: 18px 20px;
    margin: 2px 0 22px;
    box-shadow: 0 1px 2px rgba(20,20,20,0.04);
}
.dashboard-brand {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 240px;
}
.dashboard-logo {
    width: 42px;
    height: 42px;
    border-radius: 8px;
    object-fit: cover;
    border: 1px solid var(--mos-line);
}
.dashboard-title {
    color: var(--mos-ink) !important;
    font-size: 1.42rem;
    font-weight: 800;
    line-height: 1.1;
}
.dashboard-subtitle {
    color: var(--mos-muted) !important;
    font-size: 0.82rem;
    margin-top: 4px;
}
.dashboard-meta {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 8px;
}
.header-chip {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 118px;
    background: #ffffff;
    border: 1px solid var(--mos-line);
    border-radius: 8px;
    padding: 8px 10px;
}
.header-chip-label {
    color: var(--mos-muted) !important;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.header-chip-value {
    color: var(--mos-ink) !important;
    font-size: 0.88rem;
    font-weight: 700;
    line-height: 1.25;
}
@media (max-width: 760px) {
    .dashboard-header {
        align-items: flex-start;
        flex-direction: column;
        padding: 16px;
    }
    .dashboard-meta {
        justify-content: flex-start;
        width: 100%;
    }
    .header-chip {
        flex: 1 1 140px;
    }
}
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

data_source_label = html.escape(str(data_source))
transaction_count = f"{int(stats['total_transactions']):,}" if pd.notna(stats["total_transactions"]) else "0"

st.markdown(f"""
<div class='dashboard-header'>
    <div class='dashboard-brand'>
        <img class='dashboard-logo' src='data:image/png;base64,{logo_b64}' alt='Vitta logo'/>
        <div>
            <div class='dashboard-title'>Vitta Money OS</div>
            <div class='dashboard-subtitle'>Your financial command center</div>
        </div>
    </div>
    <div class='dashboard-meta'>
        <div class='header-chip'>
            <span class='header-chip-label'>Source</span>
            <span class='header-chip-value'>{data_source_label}</span>
        </div>
        <div class='header-chip'>
            <span class='header-chip-label'>Period</span>
            <span class='header-chip-value'>{date_start} &rarr; {date_end}</span>
        </div>
        <div class='header-chip'>
            <span class='header-chip-label'>Transactions</span>
            <span class='header-chip-value'>{transaction_count}</span>
        </div>
    </div>
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

page_context = PageContext(
    df=df,
    merged_raw=merged_raw,
    stats=stats,
    cat_summary=cat_summary,
    top_merchants=top_merchants,
    insights=insights,
    anomaly_info=anomaly_info,
    leak_cards=leak_cards,
    learning_cards=learning_cards,
    money_score=money_score,
    next_action=next_action,
    user_id=st.session_state.user_id,
    load_and_process_fn=load_and_process,
)

if page == "Duplicate Review":
    render_duplicate_review(merged_raw)
    page = "__handled__"
else:
    page_renderer = PAGE_RENDERERS.get(page)
    if page_renderer is not None:
        page_renderer(page_context)
        page = "__handled__"
