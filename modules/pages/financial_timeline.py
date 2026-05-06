from __future__ import annotations

import html
from textwrap import dedent
from typing import Any

import pandas as pd
import streamlit as st

from modules.pages.common import PageContext, format_inr


TIMELINE_GRADIENTS = [
    "linear-gradient(135deg, rgba(141,174,212,0.18), rgba(255,255,255,0.96))",
    "linear-gradient(135deg, rgba(164,204,188,0.18), rgba(255,255,255,0.96))",
    "linear-gradient(135deg, rgba(240,190,150,0.16), rgba(255,255,255,0.96))",
    "linear-gradient(135deg, rgba(222,196,232,0.14), rgba(255,255,255,0.96))",
]

DISCRETIONARY_CATEGORIES = {
    "Food & Dining",
    "Entertainment",
    "Shopping",
    "Travel & Stays",
    "Personal Care",
}


def _safe_div(numerator: float, denominator: float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def _short_inr(amount: float) -> str:
    amount = float(amount or 0)
    sign = "-" if amount < 0 else ""
    value = abs(amount)
    if value >= 100000:
        return f"{sign}\u20b9{value / 100000:.1f}L"
    if value >= 1000:
        return f"{sign}\u20b9{value / 1000:.1f}K"
    return f"{sign}\u20b9{value:,.0f}"


def _format_delta_pct(value: float) -> str:
    if pd.isna(value):
        return "0%"
    direction = "+" if value > 0 else ""
    return f"{direction}{value:.0f}%"


def _category_breakdown(month_df: pd.DataFrame) -> pd.DataFrame:
    debits = month_df[month_df["type"] == "Debit"]
    if debits.empty:
        return pd.DataFrame(columns=["category", "total_spent", "txns"])
    return (
        debits.groupby("category", dropna=False)["amount"]
        .agg(total_spent="sum", txns="count")
        .reset_index()
        .sort_values(["total_spent", "txns"], ascending=[False, False])
    )


def _merchant_breakdown(month_df: pd.DataFrame) -> pd.DataFrame:
    debits = month_df[month_df["type"] == "Debit"]
    if debits.empty:
        return pd.DataFrame(columns=["merchant", "total_spent", "txns"])
    return (
        debits.groupby("merchant", dropna=False)["amount"]
        .agg(total_spent="sum", txns="count")
        .reset_index()
        .sort_values(["total_spent", "txns"], ascending=[False, False])
    )


def _detect_month_subscriptions(month_df: pd.DataFrame, full_df: pd.DataFrame) -> list[str]:
    debits = full_df[full_df["type"] == "Debit"].copy()
    if debits.empty:
        return []

    monthly_presence = debits.groupby("merchant")["month"].nunique()
    merchant_amount_std = debits.groupby("merchant")["amount"].std().fillna(0)
    merchant_amount_mean = debits.groupby("merchant")["amount"].mean().fillna(0)

    candidates: list[str] = []
    month_merchants = month_df[month_df["type"] == "Debit"]["merchant"].dropna().unique().tolist()
    for merchant in month_merchants:
        mean_amt = float(merchant_amount_mean.get(merchant, 0))
        std_amt = float(merchant_amount_std.get(merchant, 0))
        appears_often = int(monthly_presence.get(merchant, 0)) >= 2
        keyword_match = any(
            token in str(merchant).lower()
            for token in [
                "netflix",
                "spotify",
                "prime",
                "hotstar",
                "youtube",
                "airtel",
                "jio",
                "recharge",
                "gym",
                "apple",
                "microsoft",
                "subscription",
            ]
        )
        if appears_often and (keyword_match or (mean_amt > 0 and std_amt <= mean_amt * 0.15)):
            candidates.append(str(merchant))
    return sorted(set(candidates))[:4]


def _compute_month_metrics(month_df: pd.DataFrame, full_df: pd.DataFrame) -> dict[str, Any]:
    debits = month_df[month_df["type"] == "Debit"].copy()
    credits = month_df[month_df["type"] == "Credit"].copy()

    total_spend = float(debits["amount"].sum())
    total_income = float(credits["amount"].sum())
    savings_estimate = total_income - total_spend
    category_breakdown = _category_breakdown(month_df)
    merchant_breakdown = _merchant_breakdown(month_df)

    top_category = (
        {
            "name": str(category_breakdown.iloc[0]["category"]),
            "amount": float(category_breakdown.iloc[0]["total_spent"]),
        }
        if not category_breakdown.empty
        else {"name": "No debit activity", "amount": 0.0}
    )
    top_merchant = (
        {
            "name": str(merchant_breakdown.iloc[0]["merchant"]),
            "amount": float(merchant_breakdown.iloc[0]["total_spent"]),
        }
        if not merchant_breakdown.empty
        else {"name": "No merchant trend", "amount": 0.0}
    )

    daily_spend = (
        debits.groupby(debits["date"].dt.date)["amount"].sum().sort_values(ascending=False)
        if not debits.empty
        else pd.Series(dtype=float)
    )
    avg_daily_spend = float(daily_spend.mean()) if not daily_spend.empty else 0.0
    spend_volatility = float(daily_spend.std(ddof=0) / avg_daily_spend) if avg_daily_spend else 0.0
    binge_threshold = avg_daily_spend * 1.8 if avg_daily_spend else 0.0
    binge_days = int((daily_spend > binge_threshold).sum()) if binge_threshold else 0

    unusual = debits[debits["anomaly_score"] >= 2].copy() if "anomaly_score" in debits.columns else pd.DataFrame()
    anomaly_count = int(len(unusual))
    unusual_spend = float(unusual["amount"].sum()) if not unusual.empty else 0.0

    weekend_mask = month_df["day_of_week"].isin(["Saturday", "Sunday"]) if "day_of_week" in month_df.columns else pd.Series(False, index=month_df.index)
    weekend_spend = float(month_df[weekend_mask & (month_df["type"] == "Debit")]["amount"].sum())
    weekend_share = round(_safe_div(weekend_spend, total_spend) * 100, 1)

    late_night_mask = month_df.get("is_odd_hour", pd.Series(False, index=month_df.index))
    late_night = month_df[(month_df["type"] == "Debit") & late_night_mask]
    late_night_count = int(len(late_night))
    late_night_spend = float(late_night["amount"].sum()) if not late_night.empty else 0.0

    payday_window = pd.DataFrame(columns=month_df.columns)
    if not credits.empty:
        payday_dates = credits["date"].dt.normalize().unique().tolist()
        payday_mask = pd.Series(False, index=month_df.index)
        for payday_date in payday_dates:
            payday_mask = payday_mask | month_df["date"].between(payday_date, payday_date + pd.Timedelta(days=3))
        payday_window = month_df[(month_df["type"] == "Debit") & payday_mask]
    payday_spend = float(payday_window["amount"].sum()) if not payday_window.empty else 0.0
    payday_share = round(_safe_div(payday_spend, total_spend) * 100, 1)

    bnpl_spend = float(
        month_df[(month_df["type"] == "Debit") & (month_df["category"] == "BNPL & Credit")]["amount"].sum()
    )
    discretionary_spend = float(
        month_df[(month_df["type"] == "Debit") & (month_df["category"].isin(DISCRETIONARY_CATEGORIES))]["amount"].sum()
    )
    subscriptions = _detect_month_subscriptions(month_df, full_df)

    avg_ticket = float(debits["amount"].mean()) if not debits.empty else 0.0
    score = 72
    score -= min(spend_volatility * 18, 18)
    score -= min(anomaly_count * 3, 15)
    score -= min(_safe_div(bnpl_spend, max(total_spend, 1)) * 25, 12)
    score -= min(_safe_div(late_night_spend, max(total_spend, 1)) * 18, 10)
    score += min(max(_safe_div(savings_estimate, max(total_income, 1)) * 100, 0), 25) * 0.6
    score = int(max(20, min(96, round(score))))

    return {
        "month": str(month_df["month"].iloc[0]),
        "month_name": pd.Period(str(month_df["month"].iloc[0]), freq="M").strftime("%B %Y"),
        "total_spend": total_spend,
        "total_income": total_income,
        "savings_estimate": savings_estimate,
        "top_category": top_category,
        "top_merchant": top_merchant,
        "category_breakdown": category_breakdown,
        "merchant_breakdown": merchant_breakdown,
        "spend_volatility": spend_volatility,
        "anomaly_count": anomaly_count,
        "unusual_spend": unusual_spend,
        "subscriptions": subscriptions,
        "weekend_share": weekend_share,
        "late_night_count": late_night_count,
        "late_night_spend": late_night_spend,
        "payday_share": payday_share,
        "bnpl_spend": bnpl_spend,
        "binge_days": binge_days,
        "debit_count": int(len(debits)),
        "credit_count": int(len(credits)),
        "avg_ticket": avg_ticket,
        "money_score": score,
        "discretionary_spend": discretionary_spend,
    }


def detect_behavioral_changes(
    current_metrics: dict[str, Any],
    prev_metrics: dict[str, Any] | None,
    month_df: pd.DataFrame,
    prev_month_df: pd.DataFrame | None,
) -> dict[str, Any]:
    if prev_metrics is None or prev_month_df is None or prev_month_df.empty:
        return {
            "events": ["This is the first month in your timeline, so it sets the baseline for future comparisons."],
            "tags": ["Baseline month"],
            "trend_direction": "flat",
        }

    events: list[str] = []
    tags: list[str] = []

    prev_categories = prev_metrics["category_breakdown"].set_index("category")["total_spent"] if not prev_metrics["category_breakdown"].empty else pd.Series(dtype=float)
    curr_categories = current_metrics["category_breakdown"].set_index("category")["total_spent"] if not current_metrics["category_breakdown"].empty else pd.Series(dtype=float)
    all_categories = sorted(set(prev_categories.index).union(set(curr_categories.index)))

    category_changes: list[tuple[str, float, float, float]] = []
    for category in all_categories:
        prev_amt = float(prev_categories.get(category, 0.0))
        curr_amt = float(curr_categories.get(category, 0.0))
        delta = curr_amt - prev_amt
        pct = (_safe_div(delta, prev_amt) * 100) if prev_amt else (100.0 if curr_amt > 0 else 0.0)
        category_changes.append((category, curr_amt, delta, pct))

    largest_rise = max(category_changes, key=lambda item: item[2], default=None)
    largest_drop = min(category_changes, key=lambda item: item[2], default=None)

    if largest_rise and largest_rise[2] > 0 and abs(largest_rise[3]) >= 15:
        events.append(f"{largest_rise[0]} spending rose {abs(largest_rise[3]):.0f}% compared to last month.")
        tags.append(f"{largest_rise[0]} up")
    if largest_drop and largest_drop[2] < 0 and abs(largest_drop[3]) >= 15:
        events.append(f"{largest_drop[0]} spending dropped {abs(largest_drop[3]):.0f}% from the previous month.")
        tags.append(f"{largest_drop[0]} down")

    volatility_delta = current_metrics["spend_volatility"] - prev_metrics["spend_volatility"]
    if volatility_delta <= -0.2:
        events.append("Daily spending felt steadier than last month, with fewer sharp swings.")
        tags.append("More stable")
    elif volatility_delta >= 0.2:
        events.append("Spending became more uneven this month, with bigger day-to-day jumps.")
        tags.append("More volatile")

    anomaly_delta = current_metrics["anomaly_count"] - prev_metrics["anomaly_count"]
    if anomaly_delta <= -2:
        events.append("This month had fewer unusual transactions.")
        tags.append("Calmer pattern")
    elif anomaly_delta >= 2:
        events.append("Unusual spending spikes showed up more often this month.")
        tags.append("Spike alerts")

    subs_delta = len(current_metrics["subscriptions"]) - len(prev_metrics["subscriptions"])
    if subs_delta > 0:
        events.append("Recurring subscriptions increased this month.")
        tags.append("Subscription creep")
    elif subs_delta < 0:
        events.append("Your recurring stack got lighter this month.")
        tags.append("Subscriptions trimmed")

    bnpl_delta = current_metrics["bnpl_spend"] - prev_metrics["bnpl_spend"]
    if bnpl_delta > 750:
        events.append("BNPL-style spending stepped up this month.")
        tags.append("BNPL higher")
    elif bnpl_delta < -750:
        events.append("BNPL-related payments eased compared to last month.")
        tags.append("BNPL lower")

    late_night_delta = current_metrics["late_night_count"] - prev_metrics["late_night_count"]
    if late_night_delta >= 2:
        events.append("Late-night purchases became more common after 10 PM.")
        tags.append("Night spending up")
    elif late_night_delta <= -2:
        events.append("Late-night spending cooled off this month.")
        tags.append("Night spending down")

    spend_delta = current_metrics["total_spend"] - prev_metrics["total_spend"]
    direction = "up" if spend_delta > 0 else "down" if spend_delta < 0 else "flat"
    if abs(spend_delta) >= max(prev_metrics["total_spend"] * 0.12, 2000):
        pct = _safe_div(spend_delta, prev_metrics["total_spend"]) * 100 if prev_metrics["total_spend"] else 0.0
        verb = "rose" if spend_delta > 0 else "fell"
        events.insert(0, f"Overall spending {verb} {abs(pct):.0f}% month over month.")
        tags.append("Spend " + direction)

    if not events:
        events.append("Your overall pattern stayed relatively consistent with the previous month.")
        tags.append("Consistent")

    return {
        "events": events[:5],
        "tags": tags[:5],
        "trend_direction": direction,
    }


def _emotional_spending_signals(metrics: dict[str, Any]) -> list[str]:
    signals: list[str] = []
    if metrics["late_night_count"] >= 3:
        signals.append(f"Most impulse risk showed up late at night, with {metrics['late_night_count']} after-hours spends.")
    if metrics["weekend_share"] >= 38:
        signals.append(f"Weekends drove {metrics['weekend_share']:.0f}% of debit spend, suggesting a stronger leisure pattern.")
    if metrics["payday_share"] >= 35:
        signals.append(f"Around payday, {metrics['payday_share']:.0f}% of spending landed within the first few days after income arrived.")
    if metrics["binge_days"] >= 2:
        signals.append(f"There were {metrics['binge_days']} binge-spend days where daily outflow ran well above your monthly norm.")
    return signals[:2]


def generate_month_story(month_df: pd.DataFrame, prev_month_df: pd.DataFrame | None = None) -> dict[str, Any]:
    full_df = month_df.attrs.get("timeline_full_df")
    if full_df is None:
        full_df = month_df if prev_month_df is None else pd.concat([prev_month_df, month_df], ignore_index=True)
    current_metrics = _compute_month_metrics(month_df, full_df)
    prev_metrics = _compute_month_metrics(prev_month_df, full_df) if prev_month_df is not None and not prev_month_df.empty else None

    change_info = detect_behavioral_changes(current_metrics, prev_metrics, month_df, prev_month_df)
    emotional_signals = _emotional_spending_signals(current_metrics)

    narrative_lines: list[str] = []
    if current_metrics["top_category"]["amount"] > 0:
        narrative_lines.append(
            f"{current_metrics['month_name']} was led by {current_metrics['top_category']['name'].lower()}, which became your biggest spend area."
        )
    if current_metrics["top_merchant"]["amount"] > 0:
        narrative_lines.append(
            f"{current_metrics['top_merchant']['name']} was the standout merchant at {_short_inr(current_metrics['top_merchant']['amount'])}."
        )

    if current_metrics["money_score"] >= 80:
        narrative_lines.append("This was one of your more stable months financially, with a calmer rhythm underneath the spending.")
    elif current_metrics["money_score"] <= 50:
        narrative_lines.append("The month felt busier and a little more reactive, with more pressure from variable spending.")

    if current_metrics["subscriptions"]:
        narrative_lines.append(f"Recurring payments stayed visible through {', '.join(current_metrics['subscriptions'][:2])}.")

    if current_metrics["anomaly_count"] >= 3:
        narrative_lines.append("A few spending spikes stood out enough to deserve a second look.")

    story = " ".join(narrative_lines[:4]).strip()
    if not story:
        story = f"{current_metrics['month_name']} was a quieter month with limited debit activity, giving you a clean baseline."

    key_insight = change_info["events"][0] if change_info["events"] else "This month set a useful baseline for your financial timeline."
    if emotional_signals:
        key_insight = emotional_signals[0]

    return {
        "metrics": current_metrics,
        "narrative": story,
        "change_events": change_info["events"],
        "trend_tags": change_info["tags"],
        "emotional_signals": emotional_signals,
        "key_insight": key_insight,
    }


def _compute_milestones(month_cards: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    if not month_cards:
        return {}

    cards = month_cards
    highest_spend = max(cards, key=lambda item: item["metrics"]["total_spend"])
    lowest_spend = min(cards, key=lambda item: item["metrics"]["total_spend"])
    best_savings = max(cards, key=lambda item: item["metrics"]["savings_estimate"])
    most_stable = max(cards, key=lambda item: (item["metrics"]["money_score"], -item["metrics"]["spend_volatility"]))
    most_chaotic = max(cards, key=lambda item: (item["metrics"]["spend_volatility"], item["metrics"]["anomaly_count"]))

    recovery_card = None
    recovery_value = 0.0
    for idx in range(1, len(cards)):
        prev_score = cards[idx - 1]["metrics"]["money_score"]
        curr_score = cards[idx]["metrics"]["money_score"]
        spend_drop = cards[idx - 1]["metrics"]["total_spend"] - cards[idx]["metrics"]["total_spend"]
        recovery_signal = (curr_score - prev_score) + _safe_div(spend_drop, 1000)
        if recovery_signal > recovery_value:
            recovery_value = recovery_signal
            recovery_card = cards[idx]

    badge_map: dict[str, list[dict[str, str]]] = {}

    def _add_badge(month_key: str, label: str, detail: str) -> None:
        badge_map.setdefault(month_key, []).append({"label": label, "detail": detail})

    _add_badge(
        highest_spend["metrics"]["month"],
        "Highest spend",
        f"Peak outflow at {_short_inr(highest_spend['metrics']['total_spend'])}",
    )
    _add_badge(
        lowest_spend["metrics"]["month"],
        "Lowest spend",
        f"Lightest spending month at {_short_inr(lowest_spend['metrics']['total_spend'])}",
    )
    _add_badge(
        best_savings["metrics"]["month"],
        "Best savings",
        f"Strongest savings estimate at {_short_inr(best_savings['metrics']['savings_estimate'])}",
    )
    _add_badge(
        most_stable["metrics"]["month"],
        "Most stable",
        f"Money score {most_stable['metrics']['money_score']} with calmer day-to-day motion",
    )
    _add_badge(
        most_chaotic["metrics"]["month"],
        "Most chaotic",
        f"{most_chaotic['metrics']['anomaly_count']} unusual signals with higher volatility",
    )

    if recovery_card is not None and recovery_value > 3:
        _add_badge(
            recovery_card["metrics"]["month"],
            "Strongest recovery",
            "Recovered with a stronger score and softer spending rhythm",
        )
    return badge_map


def build_monthly_timeline(df: pd.DataFrame) -> dict[str, Any]:
    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"], errors="coerce")
    working_df = working_df.dropna(subset=["date", "month"]).sort_values("date")

    month_cards: list[dict[str, Any]] = []
    month_order = sorted(working_df["month"].dropna().unique().tolist())
    month_frames = {month: working_df[working_df["month"] == month].copy() for month in month_order}

    for index, month in enumerate(month_order):
        month_df = month_frames[month]
        month_df.attrs["timeline_full_df"] = working_df
        prev_month_df = month_frames[month_order[index - 1]] if index > 0 else None
        if prev_month_df is not None:
            prev_month_df = prev_month_df.copy()
            prev_month_df.attrs["timeline_full_df"] = working_df
        story = generate_month_story(month_df, prev_month_df)
        month_cards.append(story)

    milestone_map = _compute_milestones(month_cards)
    for card in month_cards:
        card["milestones"] = milestone_map.get(card["metrics"]["month"], [])

    emotional_summary = []
    if month_cards:
        weekend_heavy = [card for card in month_cards if card["metrics"]["weekend_share"] >= 38]
        late_night_heavy = [card for card in month_cards if card["metrics"]["late_night_count"] >= 3]
        payday_heavy = [card for card in month_cards if card["metrics"]["payday_share"] >= 35]
        if weekend_heavy:
            emotional_summary.append("Weekends consistently increased discretionary spending across the timeline.")
        if late_night_heavy:
            emotional_summary.append("Impulse-style spending was more likely to happen after 10 PM.")
        if payday_heavy:
            emotional_summary.append("Salary week often triggered an early-month spending burst.")

    return {
        "months": list(reversed(month_cards)),
        "milestones": [badge for badges in milestone_map.values() for badge in badges],
        "emotional_summary": emotional_summary[:3],
    }


def _render_timeline_styles() -> None:
    st.markdown(
        """
        <style>
        .timeline-hero,
        .timeline-summary-card,
        .timeline-month-shell,
        .timeline-detail-box,
        .timeline-milestone-card {
            border: 1px solid rgba(216, 209, 198, 0.9);
            border-radius: 24px;
            box-shadow: 0 14px 34px rgba(35, 29, 23, 0.05);
            background: rgba(255,255,255,0.92);
        }
        .timeline-hero {
            padding: 24px;
            background: linear-gradient(135deg, rgba(141,174,212,0.18), rgba(255,255,255,0.96));
        }
        .timeline-summary-card,
        .timeline-milestone-card {
            padding: 18px 20px;
        }
        .timeline-month-shell {
            padding: 18px 18px 10px;
            margin-bottom: 16px;
        }
        .timeline-month-chip {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(255,255,255,0.72);
            border: 1px solid rgba(216, 209, 198, 0.9);
            border-radius: 999px;
            padding: 7px 12px;
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: #526b89;
        }
        .timeline-badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 7px 11px;
            font-size: 0.78rem;
            font-weight: 600;
            background: rgba(40, 126, 97, 0.12);
            color: #1f6d52;
            border: 1px solid rgba(40, 126, 97, 0.18);
        }
        .timeline-tag {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 7px 11px;
            font-size: 0.78rem;
            font-weight: 600;
            background: rgba(141,174,212,0.16);
            color: #4f6785;
            margin: 0 8px 8px 0;
        }
        .timeline-score-box {
            background: rgba(255,255,255,0.72);
            border: 1px solid rgba(223,216,206,0.95);
            border-radius: 20px;
            padding: 14px 16px;
            text-align: center;
            min-height: 100%;
        }
        .timeline-score-value {
            font-size: 2.2rem;
            font-weight: 800;
            line-height: 1;
            color: #1b1a18;
        }
        .timeline-score-label,
        .timeline-mini-label {
            font-size: 0.72rem;
            color: #6e685f;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 6px;
        }
        .timeline-story {
            font-size: 1rem;
            line-height: 1.75;
            color: #2a2824;
        }
        .timeline-metric-card,
        .timeline-detail-box {
            background: rgba(255,255,255,0.68);
            border: 1px solid rgba(223,216,206,0.95);
            border-radius: 18px;
            padding: 12px 14px;
            min-height: 100%;
        }
        .timeline-metric-value,
        .timeline-detail-title {
            font-size: 1rem;
            font-weight: 700;
            color: #1b1a18;
            line-height: 1.35;
        }
        .timeline-detail-copy,
        .timeline-bullet {
            font-size: 0.9rem;
            color: #2d2a26;
            line-height: 1.6;
        }
        .timeline-bullet {
            margin-bottom: 8px;
        }
        .timeline-expander details {
            border: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_metric_card(label: str, value: str) -> None:
    st.markdown(
        dedent(
            f"""
            <div class='timeline-metric-card'>
                <div class='timeline-mini-label'>{html.escape(label)}</div>
                <div class='timeline-metric-value'>{html.escape(value)}</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def _render_detail_box(title: str, body: str) -> None:
    st.markdown(
        dedent(
            f"""
            <div class='timeline-detail-box'>
                <div class='timeline-mini-label'>{html.escape(title)}</div>
                <div class='timeline-detail-copy'>{html.escape(body)}</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def _render_chip_row(items: list[str], class_name: str = "timeline-tag") -> None:
    if not items:
        return
    chip_html = "".join(
        f"<span class='{class_name}'>{html.escape(item)}</span>"
        for item in items
        if item
    )
    st.markdown(chip_html, unsafe_allow_html=True)


def _build_timeline_summary(timeline_payload: dict[str, Any]) -> dict[str, str]:
    months = timeline_payload["months"]
    latest = months[0]["metrics"] if months else {}
    calmest = max(months, key=lambda card: card["metrics"]["money_score"])["metrics"] if months else {}
    noisiest = max(months, key=lambda card: card["metrics"]["anomaly_count"])["metrics"] if months else {}

    opening = "Your money story is starting to show a pattern."
    if latest:
        opening = (
            f"Lately, {latest['month_name']} closed with a money score of {latest['money_score']} "
            f"and total spend of {_short_inr(latest['total_spend'])}."
        )

    rhythm = ""
    if calmest and noisiest:
        rhythm = (
            f"Your calmest stretch was {calmest['month_name']}, while {noisiest['month_name']} carried "
            f"the most unusual activity."
        )

    return {
        "opening": opening,
        "rhythm": rhythm,
    }


def render_timeline_ui(timeline_payload: dict[str, Any]) -> None:
    _render_timeline_styles()
    summary = _build_timeline_summary(timeline_payload)

    hero_left, hero_right = st.columns([1.3, 1])
    with hero_left:
        st.markdown(
            dedent(
                """
            <div class='timeline-hero'>
                <div class='micro-label'>Financial memory</div>
                <div class='card-title' style='font-size:1.5rem; margin-top:10px;'>Your money story, month by month.</div>
                <div class='card-detail' style='font-size:0.96rem; margin-top:10px; max-width:720px;'>
                    This view follows the emotional shape of your spending: where money felt steady, where it drifted, and which habits kept repeating in the background.
                </div>
                <div class='card-detail' style='font-size:0.95rem; margin-top:14px; max-width:720px;'>
                    """
                + html.escape(summary["opening"])
                + " "
                + html.escape(summary["rhythm"])
                + """
                </div>
            </div>
            """
            ),
            unsafe_allow_html=True,
        )
    with hero_right:
        milestone_lines = timeline_payload["milestones"][:4]
        if milestone_lines:
            st.markdown(
                "<div class='timeline-milestone-card'><div class='micro-label'>Milestones</div></div>",
                unsafe_allow_html=True,
            )
            for item in milestone_lines:
                _render_detail_box(item["label"], item["detail"])

    if timeline_payload["months"]:
        st.markdown("<div class='section-header'>Story Summary</div>", unsafe_allow_html=True)
        summary_cols = st.columns(4)
        latest = timeline_payload["months"][0]["metrics"]
        strongest = max(timeline_payload["months"], key=lambda card: card["metrics"]["money_score"])["metrics"]
        highest = max(timeline_payload["months"], key=lambda card: card["metrics"]["total_spend"])["metrics"]
        noisiest = max(timeline_payload["months"], key=lambda card: card["metrics"]["anomaly_count"])["metrics"]
        summary_data = [
            ("Latest month", latest["month_name"]),
            ("Best score", f"{strongest['money_score']} in {strongest['month_name']}"),
            ("Peak spend", f"{_short_inr(highest['total_spend'])} in {highest['month_name']}"),
            ("Most unusual", f"{noisiest['anomaly_count']} flags in {noisiest['month_name']}"),
        ]
        for col, (label, value) in zip(summary_cols, summary_data):
            with col:
                _render_metric_card(label, value)

    if timeline_payload["emotional_summary"]:
        st.markdown("<div class='section-header'>Behavioral signals</div>", unsafe_allow_html=True)
        signal_cols = st.columns(len(timeline_payload["emotional_summary"]))
        for col, signal in zip(signal_cols, timeline_payload["emotional_summary"]):
            with col:
                _render_detail_box("Observed pattern", signal)

    st.markdown("<div class='section-header'>Monthly Breakdown</div>", unsafe_allow_html=True)
    for index, card in enumerate(timeline_payload["months"]):
        metrics = card["metrics"]
        milestones = card.get("milestones", [])
        subscription_text = ", ".join(metrics["subscriptions"]) if metrics["subscriptions"] else "No recurring subscription pattern detected"
        anomaly_highlight = (
            f"{metrics['anomaly_count']} unusual transactions worth {_short_inr(metrics['unusual_spend'])}"
            if metrics["anomaly_count"]
            else "No strong anomaly spikes this month"
        )
        st.markdown(
            dedent(
                f"""
            <div class='timeline-month-shell' style='background:{TIMELINE_GRADIENTS[index % len(TIMELINE_GRADIENTS)]};'>
                <span class='timeline-month-chip'>{html.escape(metrics['month_name'])}</span>
            </div>
                """
            ),
            unsafe_allow_html=True,
        )
        top_cols = st.columns([1.35, 0.65])
        with top_cols[0]:
            st.markdown(f"<div class='timeline-story'>{html.escape(card['narrative'])}</div>", unsafe_allow_html=True)
            if milestones:
                _render_chip_row([item["label"] for item in milestones[:3]], class_name="timeline-badge")
            _render_chip_row(card["trend_tags"][:5], class_name="timeline-tag")
        with top_cols[1]:
            st.markdown(
                dedent(
                    f"""
                    <div class='timeline-score-box'>
                        <div class='timeline-score-label'>Money score</div>
                        <div class='timeline-score-value'>{metrics['money_score']}</div>
                        <div class='timeline-detail-copy'>Spend {format_inr(metrics['total_spend'])}</div>
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )

        kpi_cols = st.columns(4)
        with kpi_cols[0]:
            _render_metric_card("Savings estimate", format_inr(metrics["savings_estimate"]))
        with kpi_cols[1]:
            _render_metric_card("Top category", metrics["top_category"]["name"])
        with kpi_cols[2]:
            _render_metric_card("Biggest merchant", metrics["top_merchant"]["name"])
        with kpi_cols[3]:
            _render_metric_card("Unusual spend", anomaly_highlight)

        with st.expander(f"Open detailed breakdown for {metrics['month_name']}", expanded=False):
            detail_left, detail_right = st.columns(2)
            with detail_left:
                _render_detail_box("Key insight", card["key_insight"])
                for event in card["change_events"][:3]:
                    _render_detail_box("Change event", event)
            with detail_right:
                _render_detail_box("Recurring subscriptions", subscription_text)
                if card["emotional_signals"]:
                    for signal in card["emotional_signals"][:2]:
                        _render_detail_box("Behavioral note", signal)
                else:
                    _render_detail_box("Behavioral note", "No strong emotional spending signal stood out this month.")

            mix_cols = st.columns(4)
            mix_data = [
                ("Weekend share", f"{metrics['weekend_share']:.0f}%"),
                ("Payday share", f"{metrics['payday_share']:.0f}%"),
                ("Late-night txns", str(metrics["late_night_count"])),
                ("Binge days", str(metrics["binge_days"])),
            ]
            for col, (label, value) in zip(mix_cols, mix_data):
                with col:
                    _render_metric_card(label, value)


def render(context: PageContext) -> None:
    st.markdown(
        dedent(
            """
        <div style='padding: 8px 0 2px;'>
            <div style='font-family:"DM Sans",sans-serif; font-size:1.6rem; font-weight:700; color:#151515;'>
                Financial timeline
            </div>
            <div style='font-size:0.92rem; color:#6c675f; margin-top:6px; font-family:"DM Sans",sans-serif;'>
                A narrative view of how your money moved, settled, and changed over time.
            </div>
        </div>
            """
        ),
        unsafe_allow_html=True,
    )

    if context.df.empty or context.df["month"].nunique() == 0:
        st.info("Upload transaction history to build your financial timeline.")
        return

    timeline_payload = build_monthly_timeline(context.df)
    render_timeline_ui(timeline_payload)
