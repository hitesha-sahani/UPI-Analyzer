import pandas as pd
import numpy as np
import re
import io

# ── Column name aliases per UPI app / bank format ─────────────────────────────
COLUMN_MAPS = {
    "gpay": {
        "date":        ["date", "transaction date", "txn date"],
        "description": ["description", "details", "narration", "note"],
        "amount":      ["amount", "debit/credit amount", "transaction amount"],
        "type":        ["type", "dr/cr", "transaction type"],
        "upi_id":      ["upi id", "vpa", "upi ref"],
        "balance":     ["balance", "closing balance", "available balance"],
    },

    "phonepe": {
        "date":        ["date", "txn date", "transaction date"],
        "description": ["transaction details", "description", "details"],
        "amount":      ["amount (inr)", "amount"],
        "type":        ["type", "debit/credit", "cr/dr"],
        "upi_id":      ["upi transaction id", "upi id", "reference id"],
        "balance":     ["balance"],
    },

    "paytm": {
        "date":        ["date", "transaction date"],
        "description": ["details", "comment", "description", "remark"],
        "amount":      ["amount", "txn amount"],
        "type":        ["type", "txn type"],
        "upi_id":      ["order id", "txn id", "upi id"],
        "balance":     ["wallet balance", "balance"],
    },

    "generic": {
        "date": [
            "date", "txn date", "transaction date",
            "value date", "posting date",
        ],
        "description": [
            "description", "narration", "particulars",
            "details", "remarks",
        ],
        "amount": [
            "amount", "debit amount", "credit amount",
            "transaction amount", "dr amount", "cr amount",
        ],
        "type": [
            "type", "dr/cr", "debit/credit", "txn type",
        ],
        # NOTE: upi_id here only maps to actual UPI VPA columns.
        # Reference/txn numbers are handled separately via ref_no column.
        "upi_id": [
            "upi id", "vpa", "upi ref",
        ],
        "balance": [
            "balance", "available balance", "closing balance",
        ],
    },
}

# Reference number column names — kept separate from upi_id
# These contain values like S96714620, TXN123456, not VPAs like zomato@icici
REF_NO_ALIASES = [
    "txn no.", "chq/ref no", "ref no", "reference",
    "order id", "txn id", "upi transaction id", "reference id",
]

DATE_FORMATS = [
    "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%m/%d/%Y",
    "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y",
    "%d/%m/%y", "%d-%m-%y",
]


def _try_parse_date(val):
    """Try multiple date formats and return parsed datetime or NaT."""
    val = str(val).strip()
    for fmt in DATE_FORMATS:
        try:
            return pd.to_datetime(val, format=fmt)
        except Exception:
            pass
    try:
        return pd.to_datetime(val, errors="coerce")
    except Exception:
        return pd.NaT


def _find_col(df, names):
    """Find first matching column name from a list of aliases (case-insensitive)."""
    lower_cols = {c.lower().strip(): c for c in df.columns}
    for name in names:
        if name in lower_cols:
            return lower_cols[name]
    return None


def _normalize_columns(df):
    """
    Score each app template against actual CSV columns.
    Returns the best-matching field → column mapping.
    Falls back to positional guesses for date/description/amount.
    """
    lower_cols = {c.lower().strip(): c for c in df.columns}
    mapping = {}

    for _, col_map in COLUMN_MAPS.items():
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

    # Smarter fallbacks if template scoring missed key columns
    if "date" not in mapping:
        mapping["date"] = _find_col(
            df, ["txn date", "transaction date", "date", "value date"]
        )
    if "description" not in mapping:
        mapping["description"] = _find_col(
            df, ["description", "details", "narration"]
        )
    if "amount" not in mapping:
        mapping["amount"] = _find_col(
            df, ["dr amount", "cr amount", "amount"]
        )

    return mapping


