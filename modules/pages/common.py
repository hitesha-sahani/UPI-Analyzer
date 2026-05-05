from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


def format_inr(amount: float) -> str:
    return f"₹{amount:,.0f}"


@dataclass
class PageContext:
    df: pd.DataFrame
    merged_raw: pd.DataFrame | None
    stats: dict[str, Any]
    cat_summary: pd.DataFrame
    top_merchants: pd.DataFrame
    insights: dict[str, Any]
    anomaly_info: dict[str, Any]
    leak_cards: list[dict[str, Any]]
    learning_cards: list[dict[str, Any]]
    money_score: dict[str, Any]
    next_action: str
    user_id: str
    load_and_process_fn: Any
