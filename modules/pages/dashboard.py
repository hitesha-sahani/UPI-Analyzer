from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from modules.pages.common import PageContext, format_inr


SPEND_SPLIT_COLORS = ["#dce8f5", "#c9dbef", "#b7cfe8", "#a8c4e2", "#97b8d9", "#86abd0"]


def render(context: PageContext) -> None:
    score_col, action_col = st.columns([0.9, 1.4])

    with score_col:
        st.markdown(
            f"""
            <div class='money-card'>
                <div class='micro-label'>Money wellness score</div>
                <div class='money-score'>{context.money_score['score']}</div>
                <div class='card-title'>{context.money_score['label']}</div>
                <div class='card-detail'>{context.money_score['summary']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with action_col:
        st.markdown(
            f"""
            <div class='action-card'>
                <div class='micro-label'>Best next action</div>
                <div class='card-title'>{context.next_action}</div>
                <div class='card-detail'>Chosen from recurring charges, food spend, BNPL exposure, savings rate, and high-signal transactions.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        a, b, c = st.columns(3)
        for col, label, value in [
            (a, "Spent", format_inr(context.stats["total_spent"])),
            (b, "Saved", format_inr(context.insights["savings_rate"]["savings"])),
            (c, "Savings rate", f"{context.insights['savings_rate']['rate']}%"),
        ]:
            with col:
                st.markdown(
                    f"""
                    <div class='kpi-card'>
                        <div class='kpi-value'>{value}</div>
                        <div class='kpi-label'>{label}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.markdown("<div class='section-header'>What matters this month</div>", unsafe_allow_html=True)
    insight_cols = st.columns(3)
    top_cat = context.cat_summary.iloc[0] if not context.cat_summary.empty else None
    insight_items = [
        (
            "Top spend area",
            format_inr(top_cat["total_spent"]) if top_cat is not None else "No spend",
            (
                f"{top_cat['category']} is {top_cat['percentage']}% of debit spend."
                if top_cat is not None
                else "Upload data to see your spend pattern."
            ),
        ),
        (
            "Silent leaks",
            format_inr(sum(card["amount"] for card in context.leak_cards[:3])),
            f"{len(context.leak_cards)} leak signals found across subscriptions, food, BNPL, and unusual payments.",
        ),
        (
            "Risk checks",
            str(context.anomaly_info["high_severity"]),
            "Transactions flagged for unusual amount, duplicate charges, or suspicious patterns.",
        ),
    ]
    for col, (title, amount, detail) in zip(insight_cols, insight_items):
        with col:
            st.markdown(
                f"""
                <div class='insight-card'>
                    <div class='micro-label'>{title}</div>
                    <div class='amount-line'>{amount}</div>
                    <div class='card-detail'>{detail}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div class='section-header'>Money story</div>", unsafe_allow_html=True)
    story_left, story_right = st.columns([1.2, 1])
    monthly = context.insights["monthly_trend"].copy()
    recent_month = monthly.iloc[-1] if not monthly.empty else None
    previous_month = monthly.iloc[-2] if len(monthly) > 1 else None

    with story_left:
        if recent_month is not None:
            change_text = "No previous month to compare yet."
            if previous_month is not None:
                diff = recent_month["total_spent"] - previous_month["total_spent"]
                direction = "higher" if diff > 0 else "lower"
                change_text = (
                    f"{recent_month['month']} was {format_inr(abs(diff))} "
                    f"{direction} than {previous_month['month']}."
                )
            st.markdown(
                f"""
                <div class='insight-card'>
                    <div class='micro-label'>This period in plain English</div>
                    <div class='card-title'>You spent {format_inr(context.stats['total_spent'])} across {context.stats['total_transactions']} transactions.</div>
                    <div class='card-detail'>{change_text} Your average debit transaction is {format_inr(context.stats['avg_transaction'])}, and your daily burn is {format_inr(context.insights['spend_velocity']['avg_daily'])}.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with story_right:
        top_merch = context.top_merchants.head(4).copy()
        rows = "".join(
            f"<tr><td>{row['merchant']}</td><td>{format_inr(row['total_spent'])}</td></tr>"
            for _, row in top_merch.iterrows()
        )
        st.markdown(
            f"""
            <div class='insight-card'>
                <div class='micro-label'>Top merchants</div>
                <table class='mini-table'>{rows}</table>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div class='section-header'>Spend split</div>", unsafe_allow_html=True)
    chart_col, table_col = st.columns([1.25, 1])
    top_categories = context.cat_summary.head(6).sort_values("total_spent", ascending=True)
    fig = go.Figure(
        go.Bar(
            y=top_categories["category"],
            x=top_categories["total_spent"],
            orientation="h",
            marker=dict(
                color=SPEND_SPLIT_COLORS[-len(top_categories):],
                line=dict(color="#b7c8da", width=1),
            ),
            text=[format_inr(value) for value in top_categories["total_spent"]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>₹%{x:,.0f}<extra></extra>",
        )
    )
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
        cat_table = context.cat_summary[
            ["category", "total_spent", "transaction_count", "percentage"]
        ].head(8).copy()
        cat_table["total_spent"] = cat_table["total_spent"].apply(format_inr)
        cat_table["percentage"] = cat_table["percentage"].apply(lambda value: f"{value}%")
        cat_table.columns = ["Category", "Spent", "Txns", "Share"]
        st.dataframe(cat_table, use_container_width=True, hide_index=True, height=318)

    st.markdown("<div class='section-header'>Recent transaction trail</div>", unsafe_allow_html=True)
    recent = context.df.sort_values("date", ascending=False).head(8)[
        ["date", "merchant", "category", "amount", "type", "anomaly_severity"]
    ].copy()
    recent["date"] = recent["date"].dt.strftime("%d %b")
    recent["amount"] = recent["amount"].apply(format_inr)
    recent.columns = ["Date", "Merchant", "Category", "Amount", "Type", "Signal"]
    st.dataframe(recent, use_container_width=True, hide_index=True, height=300)

    st.markdown("<div class='section-header'>Learn from your own money</div>", unsafe_allow_html=True)
    lcols = st.columns(2)
    for index, card in enumerate(context.learning_cards[:4]):
        with lcols[index % 2]:
            st.markdown(
                f"""
                <div class='insight-card'>
                    <div class='micro-label'>{card['title']}</div>
                    <div class='card-detail'>{card['lesson']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