def _money_to_number(series):
    """Strip currency symbols and commas, return numeric series."""
    cleaned = (
        series.astype(str)
        .str.replace(",",  "", regex=False)
        .str.replace("₹",  "", regex=False)
        .str.replace("Cr.", "", regex=False)
        .str.replace("Dr.", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _detect_type(raw_df):
    """
    Determine Debit/Credit for each row using 4 fallback strategies:
    1. Explicit type column
    2. Separate debit/credit amount columns
    3. Sign of single amount column
    4. Keywords in description
    """
    # Priority 1 — explicit type column
    type_col = _find_col(raw_df, [
        "type", "transaction type", "dr/cr", "debit/credit", "txn type"
    ])
    if type_col:
        raw_type = raw_df[type_col].astype(str).str.lower().str.strip()
        return raw_type.apply(
            lambda x: "Credit"
            if any(w in x for w in ["credit", "cr"])
            else "Debit"
        )

    # Priority 2 — separate debit/credit columns
    debit_col  = _find_col(raw_df, ["debit amount",  "dr amount",  "debit"])
    credit_col = _find_col(raw_df, ["credit amount", "cr amount", "credit"])
    if debit_col or credit_col:
        debit_vals = (
            _money_to_number(raw_df[debit_col])
            if debit_col else pd.Series(0, index=raw_df.index)
        )
        credit_vals = (
            _money_to_number(raw_df[credit_col])
            if credit_col else pd.Series(0, index=raw_df.index)
        )
        return pd.Series(
            np.where(credit_vals.fillna(0) > 0, "Credit", "Debit"),
            index=raw_df.index,
        )

    # Priority 3 — sign of amount
    amount_col = _find_col(raw_df, ["amount"])
    if amount_col:
        amounts = _money_to_number(raw_df[amount_col])
        if (amounts < 0).any():
            return amounts.apply(lambda x: "Debit" if x < 0 else "Credit")

    # Priority 4 — description keywords
    desc_col = _find_col(raw_df, ["description", "details", "transaction details"])
    if desc_col:
        descriptions = raw_df[desc_col].astype(str).str.lower()
        return descriptions.apply(
            lambda x: "Credit"
            if any(w in x for w in ["salary", "credited", "refund", "cashback", "received"])
            else "Debit"
        )

    return pd.Series("Debit", index=raw_df.index)


def _is_real_ref(val: str) -> bool:
    """
    Check if a value looks like a real transaction reference number.
    Real refs: S96714620, TXN123456, IN2401234567
    Not refs: zomato@icici, N/A, nan, short strings
    """
    val = str(val).strip()
    if val in ("N/A", "", "nan", "None", "nan"):
        return False
    if "@" in val:
        # UPI VPA like zomato@icici — not a reference number
        return False
    if len(val) < 6:
        return False
    return True


def parse_csv(file_obj):
    """
    Main entry point. Accepts file path (str) or file-like object.
    Returns a clean normalized DataFrame with these columns:
        date, description, amount, type, upi_id, ref_no,
        balance, month, day_of_week, hour, has_time, week
    """
    # ── Read raw CSV ───────────────────────────────────────────────────────────
    if isinstance(file_obj, (str, bytes)):
        raw_df = pd.read_csv(file_obj, encoding="utf-8", on_bad_lines="skip")
    else:
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        raw_df = pd.read_csv(io.StringIO(content), on_bad_lines="skip")

    # Clean column names and drop empty rows/cols
    raw_df.columns = raw_df.columns.str.strip()
    raw_df = raw_df.loc[:, ~raw_df.columns.str.contains("^Unnamed")]
    raw_df = raw_df.dropna(axis=1, how="all")
    raw_df = raw_df.dropna(how="all")

    col_map = _normalize_columns(raw_df)
    df = pd.DataFrame()

    # ── Date ──────────────────────────────────────────────────────────────────
    date_col = col_map.get("date")
    raw_date_series = raw_df[date_col] if date_col else pd.Series([""] * len(raw_df))
    df["date"] = raw_date_series.apply(_try_parse_date)

    # has_time: True only if the raw date string contains a time component
    # This prevents transactions without timestamps from being flagged as late-night
    df["has_time"] = raw_date_series.apply(
        lambda x: bool(re.search(r"\d{1,2}:\d{2}", str(x)))
    )

    # ── Description ───────────────────────────────────────────────────────────
    desc_col = col_map.get("description")
    df["description"] = (
        raw_df[desc_col].astype(str).str.strip()
        if desc_col else "Unknown"
    )

    # ── Amount ────────────────────────────────────────────────────────────────
    debit_col  = _find_col(raw_df, ["debit amount",  "dr amount"])
    credit_col = _find_col(raw_df, ["credit amount", "cr amount"])

    if debit_col or credit_col:
        debit_vals = (
            _money_to_number(raw_df[debit_col])
            if debit_col else pd.Series(0, index=raw_df.index)
        )
        credit_vals = (
            _money_to_number(raw_df[credit_col])
            if credit_col else pd.Series(0, index=raw_df.index)
        )
        df["amount"] = debit_vals.fillna(0).abs() + credit_vals.fillna(0).abs()
    else:
        amt_col = col_map.get("amount")
        df["amount"] = (
            _money_to_number(raw_df[amt_col]).abs()
            if amt_col else pd.Series(np.nan, index=raw_df.index)
        )

    # ── Type ──────────────────────────────────────────────────────────────────
    df["type"] = _detect_type(raw_df)

    # ── UPI ID (VPA only — merchant handles like zomato@icici) ────────────────
    upi_col = col_map.get("upi_id")
    df["upi_id"] = (
        raw_df[upi_col].astype(str).str.strip()
        if upi_col else "N/A"
    )

    # ── Reference number (txn ref like S96714620) — separate from UPI ID ──────
    # Used by deduplicator for exact cross-account duplicate matching
    ref_col = _find_col(raw_df, REF_NO_ALIASES)
    if ref_col:
        df["ref_no"] = raw_df[ref_col].astype(str).str.strip()
    else:
        df["ref_no"] = "N/A"

    # ── Balance ───────────────────────────────────────────────────────────────
    bal_col = col_map.get("balance")
    df["balance"] = (
        _money_to_number(raw_df[bal_col])
        if bal_col else pd.Series(np.nan, index=raw_df.index)
    )

    # ── Clean ─────────────────────────────────────────────────────────────────
    df = df.dropna(subset=["date", "amount"])
    df = df[df["amount"] > 0]
    df = df.sort_values("date").reset_index(drop=True)

    # ── Derived time columns ───────────────────────────────────────────────────
    df["month"]       = df["date"].dt.to_period("M").astype(str)
    df["day_of_week"] = df["date"].dt.day_name()
    df["week"]        = df["date"].dt.isocalendar().week.astype(int)

    # hour: use actual hour from timestamp
    # has_time guards against treating midnight (hour=0) as late-night
    # since most CSVs don't include time — they all parse as 00:00
    df["hour"] = df["date"].dt.hour.astype(int)

    return df


def get_summary_stats(df: pd.DataFrame) -> dict:
    """Return high-level summary statistics from a parsed DataFrame."""
    debits  = df[df["type"] == "Debit"]
    credits = df[df["type"] == "Credit"]

    return {
        "total_transactions": len(df),
        "total_spent":        debits["amount"].sum(),
        "total_received":     credits["amount"].sum(),
        "avg_transaction":    debits["amount"].mean(),
        "max_transaction":    debits["amount"].max(),
        "min_transaction":    debits["amount"].min(),
        "date_range_start":   df["date"].min(),
        "date_range_end":     df["date"].max(),
        "months_covered":     df["month"].nunique(),
        "unique_merchants":   debits["description"].nunique(),
    }