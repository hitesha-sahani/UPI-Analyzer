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
from modules.pages.common import PageContext, apply_app_theme
from modules.pages.duplicate_review import render_duplicate_review
from modules.ai_advisor import (build_financial_context)
from modules.csv_format_guide import render_csv_guide


def _img_to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

logo_b64 = _img_to_b64("MoneyOS_Logo.png")
# ── Custom CSS ──────────────────────────────────────────────────────────────────
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
    <style>
      .hero-shell {{
        font-family: "DM Sans", sans-serif;
        background: #f7f5f0;
        padding: 0;
      }}
      .hero-brand {{
        display: flex;
        align-items: center;
        gap: 14px;
        margin-bottom: 40px;
      }}
      .hero-brand img {{
        width: 46px;
        border-radius: 8px;
      }}
      .hero-brand-name {{
        font-size: 1.1rem;
        font-weight: 700;
        color: #151515;
      }}
      .hero-brand-sub {{
        font-size: 0.72rem;
        color: #8aa8cd;
        letter-spacing: 0.1em;
        text-transform: uppercase;
      }}
      .hero-layout {{
        display: flex;
        gap: 60px;
        align-items: flex-start;
      }}
      .hero-copy {{
        flex: 1.2;
        min-width: 0;
      }}
      .hero-title {{
        font-size: 3rem;
        font-weight: 800;
        color: #151515;
        line-height: 1.15;
        margin-bottom: 14px;
      }}
      .hero-subtitle {{
        font-size: 1.2rem;
        font-weight: 600;
        color: #86a7cf;
        margin-bottom: 16px;
      }}
      .hero-body {{
        font-size: 0.98rem;
        color: #6c675f;
        line-height: 1.75;
        max-width: 480px;
      }}
      .hero-chips {{
        flex: 1;
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        align-content: flex-start;
        padding-top: 8px;
      }}
      .hero-chip {{
        background: white;
        border: 1px solid #e5ddd0;
        padding: 12px 18px;
        border-radius: 999px;
        font-size: 0.9rem;
        font-weight: 600;
        color: #151515;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
      }}
      @media (max-width: 720px) {{
        .hero-brand {{
          margin-bottom: 24px;
          gap: 12px;
        }}
        .hero-brand img {{
          width: 40px;
        }}
        .hero-brand-name {{
          font-size: 1rem;
        }}
        .hero-brand-sub {{
          font-size: 0.68rem;
        }}
        .hero-layout {{
          flex-direction: column;
          gap: 18px;
        }}
        .hero-title {{
          font-size: 2.15rem;
          line-height: 1.12;
          margin-bottom: 12px;
        }}
        .hero-subtitle {{
          font-size: 1rem;
          margin-bottom: 12px;
        }}
        .hero-body {{
          font-size: 0.92rem;
          line-height: 1.65;
          max-width: none;
        }}
        .hero-chips {{
          gap: 10px;
          padding-top: 0;
        }}
        .hero-chip {{
          padding: 9px 14px;
          font-size: 0.82rem;
        }}
      }}
    </style>
    <div class='hero-shell'>

        <div class='hero-brand'>
            <img src='data:image/png;base64,{logo_b64}' alt='Vitta logo'/>
            <div>
                <div class='hero-brand-name'>Vitt?</div>
                <div class='hero-brand-sub'>Money OS</div>
            </div>
        </div>

        <div class='hero-layout'>

            <div class='hero-copy'>
                <div class='hero-title'>
                    Know your money.<br>Fix the leaks.
                </div>
                <div class='hero-subtitle'>
                    A personal money checkup from your own UPI data.
                </div>
                <div class='hero-body'>
                    Upload a CSV and see what is quietly shaping your month:
                    repeat spends, avoidable leaks, unusual payments, and the
                    habits that deserve a tiny reset. No judgment. Just clarity.
                </div>
            </div>

            <div class='hero-chips'>
                {"".join([
                    f"<div class='hero-chip'>{chip}</div>"
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

    components.html(hero_html, height=420, scrolling=False)

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
        <div style='background:#f4f8fc; border:1px solid #d6e0ec;
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
        color: #7f8ea1 !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.88rem !important;
        font-weight: 500 !important;
        cursor: pointer !important;
        transition: all 0.15s ease !important;
        margin-bottom: 2px !important;
    }
    div[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background: #f3f7fc !important;
        color: #6484ac !important;
        border-left: 3px solid #d7e4f2 !important;
    }
    div[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
        background: #edf4fb !important;
        color: #537098 !important;
        border-left: 3px solid #8daed4 !important;
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
                    letter-spacing:.08em; text-transform:uppercase; color:#8090a5;
                    margin-bottom:8px; padding-left:4px;'>Quick Stats</div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style='background:#f5f9fd; border:1px solid #d7e3f0;
                    border-radius:10px; padding:10px 14px; margin-bottom:8px;
                    border-top: 2px solid #8daed4;'>
            <div style='font-family:"DM Sans",sans-serif; font-size:0.67rem;
                        color:#8090a5; text-transform:uppercase; letter-spacing:0.1em;
                        margin-bottom:2px;'>Total Spent</div>
            <div style='font-family:"Space Mono",monospace; font-size:1.25rem;
                        font-weight:700; color:#1a1a2e;'>₹{stats_sidebar['total_spent']:,.0f}</div>
        </div>
        <div style='background:#f5f9fd; border:1px solid #d7e3f0;
                    border-radius:10px; padding:10px 14px; margin-bottom:8px;
                    border-top: 2px solid #a9c2df;'>
            <div style='font-family:"DM Sans",sans-serif; font-size:0.67rem;
                        color:#8090a5; text-transform:uppercase; letter-spacing:0.1em;
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

apply_app_theme()


# HEADER (always shown)
date_start = stats["date_range_start"].strftime("%d %b %Y") if pd.notna(stats["date_range_start"]) else "-"
date_end = stats["date_range_end"].strftime("%d %b %Y") if pd.notna(stats["date_range_end"]) else "-"
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
