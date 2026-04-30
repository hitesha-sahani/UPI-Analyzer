
import pandas as pd
import numpy as np
from datetime import datetime
import re
import io

COLUMN_MAPS = {
    "gpay": {
        "date": ["date", "transaction date", "txn date"],
        "description": ["description", "details", "narration", "note"],
        "amount": ["amount", "debit/credit amount", "transaction amount"],
        "type": ["type", "dr/cr", "transaction type"],
        "upi_id": ["upi id", "vpa", "upi ref"],
        "balance": ["balance", "closing balance", "available balance"],
    },
    "phonepe": {
        "date": ["date", "txn date", "transaction date"],
        "description": ["transaction details", "description", "details"],
        "amount": ["amount (inr)", "amount", "debit amount", "credit amount"],
        "type": ["type", "debit/credit", "cr/dr"],
        "upi_id": ["upi transaction id", "upi id", "reference id"],
        "balance": ["balance"],
    },
    "paytm": {
        "date": ["date", "transaction date"],
        "description": ["details", "comment", "description", "remark"],
        "amount": ["amount", "txn amount"],
        "type": ["type", "txn type"],
        "upi_id": ["order id", "txn id", "upi id"],
        "balance": ["wallet balance", "balance"],
    },
    "generic": {
        "date": ["date", "txn date", "value date", "posting date"],
        "description": ["description", "narration", "particulars", "details", "remarks"],
        "amount": ["amount", "debit amount", "credit amount", "transaction amount"],
        "type": ["type", "dr/cr", "debit/credit", "txn type"],
        "upi_id": ["upi id", "ref no", "reference", "upi ref", "chq/ref no"],
        "balance": ["balance", "available balance", "closing balance"],
    },
}

DATE_FORMATS = [
    "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%m/%d/%Y",
    "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y",
    "%d/%m/%y", "%d-%m-%y", "%Y/%m/%d",
]


def _try_parse_date(val):
    """Try multiple date formats and return a datetime or NaT."""
    val = str(val).strip()
    for fmt in DATE_FORMATS:
        try:
            return pd.to_datetime(val, format=fmt)
        except Exception:
            pass
    try:
        return pd.to_datetime(val, infer_datetime_format=True)
    except Exception:
        return pd.NaT


def _normalize_columns(df: pd.DataFrame) -> dict:
    """
    Detect which columns in df correspond to standard fields.
    Returns a mapping {standard_field: actual_col_name}.
    """
    lower_cols = {c.lower().strip(): c for c in df.columns}
    mapping = {}

    for source, col_map in COLUMN_MAPS.items():
        score = 0
        candidate = {}
        for field, aliases in col_map.items():
            for alias in aliases:
                if alias in lower_cols:
                    candidate[field] = lower_cols[alias]
                    score += 1
                    break
        if score >= 2 and len(candidate) > len(mapping):
            mapping = candidate

    # Fallback: try to infer by position for very simple CSVs
    if "date" not in mapping and len(df.columns) >= 3:
        mapping["date"] = df.columns[0]
    if "description" not in mapping and len(df.columns) >= 3:
        mapping["description"] = df.columns[1]
    if "amount" not in mapping and len(df.columns) >= 3:
        mapping["amount"] = df.columns[2]

    return mapping


def _detect_debit_credit(df: pd.DataFrame, amount_col: str, type_col: str = None) -> pd.Series:
    """
    Determine transaction type (Debit / Credit) from the data.
    Handles: separate type col, negative values = debit, keyword sniff.
    """
    if type_col and type_col in df.columns:
        raw = df[type_col].astype(str).str.lower().str.strip()
        result = raw.map(lambda x: "Credit" if any(k in x for k in ["cr", "credit", "received"]) else "Debit")
        return result

    # Fall back to sign of amount
    nums = pd.to_numeric(df[amount_col].astype(str).str.replace(",", ""), errors="coerce")
    return nums.apply(lambda x: "Credit" if (not pd.isna(x) and x > 0) else "Debit")


def parse_csv(file_obj) -> pd.DataFrame:
    """
    Main entry point. Accepts a file-like object or file path.
    Returns a clean, normalized DataFrame.
    """
    # ── Read raw CSV ───────────────────────────────────────────────────────────
    if isinstance(file_obj, (str, bytes)):
        raw_df = pd.read_csv(file_obj, encoding="utf-8", on_bad_lines="skip")
    else:
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        raw_df = pd.read_csv(io.StringIO(content), on_bad_lines="skip")

    raw_df.columns = raw_df.columns.str.strip()
    raw_df = raw_df.dropna(how="all")

    # ── Detect column mapping ──────────────────────────────────────────────────
    col_map = _normalize_columns(raw_df)

    # ── Build standardized DataFrame ──────────────────────────────────────────
    df = pd.DataFrame()

    # Date
    date_col = col_map.get("date", raw_df.columns[0])
    df["date"] = raw_df[date_col].apply(_try_parse_date)

    # Description
    desc_col = col_map.get("description", None)
    if desc_col:
        df["description"] = raw_df[desc_col].astype(str).str.strip()
    else:
        df["description"] = "Unknown"

    # Amount
    amt_col = col_map.get("amount", None)
    if amt_col:
        amt_str = raw_df[amt_col].astype(str).str.replace(",", "").str.replace("₹", "").str.strip()
        df["amount"] = pd.to_numeric(amt_str, errors="coerce").abs()
    else:
        df["amount"] = np.nan

    # Type
    type_col = col_map.get("type", None)
    df["type"] = _detect_debit_credit(raw_df, amt_col or raw_df.columns[2], type_col)

    # UPI ID
    upi_col = col_map.get("upi_id", None)
    df["upi_id"] = raw_df[upi_col].astype(str).str.strip() if upi_col else "N/A"

    # Balance
    bal_col = col_map.get("balance", None)
    if bal_col:
        bal_str = raw_df[bal_col].astype(str).str.replace(",", "").str.replace("₹", "").str.strip()
        df["balance"] = pd.to_numeric(bal_str, errors="coerce")
    else:
        df["balance"] = np.nan

    # ── Clean ──────────────────────────────────────────────────────────────────
    df = df.dropna(subset=["date", "amount"])
    df = df[df["amount"] > 0]
    df = df.sort_values("date").reset_index(drop=True)

 
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["day_of_week"] = df["date"].dt.day_name()
    df["hour"] = df["date"].dt.hour.fillna(12).astype(int)
    df["week"] = df["date"].dt.isocalendar().week.astype(int)

    return df


def get_summary_stats(df: pd.DataFrame) -> dict:
    """Return high-level summary statistics from parsed DataFrame."""
    debits = df[df["type"] == "Debit"]
    credits = df[df["type"] == "Credit"]

    return {
        "total_transactions": len(df),
        "total_spent": debits["amount"].sum(),
        "total_received": credits["amount"].sum(),
        "avg_transaction": debits["amount"].mean(),
        "max_transaction": debits["amount"].max(),
        "min_transaction": debits["amount"].min(),
        "date_range_start": df["date"].min(),
        "date_range_end": df["date"].max(),
        "months_covered": df["month"].nunique(),
        "unique_merchants": debits["description"].nunique(),
    }
