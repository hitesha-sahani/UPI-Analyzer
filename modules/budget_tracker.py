import pandas as pd
from datetime import date
from typing import Dict


ALL_CATEGORIES = [
    "Food & Dining", "Groceries", "Transport", "Shopping",
    "Subscriptions", "Entertainment", "Bills & Utilities",
    "Housing & Rent", "Finance & Investment", "BNPL & Credit",
    "Health & Medical", "Education", "Travel & Stays",
    "P2P Transfers", "Personal Care", "Home & Maintenance",
    "Charity & Donations", "Others",
]

DEFAULT_BUDGETS: Dict[str, dict] = {
    "Food & Dining":        {"amount": 4000,  "period": "Monthly"},
    "Groceries":            {"amount": 3500,  "period": "Monthly"},
    "Transport":            {"amount": 2000,  "period": "Monthly"},
    "Shopping":             {"amount": 5000,  "period": "Monthly"},
    "Subscriptions":        {"amount": 1000,  "period": "Monthly"},
    "Entertainment":        {"amount": 1500,  "period": "Monthly"},
    "Bills & Utilities":    {"amount": 3000,  "period": "Monthly"},
    "Housing & Rent":       {"amount": 15000, "period": "Monthly"},
    "Finance & Investment": {"amount": 10000, "period": "Monthly"},
    "BNPL & Credit":        {"amount": 2000,  "period": "Monthly"},
    "Health & Medical":     {"amount": 2000,  "period": "Monthly"},
    "Education":            {"amount": 2000,  "period": "Monthly"},
    "Travel & Stays":       {"amount": 5000,  "period": "Monthly"},
    "P2P Transfers":        {"amount": 5000,  "period": "Monthly"},
    "Personal Care":        {"amount": 1500,  "period": "Monthly"},
    "Home & Maintenance":   {"amount": 2000,  "period": "Monthly"},
    "Charity & Donations":  {"amount": 500,   "period": "Monthly"},
    "Others":               {"amount": 2000,  "period": "Monthly"},
}

PERIOD_TO_DAYS = {"Daily": 1, "Weekly": 7, "Monthly": 30, "Yearly": 365}


def to_monthly(amount: float, period: str) -> float:
    """Convert any amount to monthly equivalent."""
    return (amount / PERIOD_TO_DAYS.get(period, 30)) * 30


def get_month_range(df: pd.DataFrame, month_str: str):
    """
    Returns start, end, elapsed, total_days, days_remaining.
    Uses actual transaction dates so historical CSVs work correctly.
    """
    period = pd.Period(month_str, freq="M")
    start  = period.start_time.date()
    end    = period.end_time.date()
    total  = (end - start).days + 1

    debits = df[df["type"] == "Debit"].copy()
    debits["date_only"] = debits["date"].dt.date
    in_month = debits[
        (debits["date_only"] >= start) &
        (debits["date_only"] <= end)
    ]

    elapsed = in_month["date_only"].max().day if not in_month.empty else total
    return start, end, elapsed, total, max(total - elapsed, 0)


def get_spend(df: pd.DataFrame, category: str, start: date, end: date) -> float:
    debits = df[df["type"] == "Debit"].copy()
    debits["date_only"] = debits["date"].dt.date
    mask = (
        (debits["category"] == category) &
        (debits["date_only"] >= start) &
        (debits["date_only"] <= end)
    )
    return float(debits.loc[mask, "amount"].sum())


def get_total_spend(df: pd.DataFrame, start: date, end: date) -> float:
    debits = df[df["type"] == "Debit"].copy()
    debits["date_only"] = debits["date"].dt.date
    mask = (debits["date_only"] >= start) & (debits["date_only"] <= end)
    return float(debits.loc[mask, "amount"].sum())


def get_status_color(pct: float) -> tuple:
    """Returns (status_label, hex_color) based on % used."""
    if pct >= 100:   return "Over Budget", "#FF6B6B"
    elif pct >= 80:  return "Warning",     "#FF9F43"
    elif pct >= 50:  return "On Track",    "#FFD93D"
    else:            return "Healthy",     "#6BCB77"


