

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from typing import Optional

# ── Theme ───────────────────────────────────────────────────────────────────────
THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="'DM Sans', sans-serif", color="#E0E0E0"),
    margin=dict(l=20, r=20, t=40, b=20),
)

GRID_STYLE = dict(
    showgrid=True,
    gridcolor="rgba(255,255,255,0.07)",
    zeroline=False,
    showline=False,
)

def _fmt_inr(amount: float) -> str:
    if amount >= 1_00_000:
        return f"₹{amount/1_00_000:.1f}L"
    elif amount >= 1000:
        return f"₹{amount/1000:.1f}K"
    return f"₹{amount:,.0f}"


# ── 1. Category Donut Chart ─────────────────────────────────────────────────────
def category_donut(category_summary: pd.DataFrame) -> go.Figure:
    df = category_summary[category_summary["category"] != "Income"]

    fig = go.Figure(go.Pie(
        labels=df["category"],
        values=df["total_spent"],
        hole=0.62,
        textinfo="percent",
        textfont_size=11,
        marker=dict(colors=df["color"].tolist(), line=dict(color="#1a1a2e", width=2)),
        hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<br>%{percent}<extra></extra>",
    ))

    fig.update_layout(
        **THEME,
        showlegend=True,
        legend=dict(
            orientation="v",
            x=1.02, y=0.5,
            font=dict(size=11),
        ),
        annotations=[dict(
            text="Spend<br>Split",
            x=0.5, y=0.5,
            font=dict(size=14, color="#A0A0B0"),
            showarrow=False,
        )],
        height=380,
    )
    return fig


# ── 2. Monthly Trend Bar + Line ─────────────────────────────────────────────────
def monthly_trend_chart(monthly: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=monthly["month"],
        y=monthly["total_spent"],
        name="Total Spend",
        marker_color="#6C63FF",
        opacity=0.85,
        hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>",
    ))

    # MoM change line (secondary axis)
    if "mom_change" in monthly.columns:
        colors = ["#FF6B6B" if v > 0 else "#4ECDC4" for v in monthly["mom_change"].fillna(0)]
        fig.add_trace(go.Scatter(
            x=monthly["month"],
            y=monthly["mom_change"],
            name="MoM Δ",
            mode="lines+markers",
            yaxis="y2",
            line=dict(color="#FFD93D", width=2, dash="dot"),
            marker=dict(color=colors, size=7),
            hovertemplate="%{x}<br>Change: ₹%{y:+,.0f}<extra></extra>",
        ))

    fig.update_layout(
        **THEME,
        yaxis=dict(**GRID_STYLE, title="Amount (₹)"),
        yaxis2=dict(overlaying="y", side="right", title="MoM Change", showgrid=False),
        xaxis=dict(**GRID_STYLE),
        legend=dict(orientation="h", y=1.1),
        height=360,
        barmode="group",
    )
    return fig


# ── 3. Day-of-Week Heatmap ──────────────────────────────────────────────────────
def dayofweek_bar(dayofweek: pd.DataFrame) -> go.Figure:
    colors = ["#4ECDC4" if d in ["Saturday", "Sunday"] else "#6C63FF"
              for d in dayofweek["day_of_week"].astype(str)]

    fig = go.Figure(go.Bar(
        x=dayofweek["day_of_week"].astype(str),
        y=dayofweek["avg"],
        marker_color=colors,
        text=[_fmt_inr(v) for v in dayofweek["avg"]],
        textposition="outside",
        textfont=dict(size=10),
        hovertemplate="%{x}<br>Avg: ₹%{y:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        **THEME,
        yaxis=dict(**GRID_STYLE, title="Avg Spend (₹)"),
        xaxis=dict(showgrid=False),
        height=300,
        showlegend=False,
    )
    return fig


# ── 4. Top Merchants Horizontal Bar ────────────────────────────────────────────
def top_merchants_chart(merchants: pd.DataFrame) -> go.Figure:
    df = merchants.sort_values("total_spent")

    fig = go.Figure(go.Bar(
        y=df["merchant"],
        x=df["total_spent"],
        orientation="h",
        marker=dict(
            color=df["total_spent"],
            colorscale=[[0, "#2D2D54"], [0.5, "#6C63FF"], [1, "#FF6B6B"]],
            showscale=False,
        ),
        text=[_fmt_inr(v) for v in df["total_spent"]],
        textposition="outside",
        textfont=dict(size=10),
        hovertemplate="<b>%{y}</b><br>₹%{x:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        **THEME,
        xaxis=dict(**GRID_STYLE, title="Total Spent (₹)"),
        yaxis=dict(showgrid=False),
        height=max(300, len(df) * 36),
    )
    return fig


# ── 5. Spend Heatmap (Day × Week) ──────────────────────────────────────────────
def spend_calendar_heatmap(df: pd.DataFrame) -> go.Figure:
    debits = df[df["type"] == "Debit"].copy()
    debits["date_only"] = debits["date"].dt.date

    daily = debits.groupby("date_only")["amount"].sum().reset_index()
    daily["date_dt"] = pd.to_datetime(daily["date_only"])
    daily["weekday"] = daily["date_dt"].dt.day_name()
    daily["week_num"] = daily["date_dt"].dt.isocalendar().week.astype(str)

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    pivot = daily.pivot_table(index="weekday", columns="week_num", values="amount", aggfunc="sum")
    pivot = pivot.reindex(day_order)

    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale=[[0, "#1a1a2e"], [0.5, "#6C63FF"], [1, "#FF6B6B"]],
        hovertemplate="Week %{x} | %{y}<br>₹%{z:,.0f}<extra></extra>",
        showscale=True,
    ))

    fig.update_layout(
        **THEME,
        xaxis=dict(title="Week Number", showgrid=False),
        yaxis=dict(showgrid=False),
        height=280,
    )
    return fig


