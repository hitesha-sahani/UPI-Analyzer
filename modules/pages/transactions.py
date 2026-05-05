from __future__ import annotations

import streamlit as st

from modules.pages.common import PageContext, format_inr


def render(context: PageContext) -> None:
    st.markdown("<div class='section-header'>Transactions</div>", unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns([1, 1, 2])
    with fc1:
        sel_cat = st.selectbox("Category", ["All"] + sorted(context.df["category"].unique().tolist()))
    with fc2:
        sel_type = st.selectbox("Type", ["All", "Debit", "Credit"])
    with fc3:
        search = st.text_input("Search", placeholder="Merchant or description")

    filtered_df = context.df.copy()
    if sel_cat != "All":
        filtered_df = filtered_df[filtered_df["category"] == sel_cat]
    if sel_type != "All":
        filtered_df = filtered_df[filtered_df["type"] == sel_type]
    if search:
        filtered_df = filtered_df[
            filtered_df["description"].str.contains(search, case=False, na=False)
        ]

    display = filtered_df[
        ["date", "description", "merchant", "category", "amount", "type", "anomaly_severity"]
    ].copy()
    display["date"] = display["date"].dt.strftime("%d %b %Y")
    display["amount"] = display["amount"].apply(format_inr)
    display.columns = ["Date", "Description", "Merchant", "Category", "Amount", "Type", "Signal"]
    st.dataframe(display, use_container_width=True, hide_index=True, height=520)
