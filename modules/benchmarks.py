

import pandas as pd
import numpy as np
from typing import Tuple



BENCHMARKS = {
    "Tier 1": {
        "Low": {
            "Food & Dining":        3200,
            "Transport":            1800,
            "Shopping":             1500,
            "Groceries":            2800,
            "Entertainment":         600,
            "Health & Medical":      800,
            "Education":             900,
            "Bills & Utilities":    2200,
            "Finance & Investment":  500,
            "Travel & Stays":        400,
            "Others":                800,
        },
        "Mid": {
            "Food & Dining":        6500,
            "Transport":            3200,
            "Shopping":             4500,
            "Groceries":            4200,
            "Entertainment":        1800,
            "Health & Medical":     1500,
            "Education":            2200,
            "Bills & Utilities":    3500,
            "Finance & Investment": 6000,
            "Travel & Stays":       2500,
            "Others":               2000,
        },
        "High": {
            "Food & Dining":       12000,
            "Transport":            6000,
            "Shopping":            10000,
            "Groceries":            7000,
            "Entertainment":        4500,
            "Health & Medical":     3000,
            "Education":            5000,
            "Bills & Utilities":    5000,
            "Finance & Investment":20000,
            "Travel & Stays":       8000,
            "Others":               4000,
        },
    },
    "Tier 2": {
        "Low": {
            "Food & Dining":        2200,
            "Transport":            1200,
            "Shopping":             1000,
            "Groceries":            2200,
            "Entertainment":         400,
            "Health & Medical":      600,
            "Education":             700,
            "Bills & Utilities":    1800,
            "Finance & Investment":  400,
            "Travel & Stays":        300,
            "Others":                600,
        },
        "Mid": {
            "Food & Dining":        4200,
            "Transport":            2200,
            "Shopping":             3000,
            "Groceries":            3200,
            "Entertainment":        1200,
            "Health & Medical":     1200,
            "Education":            1800,
            "Bills & Utilities":    2800,
            "Finance & Investment": 4500,
            "Travel & Stays":       1800,
            "Others":               1500,
        },
        "High": {
            "Food & Dining":        8000,
            "Transport":            4000,
            "Shopping":             7000,
            "Groceries":            5000,
            "Entertainment":        3000,
            "Health & Medical":     2200,
            "Education":            4000,
            "Bills & Utilities":    4000,
            "Finance & Investment":14000,
            "Travel & Stays":       5000,
            "Others":               3000,
        },
    },
    "Tier 3": {
        "Low": {
            "Food & Dining":        1500,
            "Transport":             800,
            "Shopping":              700,
            "Groceries":            1800,
            "Entertainment":         250,
            "Health & Medical":      500,
            "Education":             500,
            "Bills & Utilities":    1400,
            "Finance & Investment":  300,
            "Travel & Stays":        200,
            "Others":                400,
        },
        "Mid": {
            "Food & Dining":        3000,
            "Transport":            1500,
            "Shopping":             2000,
            "Groceries":            2500,
            "Entertainment":         800,
            "Health & Medical":      900,
            "Education":            1500,
            "Bills & Utilities":    2200,
            "Finance & Investment": 3000,
            "Travel & Stays":       1200,
            "Others":               1000,
        },
        "High": {
            "Food & Dining":        5500,
            "Transport":            2800,
            "Shopping":             5000,
            "Groceries":            3800,
            "Entertainment":        2000,
            "Health & Medical":     1800,
            "Education":            3000,
            "Bills & Utilities":    3000,
            "Finance & Investment": 9000,
            "Travel & Stays":       3500,
            "Others":               2000,
        },
    },
}

# Savings rate benchmarks (% of income)
SAVINGS_BENCHMARKS = {
    "Tier 1": {"Low": 8,  "Mid": 18, "High": 28},
    "Tier 2": {"Low": 10, "Mid": 20, "High": 30},
    "Tier 3": {"Low": 12, "Mid": 22, "High": 32},
}


def _infer_income_bracket(monthly_income: float) -> str:
    if monthly_income < 30_000:
        return "Low"
    elif monthly_income <= 75_000:
        return "Mid"
    return "High"