# ── 6. Anomaly Scatter Plot ─────────────────────────────────────────────────────
def anomaly_scatter(df: pd.DataFrame) -> go.Figure:
    debits = df[df["type"] == "Debit"].copy()

    color_map = {"Clean": "#3D3D6B", "Low": "#FFD93D", "Medium": "#FF9F43", "High": "#FF6B6B"}
    size_map  = {"Clean": 5, "Low": 9, "Medium": 12, "High": 16}

    debits["color"] = debits["anomaly_severity"].map(color_map)
    debits["size"]  = debits["anomaly_severity"].map(size_map)
    debits["flags_str"] = debits["anomaly_flags"].apply(
        lambda x: "<br>".join(x) if x else "No flags"
    )

    fig = go.Figure()

    for severity in ["Clean", "Low", "Medium", "High"]:
        sub = debits[debits["anomaly_severity"] == severity]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["date"],
            y=sub["amount"],
            mode="markers",
            name=severity,
            marker=dict(color=color_map[severity], size=size_map[severity], opacity=0.8),
            customdata=sub[["description", "flags_str", "category"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "₹%{y:,.0f} on %{x|%d %b}<br>"
                "Category: %{customdata[2]}<br>"
                "%{customdata[1]}<extra></extra>"
            ),
        ))

    fig.update_layout(
        **THEME,
        xaxis=dict(**GRID_STYLE, title="Date"),
        yaxis=dict(**GRID_STYLE, title="Amount (₹)"),
        legend=dict(orientation="h", y=1.1),
        height=360,
    )
    return fig


# ── 7. Category Monthly Stacked Bar ────────────────────────────────────────────
def category_monthly_stacked(df: pd.DataFrame, category_summary: pd.DataFrame) -> go.Figure:
    debits = df[df["type"] == "Debit"]
    pivot = debits.groupby(["month", "category"])["amount"].sum().unstack(fill_value=0)

    fig = go.Figure()
    for cat in pivot.columns:
        color = category_summary[category_summary["category"] == cat]["color"].values
        color = color[0] if len(color) else "#6C63FF"
        fig.add_trace(go.Bar(
            name=cat,
            x=pivot.index.tolist(),
            y=pivot[cat].tolist(),
            marker_color=color,
            hovertemplate=f"<b>{cat}</b><br>%{{x}}<br>₹%{{y:,.0f}}<extra></extra>",
        ))

    fig.update_layout(
        **THEME,
        barmode="stack",
        xaxis=dict(showgrid=False),
        yaxis=dict(**GRID_STYLE, title="Amount (₹)"),
        legend=dict(orientation="h", y=-0.2, font=dict(size=10)),
        height=380,
    )
    return fig


# ── 8. Savings Gauge ────────────────────────────────────────────────────────────
def savings_gauge(savings_rate: float) -> go.Figure:
    color = "#FF6B6B" if savings_rate < 10 else ("#FFD93D" if savings_rate < 20 else "#4ECDC4")

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=savings_rate,
        number=dict(suffix="%", font=dict(size=36, color=color)),
        delta=dict(reference=20, valueformat=".1f"),
        gauge=dict(
            axis=dict(range=[0, 60], tickfont=dict(size=10)),
            bar=dict(color=color, thickness=0.25),
            steps=[
                dict(range=[0, 10],  color="#3D1A1A"),
                dict(range=[10, 20], color="#3D3000"),
                dict(range=[20, 40], color="#1A3D30"),
                dict(range=[40, 60], color="#103020"),
            ],
            threshold=dict(
                line=dict(color="#FFFFFF", width=2),
                thickness=0.8, value=20,
            ),
        ),
        title=dict(text="Savings Rate", font=dict(size=14)),
    ))

    fig.update_layout(**THEME, height=250)
    return fig
