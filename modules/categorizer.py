

import json
import re
import os
import pandas as pd
from pathlib import Path


# ── Load category config ───────────────────────────────────────────────────────
_CONFIG_PATH = Path(__file__).parent.parent / "config" / "categories.json"

def _load_categories() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

CATEGORIES = _load_categories()


# ── Keyword → Category reverse index ──────────────────────────────────────────
def _build_keyword_index(categories: dict) -> list:
    """Returns sorted list of (keyword, category) tuples, longest first."""
    index = []
    for cat, data in categories.items():
        for kw in data.get("keywords", []):
            index.append((kw.lower(), cat))
    # Sort by keyword length descending so "big basket" beats "basket"
    return sorted(index, key=lambda x: len(x[0]), reverse=True)

_KW_INDEX = _build_keyword_index(CATEGORIES)


def _clean_description(desc: str) -> str:
    """Remove noise from transaction description for better matching."""
    desc = str(desc).lower().strip()
    # Remove common transaction noise
    noise_patterns = [
        r"upi[/-]?\w*",
        r"ref\s*no[\s:]*\w+",
        r"txn\s*id[\s:]*\w+",
        r"order\s*#?\s*\w+",
        r"\b\d{6,}\b",        # Long numeric IDs
        r"payment\s+to",
        r"payment\s+from",
        r"transfer\s+to",
        r"transfer\s+from",
        r"@\w+",              # UPI handles like @okicici
    ]
    for pat in noise_patterns:
        desc = re.sub(pat, " ", desc, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", desc).strip()


def _categorize_single(description: str, upi_id: str = "") -> str:
    """Assign category to a single transaction."""
    clean_desc = _clean_description(description)
    search_text = clean_desc + " " + str(upi_id).lower()

    for keyword, category in _KW_INDEX:
        if keyword in search_text:
            return category

    return "Others"


def _extract_merchant(description: str) -> str:
    """
    Best-effort merchant name extraction from raw description.
    Returns a cleaned, title-cased merchant name.
    """
    desc = str(description).strip()

    # Known brand patterns — return canonical name
    brand_map = {
        "zomato": "Zomato", "swiggy": "Swiggy", "uber": "Uber",
        "ola": "Ola", "rapido": "Rapido", "amazon": "Amazon",
        "flipkart": "Flipkart", "netflix": "Netflix", "hotstar": "Hotstar",
        "spotify": "Spotify", "bigbasket": "BigBasket", "blinkit": "Blinkit",
        "zepto": "Zepto", "dmart": "DMart", "airtel": "Airtel",
        "jio": "Jio", "irctc": "IRCTC", "phonepe": "PhonePe",
        "paytm": "Paytm", "gpay": "Google Pay", "nykaa": "Nykaa",
        "myntra": "Myntra", "zerodha": "Zerodha", "groww": "Groww",
        "cult": "Cult.fit", "apollo": "Apollo", "medplus": "Medplus",
        "oyo": "OYO", "pvr": "PVR", "bookmyshow": "BookMyShow",
    }
    desc_lower = desc.lower()
    for key, canonical in brand_map.items():
        if key in desc_lower:
            return canonical

    # Generic: take first meaningful word(s), remove IDs and noise
    cleaned = re.sub(r"[#\-_]?\d{4,}", "", desc)   # Remove long numbers
    cleaned = re.sub(r"@\w+", "", cleaned)           # Remove UPI handles
    cleaned = re.sub(r"\b(upi|ref|txn|order|payment|transfer|debit|credit)\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    parts = cleaned.split()
    if parts:
        return " ".join(parts[:3]).title()

    return desc[:30].title()


def categorize_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add 'category' and 'merchant' columns to the DataFrame.
    Only categorizes Debit transactions; Credits get 'Income'.
    """
    df = df.copy()

    df["category"] = df.apply(
        lambda row: "Income" if row["type"] == "Credit" else _categorize_single(
            row["description"], row.get("upi_id", "")
        ),
        axis=1,
    )

    df["merchant"] = df["description"].apply(_extract_merchant)

    return df


def get_category_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a summary DataFrame with spend per category.
    Only includes Debit transactions.
    """
    debits = df[df["type"] == "Debit"].copy()

    summary = (
        debits.groupby("category")
        .agg(
            total_spent=("amount", "sum"),
            transaction_count=("amount", "count"),
            avg_transaction=("amount", "mean"),
            max_transaction=("amount", "max"),
        )
        .reset_index()
        .sort_values("total_spent", ascending=False)
    )

    total = summary["total_spent"].sum()
    summary["percentage"] = (summary["total_spent"] / total * 100).round(1)

    # Attach color and icon from config
    summary["color"] = summary["category"].apply(
        lambda c: CATEGORIES.get(c, {}).get("color", "#B2BEC3")
    )
    summary["icon"] = summary["category"].apply(
        lambda c: CATEGORIES.get(c, {}).get("icon", "📦")
    )

    return summary


def get_top_merchants(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Returns top N merchants by total spend."""
    debits = df[df["type"] == "Debit"].copy()
    return (
        debits.groupby("merchant")
        .agg(total_spent=("amount", "sum"), visits=("amount", "count"))
        .reset_index()
        .sort_values("total_spent", ascending=False)
        .head(n)
    )
