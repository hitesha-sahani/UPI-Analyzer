


import pandas as pd
import numpy as np
from datetime import date, timedelta
from typing import Dict, Optional


# ── Default budgets (₹/month) — user can override in UI ───────────────────────
DEFAULT_BUDGETS: Dict[str, float] = {
    "Food & Dining":       4000,
    "Transport":           2000,
    "Shopping":            5000,
    "Groceries":           3500,
    "Entertainment":       1500,
    "Health & Medical":    2000,
    "Education":           2000,
    "Bills & Utilities":   3000,
    "Finance & Investment":10000,
    "Transfers":           5000,
    "Travel & Stays":      5000,
    "Others":              2000,
}


def _days_in_current_month(ref_date: Optional[date] = None) -> int:
    """Return number of days in the reference month."""
    d = ref_date or date.today()
    # Last day of month trick
    next_month = d.replace(day=28) + timedelta(days=4)
    last_day = next_month - timedelta(days=next_month.day)
    return last_day.day


def _days_elapsed(ref_date: Optional[date] = None) -> int:
    """Days elapsed so far in current month (min 1 to avoid div/0)."""
    d = ref_date or date.today()
    return max(d.day, 1)


def compute_budget_status(
    df: pd.DataFrame,
    budgets: Dict[str, float],
    reference_month: Optional[str] = None,
) -> pd.DataFrame:
    
    debits = df[df["type"] == "Debit"].copy()

    # Determine reference month
    if reference_month is None:
        reference_month = debits["month"].max()

    month_data = debits[debits["month"] == reference_month]

    # Parse month dates for burn-rate calc
    try:
        ref_date = pd.to_datetime(reference_month + "-01").date()
    except Exception:
        ref_date = date.today().replace(day=1)

    # Determine days elapsed and days in month
    today = date.today()
    if ref_date.year == today.year and ref_date.month == today.month:
        elapsed = _days_elapsed(today)
        total_days = _days_in_current_month(today)
    else:
        # Historical month — treat as complete
        total_days = _days_in_current_month(ref_date)
        elapsed = total_days

    days_remaining = max(total_days - elapsed, 0)

    rows = []
    for category, budget in budgets.items():
        spent = month_data[month_data["category"] == category]["amount"].sum()
        remaining = budget - spent
        pct_used = min((spent / budget * 100) if budget > 0 else 0, 999)

        # Burn rate: ₹ spent per day so far
        daily_burn = spent / elapsed if elapsed > 0 else 0

        # Projected end-of-month spend
        projected_eom = spent + (daily_burn * days_remaining)

        # Will we breach?
        will_breach = projected_eom > budget
        breach_amount = max(projected_eom - budget, 0)

        # Days until breach (if trending over budget)
        if daily_burn > 0 and remaining > 0:
            days_to_breach = remaining / daily_burn
        elif remaining <= 0:
            days_to_breach = 0
        else:
            days_to_breach = float("inf")

        # Status label
        if pct_used >= 100:
            status = "Over Budget"
        elif pct_used >= 85:
            status = "Critical"
        elif pct_used >= 60:
            status = "Warning"
        elif pct_used >= 30:
            status = "On Track"
        else:
            status = "Healthy"

        rows.append({
            "category":       category,
            "budget":         budget,
            "spent":          spent,
            "remaining":      remaining,
            "pct_used":       round(pct_used, 1),
            "daily_burn":     round(daily_burn, 2),
            "projected_eom":  round(projected_eom, 2),
            "will_breach":    will_breach,
            "days_to_breach": round(days_to_breach, 1) if days_to_breach != float("inf") else None,
            "breach_amount":  round(breach_amount, 2),
            "status":         status,
            "days_remaining": days_remaining,
            "elapsed_days":   elapsed,
            "total_days":     total_days,
            "reference_month": reference_month,
        })

    result = pd.DataFrame(rows)
    # Only show categories with budget > 0 or that have transactions
    result = result[(result["budget"] > 0) | (result["spent"] > 0)]
    return result.sort_values("pct_used", ascending=False).reset_index(drop=True)


def get_budget_alerts(budget_status: pd.DataFrame) -> list:
    """
    Generate plain-English alert strings for critical/breach categories.
    Returns list of (severity, message) tuples.
    """
    alerts = []
    for _, row in budget_status.iterrows():
        cat = row["category"]
        spent = row["spent"]
        budget = row["budget"]
        breach = row["breach_amount"]
        days_left = row["days_remaining"]
        days_to_breach = row["days_to_breach"]
        proj = row["projected_eom"]

        if row["status"] == "Over Budget":
            alerts.append(("🔴 Over Budget", cat,
                f"Already exceeded by ₹{abs(row['remaining']):,.0f}. "
                f"Spent ₹{spent:,.0f} of ₹{budget:,.0f} budget."))

        elif row["status"] == "Critical" and row["will_breach"]:
            alerts.append(("🟠 Breach Incoming", cat,
                f"At this pace, you'll exceed your ₹{budget:,.0f} budget by "
                f"₹{breach:,.0f} in {days_left} days. "
                f"Projected spend: ₹{proj:,.0f}."))

        elif row["will_breach"] and days_to_breach and days_to_breach <= 7:
            alerts.append(("🟡 Approaching Limit", cat,
                f"Budget breach expected in ~{days_to_breach:.0f} days. "
                f"Slow down — you're burning ₹{row['daily_burn']:,.0f}/day here."))

    return alerts


def get_overall_budget_health(budget_status: pd.DataFrame) -> dict:
    """Returns aggregate health score and summary."""
    total_budget = budget_status["budget"].sum()
    total_spent  = budget_status["spent"].sum()
    over_count   = len(budget_status[budget_status["status"] == "Over Budget"])
    critical_count = len(budget_status[budget_status["status"] == "Critical"])
    healthy_count  = len(budget_status[budget_status["status"].isin(["Healthy", "On Track"])])

    health_pct = max(0, 100 - (over_count * 25) - (critical_count * 10))

    return {
        "total_budget":    total_budget,
        "total_spent":     total_spent,
        "total_remaining": total_budget - total_spent,
        "over_count":      over_count,
        "critical_count":  critical_count,
        "healthy_count":   healthy_count,
        "health_score":    health_pct,
    }
