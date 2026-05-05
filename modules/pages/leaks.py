from __future__ import annotations

import streamlit as st

from modules.pages.common import PageContext, format_inr


def render(context: PageContext) -> None:
    st.markdown("<div class='section-header'>Silent leaks</div>", unsafe_allow_html=True)
    if context.leak_cards:
        for card in context.leak_cards:
            st.markdown(
                f"""
                <div class='leak-card'>
                    <div class='micro-label'>{card['title']}</div>
                    <div class='amount-line'>{format_inr(card['amount'])}</div>
                    <div class='card-detail'>{card['detail']}<br><b>Action:</b> {card['action']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.success("No strong leak signals found in this statement.")

    st.markdown("<div class='section-header'>Detected recurring payments</div>", unsafe_allow_html=True)
    subscriptions = context.insights["subscriptions"].copy()
    if not subscriptions.empty:
        subscriptions["monthly_cost"] = subscriptions["monthly_cost"].apply(format_inr)
        subscriptions["annual_projection"] = subscriptions["annual_projection"].apply(format_inr)
        st.dataframe(
            subscriptions.rename(
                columns={
                    "merchant": "Merchant",
                    "monthly_cost": "Monthly",
                    "months_active": "Months active",
                    "annual_projection": "Annual run-rate",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No recurring subscription pattern detected.")
