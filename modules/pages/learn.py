from __future__ import annotations

import streamlit as st

from modules.pages.common import PageContext, format_inr


def render(context: PageContext) -> None:
    st.markdown("<div class='section-header'>Money lessons from your transactions</div>", unsafe_allow_html=True)
    for card in context.learning_cards:
        st.markdown(
            f"""
            <div class='insight-card'>
                <div class='micro-label'>{card['title']}</div>
                <div class='card-detail'>{card['lesson']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div class='section-header'>Category lessons</div>", unsafe_allow_html=True)
    for _, row in context.cat_summary.head(6).iterrows():
        monthly_avg = row["total_spent"] / max(context.stats["months_covered"], 1)
        st.markdown(
            f"""
            <div class='leak-card'>
                <div class='micro-label'>{row['category']}</div>
                <div class='amount-line'>{format_inr(monthly_avg)}/month</div>
                <div class='card-detail'>{row['transaction_count']} transactions, {row['percentage']}% of spending. Ask whether this category is a need, a lifestyle choice, or a leak.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
