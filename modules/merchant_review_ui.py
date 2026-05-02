"""
modules/merchant_review_ui.py
─────────────────────────────
Uses upi_id as the display key — it's the actual payee identifier
(e.g. rahul@okaxis, zomato@icici, paytm-12345@paytm).

Falls back to description only when upi_id is missing/N/A.

This avoids two problems:
  - description groups all Paytm transactions under one entry
  - merchant column misidentifies e.g. TANVI as Vi (Vodafone)
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from modules.user_overrides import get_user_map, save_bulk


def _get_all_categories() -> list[str]:
    try:
        from modules.categorizer import CATEGORIES as CAT_CONFIG
        cats = list(CAT_CONFIG.keys())
        priority = [
            "Food & Dining", "Groceries", "Transport", "Shopping",
            "Subscriptions", "Bills & Utilities", "Health & Medical",
            "Education", "Housing & Rent", "Finance & Investment",
            "Travel & Stays", "Entertainment", "P2P Transfers",
            "Personal Care", "Home & Maintenance", "Charity & Donations",
            "Others",
        ]
        ordered = [c for c in priority if c in cats]
        ordered += [c for c in cats if c not in ordered]
        return ordered
    except Exception:
        return [
            "Food & Dining", "Groceries", "Transport", "Shopping",
            "Subscriptions", "Bills & Utilities", "Health & Medical",
            "Education", "Housing & Rent", "Finance & Investment",
            "Travel & Stays", "Entertainment", "P2P Transfers",
            "Personal Care", "Home & Maintenance", "Charity & Donations",
            "Others",
        ]


_SOURCE_STYLE = {
    "override": ("🟣", "#A29BFE", "Your rule"),
    "global":   ("🟢", "#55EFC4", "Auto-matched"),
    "fallback": ("🟡", "#FFEAA7", "Fallback"),
}

def _source_tag(key, current_category, user_map):
    if key in user_map:
        return _SOURCE_STYLE["override"]
    if current_category != "Others":
        return _SOURCE_STYLE["global"]
    return _SOURCE_STYLE["fallback"]


def _display_key(row) -> str:
    """
    Use upi_id only when it looks like a real UPI handle (contains @).
    Reference/txn numbers like S58931978 are rejected and we fall back
    to description instead.
    """
    uid = str(row.get("upi_id", "")).strip()
    if uid and "@" in uid:
        return uid
    return str(row.get("description", "")).strip()


def render_merchant_review(df, user_id, *, load_and_process_fn=None, key="merchant_review"):
    ALL_CATEGORIES = _get_all_categories()
    user_map       = get_user_map(user_id)

    debits = df[df["type"] == "Debit"].copy()
    if debits.empty:
        st.info("No debit transactions found to review.")
        return

    # Build a display_key column: upi_id if present, else description
    debits["_key"] = debits.apply(_display_key, axis=1)

    # Count, dedup, sort by frequency desc
    txn_counts = debits.groupby("_key").size().rename("txn_count")
    unique = (
        debits[["_key", "category"]]
        .drop_duplicates(subset="_key", keep="first")
        .join(txn_counts, on="_key")
        .sort_values("txn_count", ascending=False)
        .reset_index(drop=True)
    )

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>🏪 Review Merchant Categories</div>",
                unsafe_allow_html=True)
    st.markdown(
        f"<small style='color:#8A8AB0'>Found "
        f"<b style='color:#E0E0F0'>{len(unique)}</b> unique payees — "
        f"sorted by frequency. Fix wrong categories; rules apply to all future uploads.</small>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Search ────────────────────────────────────────────────────────────────
    search = st.text_input("search", placeholder="🔍  Search by UPI ID or description…",
                           key=f"{key}_search", label_visibility="collapsed")

    display_df = unique.copy()
    if search.strip():
        display_df = display_df[
            display_df["_key"].str.contains(search.strip(), case=False, na=False)
        ].reset_index(drop=True)

    if display_df.empty:
        st.warning("No payees match that search.")
        return

    # ── Form ──────────────────────────────────────────────────────────────────
    with st.form(key=f"{key}_form"):
        h1, h2, h3, h4 = st.columns([4, 3, 1.6, 0.8])
        for col, lbl in zip([h1, h2, h3, h4],
                            ["UPI ID / Description", "Category", "Source", "Txns"]):
            col.markdown(
                f"<small style='color:#8A8AB0; text-transform:uppercase; "
                f"letter-spacing:.06em;'>{lbl}</small>",
                unsafe_allow_html=True,
            )
        st.markdown(
            "<div style='border-bottom:1px solid rgba(108,99,255,0.15);"
            " margin:4px 0 8px;'></div>",
            unsafe_allow_html=True,
        )

        new_mapping: dict[str, str] = {}

        for idx, row in display_df.iterrows():
            raw_key      = str(row["_key"])
            current_cat  = row["category"]
            lookup_key   = raw_key.lower()
            count        = int(row.get("txn_count", 0))

            c1, c2, c3, c4 = st.columns([4, 3, 1.6, 0.8])

            c1.markdown(
                f"<div style='padding-top:5px; font-family:\"Space Mono\",monospace; "
                f"font-size:0.76rem; color:#C8C8E8; word-break:break-all;'>"
                f"{raw_key}</div>",
                unsafe_allow_html=True,
            )

            try:
                default_idx = ALL_CATEGORIES.index(current_cat)
            except ValueError:
                default_idx = ALL_CATEGORIES.index("Others")

            chosen = c2.selectbox(
                label=f"cat_{idx}", options=ALL_CATEGORIES, index=default_idx,
                key=f"{key}_{idx}_{lookup_key[:30]}", label_visibility="collapsed",
            )
            new_mapping[lookup_key] = chosen

            emoji, colour, badge_label = _source_tag(lookup_key, current_cat, user_map)
            c3.markdown(
                f"<div style='padding-top:5px; font-size:0.75rem; color:{colour};'>"
                f"{emoji} {badge_label}</div>",
                unsafe_allow_html=True,
            )

            c4.markdown(
                f"<div style='margin-top:4px; font-size:0.8rem; font-weight:700; "
                f"color:#6C63FF; text-align:center; background:rgba(108,99,255,0.13); "
                f"border-radius:10px; padding:3px 0;'>{count}</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button(
            f"💾  Save {len(new_mapping)} rules",
            use_container_width=True, type="primary",
        )

    if submitted:
        save_bulk(user_id, new_mapping)
        if load_and_process_fn is not None:
            load_and_process_fn.clear()
        st.success(f"✅  Saved {len(new_mapping)} rules. Refreshing…")
        st.rerun()