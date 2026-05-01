import pandas as pd
from typing import List, Dict


def _mom_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Month-over-month total spend trend."""
    debits = df[df["type"] == "Debit"]
    monthly = (
        debits.groupby("month")["amount"]
        .sum()
        .reset_index()
        .rename(columns={"amount": "total_spent"})
    )
    monthly["mom_change"] = monthly["total_spent"].diff()
    monthly["mom_pct"] = monthly["total_spent"].pct_change() * 100
    return monthly


def _dayofweek_pattern(df: pd.DataFrame) -> pd.DataFrame:
    """Average spend by day of week."""
    debits = df[df["type"] == "Debit"]
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    pattern = (
        debits.groupby("day_of_week")["amount"]
        .agg(["sum", "mean", "count"])
        .reset_index()
        .rename(columns={"sum": "total", "mean": "avg", "count": "txns"})
    )
    pattern["day_of_week"] = pd.Categorical(pattern["day_of_week"], categories=order, ordered=True)
    return pattern.sort_values("day_of_week")


def _weekend_vs_weekday(df: pd.DataFrame) -> dict:
    """Compare weekend vs weekday spending."""
    debits = df[df["type"] == "Debit"].copy()
    debits["is_weekend"] = debits["day_of_week"].isin(["Saturday", "Sunday"])

    weekend = debits[debits["is_weekend"]]["amount"].sum()
    weekday = debits[~debits["is_weekend"]]["amount"].sum()
    total = weekend + weekday

    return {
        "weekend_total": weekend,
        "weekday_total": weekday,
        "weekend_pct": round(weekend / total * 100, 1) if total > 0 else 0,
        "weekday_pct": round(weekday / total * 100, 1) if total > 0 else 0,
    }


def _detect_subscriptions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect probable subscriptions: same merchant, similar amounts, monthly cadence.
    Returns DataFrame of suspected subscription merchants.
    """
    debits = df[df["type"] == "Debit"].copy()
    subs = []

    sub_keywords = [
        "netflix", "spotify", "hotstar", "prime", "jio", "airtel", "youtube",
        "zee5", "sony", "gaana", "apple", "microsoft", "gym", "cult",
        "subscription", "monthly", "annual", "recharge", "postpaid",
    ]

    for merchant, group in debits.groupby("merchant"):
        is_keyword = any(kw in merchant.lower() for kw in sub_keywords)
        months_active = group["month"].nunique()
        amount_std = group["amount"].std()
        avg_amount = group["amount"].mean()

        # Subscription signal: appears in 2+ months, low variance
        if months_active >= 2 and (amount_std < avg_amount * 0.1 or is_keyword):
            subs.append({
                "merchant": merchant,
                "monthly_cost": round(avg_amount, 2),
                "months_active": months_active,
                "annual_projection": round(avg_amount * 12, 2),
            })

    return pd.DataFrame(subs).sort_values("monthly_cost", ascending=False) if subs else pd.DataFrame()


def _savings_rate(df: pd.DataFrame) -> dict:
    """Estimate savings rate from income vs spend."""
    income = df[df["type"] == "Credit"]["amount"].sum()
    spend = df[df["type"] == "Debit"]["amount"].sum()

    if income == 0:
        return {"income": 0, "spend": spend, "savings": 0, "rate": 0}

    savings = income - spend
    rate = round((savings / income) * 100, 1)
    return {"income": income, "spend": spend, "savings": savings, "rate": rate}


def _guilt_merchant(df: pd.DataFrame) -> dict:
    """Find the 'guilty pleasure' — most frequent merchant in impulsive categories."""
    impulse_cats = ["Food & Dining", "Entertainment", "Shopping"]
    impulse = df[(df["type"] == "Debit") & (df["category"].isin(impulse_cats))]
    if impulse.empty:
        return {}

    top = (
        impulse.groupby("merchant")
        .agg(visits=("amount", "count"), total=("amount", "sum"))
        .reset_index()
        .sort_values("visits", ascending=False)
        .iloc[0]
    )
    return {"merchant": top["merchant"], "visits": top["visits"], "total": top["total"]}


