import pandas as pd
import streamlit as st

from modules.deduplicator import get_dedup_report, get_duplicate_pairs


def _inject_light_theme() -> None:
    st.markdown("""
    <style>
    .stApp {
        background: #f7f5f0 !important;
        color: #151515 !important;
    }
    .block-container {
        background: #f7f5f0 !important;
    }
    .kpi-card {
        background: #ffffff !important;
        border: 1px solid #ded9cf !important;
        border-radius: 8px !important;
        box-shadow: 0 1px 2px rgba(20,20,20,0.04) !important;
    }
    .kpi-card::before {
        content: none !important;
    }
    .kpi-card:hover {
        transform: none !important;
        box-shadow: 0 1px 2px rgba(20,20,20,0.04) !important;
    }
    .kpi-value {
        color: #151515 !important;
        font-family: "DM Sans", sans-serif !important;
    }
    .kpi-label {
        color: #6c675f !important;
        letter-spacing: 0 !important;
        text-transform: none !important;
    }
    .section-header {
        color: #151515 !important;
        border-bottom: 1px solid #ded9cf !important;
        letter-spacing: 0 !important;
    }
    .section-header::after {
        background: #1769ff !important;
        width: 28px !important;
    }
    div[data-testid="stDataFrame"] {
        background: #ffffff !important;
        border: 1px solid #ded9cf !important;
        border-radius: 8px !important;
    }
    div, p, span, label, h1, h2, h3, h4, h5, h6,
    [data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] {
        color: #151515;
    }
    </style>
    """, unsafe_allow_html=True)


def _money(value) -> str:
    return f"₹{value:,.0f}"


def _transaction_row(row: dict) -> pd.DataFrame:
    return pd.DataFrame([{
        "Date": pd.to_datetime(row["date"]).strftime("%d %b %Y"),
        "Description": row["description"],
        "Amount": _money(row["amount"]),
        "Source": row["source"],
    }])


def _render_kpis(merged_raw: pd.DataFrame, dedup_report: dict) -> None:
    d1, d2, d3, d4 = st.columns(4)
    for col, label, val, color in [
        (d1, "Accounts merged", len(dedup_report["sources"]), "#1769ff"),
        (d2, "Total transactions", len(merged_raw), "#151515"),
        (d3, "Flagged for review", dedup_report["total_duplicates"], "#FF9F43"),
        (d4, "Confirmed removed", _money(dedup_report["amount_deduplicated"]), "#6BCB77"),
    ]:
        with col:
            st.markdown(f"""
            <div class='kpi-card'>
                <div class='kpi-value' style='color:{color}; font-size:1.4rem;'>{val}</div>
                <div class='kpi-label'>{label}</div>
            </div>
            """, unsafe_allow_html=True)


def _render_sources(merged_raw: pd.DataFrame) -> None:
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
                {sr['transactions']} txns &nbsp;·&nbsp; {_money(sr['debit_amount'])} spent
            </span>
        </div>
        """, unsafe_allow_html=True)


def _render_duplicate_summary(dedup_report: dict) -> None:
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


def _render_candidate_table(dedup_report: dict, duplicate_pairs: list) -> None:
    if not duplicate_pairs:
        st.success("✅ No duplicate transactions found across your accounts!")
        return

    st.markdown("<div class='section-header'>Detected Duplicate Candidates</div>", unsafe_allow_html=True)
    dup_display = dedup_report["review_rows"].copy()
    dup_display["date"] = pd.to_datetime(dup_display["date"]).dt.strftime("%d %b %Y")
    dup_display["amount"] = dup_display["amount"].apply(_money)
    dup_display.columns = ["Date", "Description", "Amount", "Source", "Reason", "Decision"]
    st.dataframe(dup_display, use_container_width=True, hide_index=True)


def _render_pair_review(duplicate_pairs: list) -> None:
    st.markdown("<div class='section-header'>Review Duplicate Pairs</div>", unsafe_allow_html=True)

    if duplicate_pairs:
        st.caption("Pending rows stay in analytics until you explicitly remove them.")

    for pair in duplicate_pairs:
        pair_id = str(pair["pair_id"])
        original = pair["original"]
        duplicate = pair["duplicate"]
        previous_decision = st.session_state.manual_duplicate_decisions.get(pair_id)
        current_decision = previous_decision or "Pending"

        st.markdown(f"#### {pair_id}")

        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("**Original Transaction**")
            st.dataframe(_transaction_row(original), use_container_width=True, hide_index=True)

        with c2:
            st.markdown("**Flagged Transaction**")
            st.dataframe(_transaction_row(duplicate), use_container_width=True, hide_index=True)

        default_index = {
            "Pending": 0,
            "Duplicate": 1,
            "Keep": 2,
        }.get(current_decision, 0)
        choice = st.radio(
            f"Decision for {pair_id}",
            ["Pending review", "Remove duplicate", "Keep both"],
            index=default_index,
            horizontal=True,
            key=f"dup_action_{pair_id}",
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


def _render_explainer() -> None:
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

        The transaction with the richer description is shown as the original.
        You decide whether the flagged row is removed from analytics.
        """)


def render_duplicate_review(merged_raw: pd.DataFrame | None) -> None:
    _inject_light_theme()

    st.markdown("<div class='section-header'>Account Deduplication</div>", unsafe_allow_html=True)
    st.markdown(
        "<small style='color:#6c675f;'>Detects duplicate transactions across multiple "
        "UPI apps — so your spend totals aren't double-counted.</small>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    if merged_raw is None:
        st.info("Upload your primary CSV, then add extra account CSVs using 'Add more accounts' in the sidebar.")
        return

    dedup_report = get_dedup_report(merged_raw)
    duplicate_pairs = get_duplicate_pairs(merged_raw)

    _render_kpis(merged_raw, dedup_report)
    st.markdown("<br>", unsafe_allow_html=True)
    _render_sources(merged_raw)
    st.markdown("<br>", unsafe_allow_html=True)
    _render_duplicate_summary(dedup_report)
    st.markdown("<br>", unsafe_allow_html=True)
    _render_candidate_table(dedup_report, duplicate_pairs)
    st.markdown("<br>", unsafe_allow_html=True)
    _render_pair_review(duplicate_pairs)
    _render_explainer()
