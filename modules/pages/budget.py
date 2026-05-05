from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from modules.budget_tracker import (
    ALL_CATEGORIES,
    DEFAULT_BUDGETS,
    compute_budget_status,
    compute_monthly_overview,
    get_budget_alerts,
)
from modules.pages.common import PageContext


def render(context: PageContext) -> None:
    st.markdown("<div class='section-header'>Budget Tracker</div>", unsafe_allow_html=True)
    st.markdown(
        "<small style='color:#6c675f;'>Set your monthly budget. Spend is pulled automatically from your statement.</small>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    if "budgets" not in st.session_state:
        st.session_state.budgets = {
            key: {"amount": value["amount"], "period": value["period"]}
            for key, value in DEFAULT_BUDGETS.items()
        }
    if "monthly_budget" not in st.session_state:
        st.session_state.monthly_budget = 50000.0

    st.markdown(
        """
        <div style='font-family:"DM Sans",sans-serif; font-weight:700;
                    font-size:1rem; color:#151515; margin-bottom:8px;'>
            What's your total monthly spending budget?
        </div>
        """,
        unsafe_allow_html=True,
    )

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

    if monthly_budget > 0:
        st.markdown("<div class='section-header'>Monthly Overview</div>", unsafe_allow_html=True)
        monthly_overview = compute_monthly_overview(context.df, monthly_budget)
        rows = [monthly_overview.iloc[index : index + 6] for index in range(0, len(monthly_overview), 6)]

        for chunk in rows:
            month_cols = st.columns(len(chunk))
            for index, (_, month_row) in enumerate(chunk.iterrows()):
                with month_cols[index]:
                    pct = min(month_row["pct_used"], 100)
                    color = month_row["color"]
                    st.markdown(
                        f"""
                        <div style='background:#ffffff; border:2px solid {color}; border-radius:12px;
                                    padding:16px 10px; text-align:center;'>
                            <div style='font-family:"DM Sans",sans-serif; font-size:0.72rem;
                                        color:#6c675f; text-transform:uppercase; letter-spacing:0.06em;'>
                                {month_row["month"]}
                            </div>
                            <div style='font-family:"DM Sans",sans-serif; font-weight:800;
                                        font-size:1.4rem; color:{color}; margin:6px 0;'>
                                {pct:.0f}%
                            </div>
                            <div style='font-size:0.75rem; color:#151515; font-family:"DM Sans",sans-serif;'>
                                ₹{month_row["spent"]:,.0f}
                            </div>
                            <div style='font-size:0.7rem; color:#6c675f; margin-top:2px;'>
                                of ₹{month_row["budget"]:,.0f}
                            </div>
                            <div style='background:#f7f5f0; border-radius:99px; height:4px; margin-top:8px;'>
                                <div style='width:{pct}%; height:4px; background:{color}; border-radius:99px;'></div>
                            </div>
                            <div style='font-size:0.68rem; color:{color}; font-weight:600;
                                        font-family:"DM Sans",sans-serif; margin-top:6px;'>
                                {month_row["status"]}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

    available_months = sorted(
        context.df[context.df["type"] == "Debit"]["month"].unique().tolist(),
        reverse=True,
    )
    st.markdown("<div class='section-header'>Category Breakdown</div>", unsafe_allow_html=True)

    sel_col, _ = st.columns([1, 2])
    with sel_col:
        selected_month = st.selectbox("Select month", available_months, index=0)

    st.markdown("<br>", unsafe_allow_html=True)

    budget_status = compute_budget_status(
        context.df,
        st.session_state.budgets,
        selected_month=selected_month,
        monthly_budget=monthly_budget,
    )
    alerts = get_budget_alerts(budget_status)

    total_spent = budget_status["spent"].sum()
    total_budget = budget_status["monthly_budget"].sum()
    over_count = int((budget_status["status"] == "Over Budget").sum())

    k1, k2, k3, k4 = st.columns(4)
    for col, label, value, color in [
        (k1, "Total budgeted", f"₹{total_budget:,.0f}", "#151515"),
        (k2, "Total spent", f"₹{total_spent:,.0f}", "#FF6B6B"),
        (k3, "Remaining", f"₹{max(total_budget - total_spent, 0):,.0f}", "#1769ff"),
        (k4, "Categories over limit", str(over_count), "#FF9F43"),
    ]:
        with col:
            st.markdown(
                f"""
                <div class='kpi-card'>
                    <div class='kpi-value' style='color:{color}; font-size:1.35rem;'>{value}</div>
                    <div class='kpi-label'>{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    if alerts:
        st.markdown("<div class='section-header'>Alerts</div>", unsafe_allow_html=True)
        for severity, category, message in alerts:
            color = "#FF6B6B" if "Over" in severity else "#FF9F43" if "Breach" in severity else "#FFD93D"
            st.markdown(
                f"""
                <div class='nudge-card' style='border-left-color:{color};'>
                    <b style='color:{color};'>{severity} - {category}</b><br>
                    <span style='font-size:0.85rem; color:#6c675f;'>{message}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("<br>", unsafe_allow_html=True)

    view_mode = st.radio(
        "Display as",
        ["Progress bars", "Gauge cards"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if view_mode == "Progress bars":
        _render_progress_bars(budget_status)
    else:
        _render_gauge_cards(budget_status)

    st.markdown("<br>", unsafe_allow_html=True)
    _render_budget_editor()
    st.markdown("<br>", unsafe_allow_html=True)
    _render_budget_chart(budget_status)


def _render_progress_bars(budget_status) -> None:
    for _, row in budget_status.iterrows():
        if row["monthly_budget"] == 0 and row["spent"] == 0:
            continue
        pct = min(row["pct_used"], 100)
        color = row["color"]
        period = row["budget_period"].lower()
        projected = (
            f" · Projected ₹{row['projected_eom']:,.0f}"
            if row["will_breach"] and row["days_remaining"] > 0
            else ""
        )

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

        st.markdown(
            f"""
            <div style='background:#f7f5f0; border-radius:99px; height:7px;
                        margin-bottom:4px; overflow:hidden;'>
                <div style='width:{pct}%; height:7px; background:{color}; border-radius:99px;'></div>
            </div>
            <div style='font-size:0.72rem; color:#6c675f; margin-bottom:16px;'>
                {row['pct_used']:.0f}% used &nbsp;·&nbsp;
                Budget ₹{row['budget_amount']:,.0f}/{period} &nbsp;·&nbsp;
                ₹{row['daily_burn']:,.0f}/day{projected}
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_gauge_cards(budget_status) -> None:
    rows_data = budget_status.to_dict("records")
    for index in range(0, len(rows_data), 3):
        chunk = rows_data[index : index + 3]
        cols = st.columns(3)
        for col_index, row in enumerate(chunk):
            color = row["color"]
            pct = min(row["pct_used"], 100)
            radius, cx, cy = 36, 44, 44
            circumference = 2 * 3.14159 * radius
            dash = circumference * (pct / 100)
            gap = circumference - dash
            period = row["budget_period"].lower()

            with cols[col_index]:
                st.markdown(
                    f"""
                    <div style='background:#ffffff; border:1px solid #ede8e0;
                                border-radius:12px; padding:16px;
                                text-align:center; margin-bottom:12px;'>
                        <svg width="88" height="88" viewBox="0 0 88 88">
                            <circle cx="{cx}" cy="{cy}" r="{radius}"
                                fill="none" stroke="#f7f5f0" stroke-width="8"/>
                            <circle cx="{cx}" cy="{cy}" r="{radius}"
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
                            Budget ₹{row["budget_amount"]:,.0f}/{period}
                        </div>
                        <div style='font-size:0.72rem; font-weight:600; color:{color};
                                    margin-top:4px;'>{row["status"]}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def _render_budget_editor() -> None:
    with st.expander("Edit category budgets", expanded=False):
        st.markdown(
            "<small style='color:#6c675f;'>Set amount and period per category. Leave at 0 to skip a category.</small>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

        new_budgets = {}
        for index in range(0, len(ALL_CATEGORIES), 2):
            pair = ALL_CATEGORIES[index : index + 2]
            cols = st.columns(4)
            for pair_index, category in enumerate(pair):
                current = st.session_state.budgets.get(
                    category,
                    DEFAULT_BUDGETS.get(category, {"amount": 0, "period": "Monthly"}),
                )
                with cols[pair_index * 2]:
                    amount = st.number_input(
                        category,
                        min_value=0,
                        max_value=10_00_000,
                        value=int(current.get("amount", 0)),
                        step=100,
                        key=f"bamt_{category}",
                    )
                with cols[pair_index * 2 + 1]:
                    period = st.selectbox(
                        "Period",
                        ["Daily", "Weekly", "Monthly", "Yearly"],
                        index=["Daily", "Weekly", "Monthly", "Yearly"].index(
                            current.get("period", "Monthly")
                        ),
                        key=f"bper_{category}",
                        label_visibility="collapsed",
                    )
                new_budgets[category] = {"amount": float(amount), "period": period}

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Save category budgets", type="primary"):
            st.session_state.budgets = new_budgets
            st.success("Saved!")
            st.rerun()


def _render_budget_chart(budget_status) -> None:
    st.markdown("<div class='section-header'>Spend vs Budget - Category Chart</div>", unsafe_allow_html=True)

    valid = budget_status[budget_status["monthly_budget"] > 0]
    if valid.empty:
        return

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Spent",
            x=valid["category"],
            y=valid["spent"],
            marker_color="#1769ff",
            opacity=0.9,
        )
    )
    fig.add_trace(
        go.Bar(
            name="Projected month end",
            x=valid["category"],
            y=valid["projected_eom"],
            marker_color="#FF9F43",
            opacity=0.45,
        )
    )
    fig.add_trace(
        go.Scatter(
            name="Budget limit",
            x=valid["category"],
            y=valid["monthly_budget"],
            mode="markers",
            marker=dict(
                symbol="line-ew",
                size=20,
                color="#FF6B6B",
                line=dict(width=2, color="#FF6B6B"),
            ),
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#151515"),
        barmode="overlay",
        xaxis=dict(showgrid=False, tickangle=-30, tickfont=dict(size=10)),
        yaxis=dict(showgrid=True, gridcolor="#ede8e0", title="₹"),
        legend=dict(orientation="h", y=1.12),
        margin=dict(l=20, r=20, t=40, b=90),
        height=360,
    )
    st.plotly_chart(fig, use_container_width=True)