def compute_monthly_overview(
    df: pd.DataFrame,
    monthly_budget: float,
) -> pd.DataFrame:
    """
    For each month in the data, compute total spend vs monthly_budget.
    Returns a DataFrame with one row per month — used for the month color grid.
    """
    months = sorted(df[df["type"] == "Debit"]["month"].unique().tolist())
    rows   = []
    for month_str in months:
        start, end, elapsed, total_days, days_remaining = get_month_range(df, month_str)
        spent = get_total_spend(df, start, end)
        pct   = (spent / monthly_budget * 100) if monthly_budget > 0 else 0
        status, color = get_status_color(pct)
        rows.append({
            "month":          month_str,
            "spent":          round(spent, 2),
            "budget":         monthly_budget,
            "pct_used":       round(pct, 1),
            "status":         status,
            "color":          color,
            "days_remaining": days_remaining,
        })
    return pd.DataFrame(rows)


def compute_budget_status(
    df: pd.DataFrame,
    budgets: Dict[str, dict],
    selected_month: str,
    monthly_budget: float = 0,
) -> pd.DataFrame:
    """
    For each category in selected_month:
    - Gets actual spend from CSV
    - Converts user budget to monthly for comparison
    - Computes status and projection
    """
    start, end, elapsed, total_days, days_remaining = get_month_range(df, selected_month)

    rows = []
    for cat in ALL_CATEGORIES:
        cfg    = budgets.get(cat, DEFAULT_BUDGETS.get(cat, {"amount": 0, "period": "Monthly"}))
        amt    = float(cfg.get("amount", 0))
        per    = cfg.get("period", "Monthly")
        cat_monthly_budget = to_monthly(amt, per)

        spent         = get_spend(df, cat, start, end)
        pct_used      = min((spent / cat_monthly_budget * 100) if cat_monthly_budget > 0 else 0, 999)
        remaining     = cat_monthly_budget - spent
        daily_burn    = spent / max(elapsed, 1)
        projected_eom = spent + daily_burn * days_remaining
        will_breach   = projected_eom > cat_monthly_budget if cat_monthly_budget > 0 else False
        breach_amount = max(projected_eom - cat_monthly_budget, 0)

        gap = cat_monthly_budget - spent
        if daily_burn > 0 and gap > 0:
            days_to_breach = gap / daily_burn
        elif gap <= 0:
            days_to_breach = 0
        else:
            days_to_breach = None

        status, color = get_status_color(pct_used)

        rows.append({
            "category":         cat,
            "budget_amount":    amt,
            "budget_period":    per,
            "monthly_budget":   round(cat_monthly_budget, 2),
            "spent":            round(spent, 2),
            "remaining":        round(remaining, 2),
            "pct_used":         round(pct_used, 1),
            "daily_burn":       round(daily_burn, 2),
            "projected_eom":    round(projected_eom, 2),
            "will_breach":      will_breach,
            "days_to_breach":   round(days_to_breach, 1) if isinstance(days_to_breach, float) else days_to_breach,
            "breach_amount":    round(breach_amount, 2),
            "status":           status,
            "color":            color,
            "days_remaining":   days_remaining,
            "elapsed_days":     elapsed,
            "total_days":       total_days,
        })

    result = pd.DataFrame(rows)
    return result[
        (result["budget_amount"] > 0) | (result["spent"] > 0)
    ].sort_values("pct_used", ascending=False).reset_index(drop=True)


def get_budget_alerts(budget_status: pd.DataFrame) -> list:
    alerts = []
    for _, row in budget_status.iterrows():
        pct = row["pct_used"]
        dtb = row["days_to_breach"]
        if pct >= 100:
            alerts.append(("🔴 Over Budget", row["category"],
                f"Spent ₹{row['spent']:,.0f} against ₹{row['monthly_budget']:,.0f} — "
                f"over by ₹{abs(row['remaining']):,.0f}."))
        elif pct >= 80 and row["will_breach"]:
            alerts.append(("🟠 Breach Incoming", row["category"],
                f"Projected ₹{row['projected_eom']:,.0f} by month end — "
                f"₹{row['breach_amount']:,.0f} over budget."))
        elif row["will_breach"] and isinstance(dtb, float) and dtb <= 7:
            alerts.append(("🟡 Approaching Limit", row["category"],
                f"Budget breach in ~{dtb:.0f} days at ₹{row['daily_burn']:,.0f}/day."))
    return alerts