def compute_benchmarks(
    cat_summary: pd.DataFrame,
    months_covered: int,
    city_tier: str = "Tier 1",
    monthly_income: float = 60_000,
) -> pd.DataFrame:
    """
    Compare user's average monthly category spend vs peer benchmarks.

    Returns DataFrame with columns:
      category, user_monthly_avg, benchmark, ratio,
      vs_peers, percentile_label, insight
    """
    bracket = _infer_income_bracket(monthly_income)
    peer_data = BENCHMARKS.get(city_tier, BENCHMARKS["Tier 1"]).get(bracket, {})

    rows = []
    for _, row in cat_summary.iterrows():
        cat = row["category"]
        if cat in ("Income",):
            continue

        user_monthly = row["total_spent"] / max(months_covered, 1)
        benchmark    = peer_data.get(cat, 0)

        if benchmark == 0:
            continue

        ratio = user_monthly / benchmark if benchmark > 0 else 1.0

        # Vs peers label
        if ratio <= 0.5:
            vs_peers = "Way below peers"
            color = "#4ECDC4"
        elif ratio <= 0.8:
            vs_peers = "Below peers"
            color = "#6BCB77"
        elif ratio <= 1.1:
            vs_peers = "In line with peers"
            color = "#FFD93D"
        elif ratio <= 1.5:
            vs_peers = "Above peers"
            color = "#FF9F43"
        else:
            vs_peers = "Well above peers"
            color = "#FF6B6B"

        # Insight
        if ratio > 1.5:
            insight = (
                f"You spend {ratio:.1f}x the {city_tier} {bracket}-income average "
                f"on {cat}. Consider reviewing this category."
            )
        elif ratio < 0.5:
            insight = (
                f"Your {cat} spend is very low vs peers — "
                f"either you're disciplined or under-reporting."
            )
        else:
            insight = f"Your {cat} spending is typical for {city_tier} {bracket}-income households."

        rows.append({
            "category":         cat,
            "user_monthly_avg": round(user_monthly, 2),
            "benchmark":        benchmark,
            "ratio":            round(ratio, 2),
            "vs_peers":         vs_peers,
            "color":            color,
            "insight":          insight,
            "bracket":          bracket,
            "city_tier":        city_tier,
        })

    return pd.DataFrame(rows).sort_values("ratio", ascending=False).reset_index(drop=True)


def get_savings_benchmark(
    savings_rate: float,
    city_tier: str = "Tier 1",
    monthly_income: float = 60_000,
) -> dict:
    """Compare user's savings rate vs peers."""
    bracket   = _infer_income_bracket(monthly_income)
    peer_rate = SAVINGS_BENCHMARKS.get(city_tier, {}).get(bracket, 18)
    diff      = savings_rate - peer_rate

    if diff >= 5:
        label   = "Above average saver 🏆"
        color   = "#4ECDC4"
        message = f"Your savings rate of {savings_rate}% beats the peer average of {peer_rate}% by {diff:.0f} points."
    elif diff >= -2:
        label   = "Average saver 👍"
        color   = "#FFD93D"
        message = f"Your savings rate of {savings_rate}% is in line with the peer average of {peer_rate}%."
    else:
        label   = "Below average saver ⚠️"
        color   = "#FF6B6B"
        message = f"Your savings rate of {savings_rate}% is {abs(diff):.0f} points below the peer average of {peer_rate}%."

    return {
        "user_rate":  savings_rate,
        "peer_rate":  peer_rate,
        "diff":       diff,
        "label":      label,
        "color":      color,
        "message":    message,
        "bracket":    bracket,
        "city_tier":  city_tier,
    }


def get_standout_categories(bench_df: pd.DataFrame, top_n: int = 3) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Return top N overspending and underspending categories vs peers."""
    overspend  = bench_df[bench_df["ratio"] > 1.1].head(top_n)
    underspend = bench_df[bench_df["ratio"] < 0.9].tail(top_n)
    return overspend, underspend