def _spend_velocity(df: pd.DataFrame) -> dict:
    """Average daily and weekly spend."""
    debits = df[df["type"] == "Debit"]
    days = max((df["date"].max() - df["date"].min()).days, 1)
    total = debits["amount"].sum()

    return {
        "avg_daily": round(total / days, 2),
        "avg_weekly": round(total / days * 7, 2),
        "avg_monthly": round(total / max(df["month"].nunique(), 1), 2),
    }


def _biggest_mom_jump(df: pd.DataFrame) -> dict:
    """Find the month with the biggest MoM spending increase."""
    monthly = _mom_trend(df)
    if len(monthly) < 2:
        return {}

    max_jump_idx = monthly["mom_change"].idxmax()
    row = monthly.iloc[max_jump_idx]
    prev = monthly.iloc[max_jump_idx - 1]

    return {
        "month": row["month"],
        "amount": row["total_spent"],
        "prev_month": prev["month"],
        "prev_amount": prev["total_spent"],
        "change": row["mom_change"],
        "pct_change": row["mom_pct"],
    }


def generate_nudges(df: pd.DataFrame, savings: dict, subscriptions: pd.DataFrame) -> List[str]:
    """
    Generate actionable text nudges based on behavioral data.
    Returns list of insight strings.
    """
    nudges = []

    # Savings rate
    rate = savings.get("rate", 0)
    if rate < 20:
        nudges.append(f"💡 Your savings rate is **{rate}%**. Financial experts recommend saving at least 20% of income. You're spending ₹{savings['spend']:,.0f} out of ₹{savings['income']:,.0f} earned.")
    elif rate >= 30:
        nudges.append(f"🏆 Great discipline! Your savings rate is **{rate}%** — above the 30% benchmark. Keep it up!")

    # Food ordering
    food_spend = df[(df["type"] == "Debit") & (df["category"] == "Food & Dining")]["amount"].sum()
    food_orders = len(df[(df["type"] == "Debit") & (df["category"] == "Food & Dining")])
    if food_orders > 20:
        nudges.append(f"🍔 You placed **{food_orders} food delivery orders** totaling ₹{food_spend:,.0f}. That's ₹{food_spend/food_orders:,.0f} per order on average — cooking twice a week could save ~₹{food_spend*0.3:,.0f}/month.")

    # Subscription audit
    if not subscriptions.empty:
        total_subs = subscriptions["monthly_cost"].sum()
        sub_count = len(subscriptions)
        nudges.append(f"📺 You have **{sub_count} detected subscriptions** costing ₹{total_subs:,.0f}/month (₹{total_subs*12:,.0f}/year). Time for a subscription audit?")

    # Weekend splurge
    wknd = _weekend_vs_weekday(df)
    if wknd["weekend_pct"] > 40:
        nudges.append(f"📅 **{wknd['weekend_pct']}% of your spending** happens on weekends. Weekend plans are burning through your budget faster than weekdays.")

    # Late-night spending
    odd_hour = df[(df["type"] == "Debit") & df["is_odd_hour"]] if "is_odd_hour" in df.columns else pd.DataFrame()
    if not odd_hour.empty:
        nudges.append(f"🌙 **{len(odd_hour)} late-night transactions** detected (after 11 PM). Impulse spending risk is highest at night — consider setting a night-time limit.")

    return nudges


def generate_full_insights(df: pd.DataFrame) -> dict:
    """
    Master function. Returns all computed behavioral insights as a dict.
    """
    return {
        "monthly_trend":     _mom_trend(df),
        "dayofweek_pattern": _dayofweek_pattern(df),
        "weekend_vs_weekday":_weekend_vs_weekday(df),
        "subscriptions":     _detect_subscriptions(df),
        "savings_rate":      _savings_rate(df),
        "guilt_merchant":    _guilt_merchant(df),
        "spend_velocity":    _spend_velocity(df),
        "biggest_jump":      _biggest_mom_jump(df),
    }
