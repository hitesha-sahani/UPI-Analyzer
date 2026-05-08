import io
import re
import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# COLUMN ALIAS MAPS
# Each template maps canonical field → list of possible CSV headers.
# _normalize_columns scores every template and picks the best match.
# Add new formats here — nothing else needs changing.
# ─────────────────────────────────────────────────────────────────────────────
COLUMN_MAPS = {
    "gpay": {
        "date":        ["date", "transaction date", "txn date"],
        "payee":       ["description", "details", "narration", "note"],
        "amount":      ["amount", "debit/credit amount", "transaction amount"],
        "type":        ["type", "dr/cr", "transaction type"],
        "upi_id":      ["upi id", "vpa", "upi ref"],
        "balance":     ["balance", "closing balance", "available balance"],
    },
    "phonepe": {
        "date":        ["date", "txn date", "transaction date"],
        "payee":       ["transaction details", "description", "details"],
        "amount":      ["amount (inr)", "amount"],
        "type":        ["type", "debit/credit", "cr/dr"],
        "upi_id":      ["upi transaction id", "upi id", "reference id"],
        "balance":     ["balance"],
    },
    "paytm": {
        "date":        ["date", "transaction date"],
        "payee":       ["details", "comment", "description", "remark"],
        "amount":      ["amount", "txn amount"],
        "type":        ["type", "txn type"],
        "upi_id":      ["order id", "txn id", "upi id"],
        "balance":     ["wallet balance", "balance"],
    },
    # Raw UPI switch / bank API export (e.g. data warehouse dumps)
    "raw_upi_export": {
        "date":        ["ts", "timestamp", "created_at", "transaction_time"],
        "payee":       ["payee_name", "merchant_name", "beneficiary", "payee"],
        "amount":      ["amount_inr", "amount_inr_", "inr_amount"],
        "type":        ["txn_type", "transaction_type"],
        "upi_id":      ["payee_vpa", "vpa", "upi_id"],
        "balance":     ["balance"],
    },
    "generic": {
        "date": [
            "date", "txn date", "transaction date",
            "value date", "posting date",
        ],
        "payee": [
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
        "upi_id": [
            "upi id", "vpa", "upi ref",
        ],
        "balance": [
            "balance", "available balance", "closing balance",
        ],
    },
}

# Status column aliases — rows not explicitly "success" are dropped
STATUS_COL_ALIASES = [
    "status", "txn_status", "transaction_status",
    "payment_status", "state", "result",
]

# RRN / reference number aliases — kept separate from upi_id
# These hold values like S96714620, 319810211398, not VPAs
REF_NO_ALIASES = [
    "rrn", "txn no.", "chq/ref no", "ref no", "reference",
    "order id", "txn id", "upi transaction id", "reference id",
]

DATE_FORMATS = [
    "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%m/%d/%Y",
    "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y",
    "%d/%m/%y", "%d-%m-%y",
]


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _find_col(df, aliases):
    """Return the first df column matching any alias (case-insensitive)."""
    lower_cols = {c.lower().strip(): c for c in df.columns}
    for alias in aliases:
        key = alias.lower().strip()
        if key in lower_cols:
            return lower_cols[key]
    return None


def _try_parse_date(val):
    """Try multiple date formats; return parsed datetime or NaT."""
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


def _money_to_number(series):
    """Strip currency symbols / commas and return a numeric Series."""
    cleaned = (
        series.astype(str)
        .str.replace(",",   "", regex=False)
        .str.replace("₹",   "", regex=False)
        .str.replace("Cr.", "", regex=False)
        .str.replace("Dr.", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _normalize_columns(df):
    """
    Score each app template against actual CSV columns.
    Returns the best-matching field → original column name mapping.
    Falls back to broader alias lists for the three critical fields
    (date / payee / amount) if template scoring missed them.
    """
    lower_cols = {c.lower().strip(): c for c in df.columns}
    mapping = {}

    for _, col_map in COLUMN_MAPS.items():
        score = 0
        candidate = {}
        for field, aliases in col_map.items():
            for alias in aliases:
                if alias.lower().strip() in lower_cols:
                    candidate[field] = lower_cols[alias.lower().strip()]
                    score += 1
                    break
        if score >= 2 and len(candidate) > len(mapping):
            mapping = candidate

    # Broad fallbacks so obscure formats still resolve the critical trio
    if "date" not in mapping:
        mapping["date"] = _find_col(df, [
            "ts", "timestamp", "created_at", "transaction_time",
            "txn date", "transaction date", "date", "value date", "posting date",
        ])
    if "payee" not in mapping:
        mapping["payee"] = _find_col(df, [
            "payee_name", "merchant_name", "beneficiary", "payee",
            "description", "details", "narration", "particulars", "remarks",
            "transaction details",
        ])
    if "amount" not in mapping:
        mapping["amount"] = _find_col(df, [
            "amount_inr", "inr_amount",
            "dr amount", "cr amount", "amount",
            "debit amount", "credit amount", "transaction amount",
        ])

    return mapping


def _detect_type(raw_df):
    """
    Determine Debit / Credit per row using 4 fallback strategies:
      1. Explicit type column  (supports Dr/Cr, P2M/P2P, debit/credit keywords)
      2. Separate debit / credit amount columns
      3. Sign of a single amount column
      4. Keywords in payee / description
    """
    # Priority 1 — explicit type column
    type_col = _find_col(raw_df, [
        "type", "transaction type", "dr/cr", "debit/credit",
        "txn type", "txn_type",
    ])
    if type_col:
        raw_type = raw_df[type_col].astype(str).str.lower().str.strip()
        return raw_type.apply(
            lambda x: "Credit"
            if any(w in x for w in ["credit", "cr", "p2p_receive", "refund", "reversal"])
            else "Debit"
        )

    # Priority 2 — separate debit / credit columns
    debit_col  = _find_col(raw_df, ["debit amount", "dr amount", "debit"])
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

    # Priority 4 — description / payee keywords
    desc_col = _find_col(raw_df, [
        "payee_name", "description", "details", "transaction details",
    ])
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
    Return True if val looks like a real transaction reference number.
      Real  : S96714620, TXN123456, 319810211398
      Not   : zomato@icici, N/A, nan, short strings
    """
    val = str(val).strip()
    if val in ("N/A", "", "nan", "None"):
        return False
    if "@" in val:
        return False
    if len(val) < 6:
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def parse_csv(file_obj):
    """
    Accept a file path (str/bytes) or file-like object.
    Handles GPay, PhonePe, Paytm, raw UPI exports, and generic bank CSVs.
    Failed / non-success rows are silently dropped first.

    Output columns (identical to original schema):
        date        — parsed datetime
        description — merchant / person name (falls back to upi_id if absent)
        amount      — INR, always positive float
        type        — "Debit" | "Credit"
        upi_id      — payee VPA e.g. zomato@icici
        ref_no      — reference / trace number (rrn, chq/ref no, etc.)
        balance     — closing balance (NaN if not in source)
        has_time    — True when source timestamp included a time component
        hour        — hour of day; only meaningful when has_time=True
        month       — period string e.g. "2025-10"
        day_of_week — e.g. "Monday"
        week        — ISO week number
    """
    # ── Load ─────────────────────────────────────────────────────────────────
    if isinstance(file_obj, (str, bytes)):
        raw_df = pd.read_csv(file_obj, encoding="utf-8", on_bad_lines="skip")
    else:
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        raw_df = pd.read_csv(io.StringIO(content), on_bad_lines="skip")

    # Clean column names; drop fully-empty rows / columns
    raw_df.columns = raw_df.columns.str.strip()
    raw_df = raw_df.loc[:, ~raw_df.columns.str.contains("^Unnamed")]
    raw_df = raw_df.dropna(axis=1, how="all")
    raw_df = raw_df.dropna(how="all")

    # ── Drop failed transactions ──────────────────────────────────────────────
    # Strict "success"-only filter — pending, failed, reversed all excluded.
    status_col = _find_col(raw_df, STATUS_COL_ALIASES)
    if status_col:
        raw_df = raw_df[
            raw_df[status_col].astype(str).str.strip().str.lower() == "success"
        ].reset_index(drop=True)

    # ── Map columns to canonical names ────────────────────────────────────────
    col_map = _normalize_columns(raw_df)
    df = pd.DataFrame()

    # ── Date (kept as "date" to not break downstream code) ───────────────────
    date_col = col_map.get("date")
    raw_ts = raw_df[date_col] if date_col else pd.Series([""] * len(raw_df))
    df["date"]     = raw_ts.apply(_try_parse_date)
    df["has_time"] = raw_ts.apply(
        lambda x: bool(re.search(r"\d{1,2}:\d{2}", str(x)))
    )

    # ── Description (kept as "description" to not break downstream code) ─────
    # Primary: dedicated payee / description column
    # Fallback: upi_id column (at least shows the VPA)
    payee_col = col_map.get("payee")
    upi_col   = col_map.get("upi_id") or _find_col(raw_df, [
        "payee_vpa", "payer_vpa", "vpa", "upi id", "upi_id",
    ])
    if payee_col:
        df["description"] = raw_df[payee_col].astype(str).str.strip()
    elif upi_col:
        df["description"] = raw_df[upi_col].astype(str).str.strip()
    else:
        df["description"] = "Unknown"

    # ── UPI ID / VPA ──────────────────────────────────────────────────────────
    df["upi_id"] = (
        raw_df[upi_col].astype(str).str.strip()
        if upi_col else pd.Series("N/A", index=raw_df.index)
    )

    # ── Amount ───────────────────────────────────────────────────────────────
    debit_col  = _find_col(raw_df, ["debit amount", "dr amount"])
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

    # ── Type ─────────────────────────────────────────────────────────────────
    df["type"] = _detect_type(raw_df)

    # ── Reference number (kept as "ref_no" to match original schema) ────────
    ref_col = _find_col(raw_df, REF_NO_ALIASES)
    df["ref_no"] = (
        raw_df[ref_col].astype(str).str.strip()
        if ref_col else pd.Series("N/A", index=raw_df.index)
    )

    # ── Balance ──────────────────────────────────────────────────────────────
    bal_col = col_map.get("balance")
    df["balance"] = (
        _money_to_number(raw_df[bal_col])
        if bal_col else pd.Series(np.nan, index=raw_df.index)
    )

    # ── Clean ─────────────────────────────────────────────────────────────────
    df = df.dropna(subset=["date", "amount"])
    df = df[df["amount"] > 0]
    df = df.sort_values("date").reset_index(drop=True)

    # ── Derived time columns ──────────────────────────────────────────────────
    df["month"]       = df["date"].dt.to_period("M").astype(str)
    df["day_of_week"] = df["date"].dt.day_name()
    df["week"]        = df["date"].dt.isocalendar().week.astype(int)
    df["hour"]        = df["date"].dt.hour.astype(int)
    # hour is only meaningful when has_time=True — callers should guard:
    #   df.loc[df["has_time"], "hour"]

    return df


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY STATS
# ─────────────────────────────────────────────────────────────────────────────

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
        "unique_payees":      debits["description"].nunique(),
        "top_payee":          debits.groupby("description")["amount"].sum().idxmax()
                              if not debits.empty else None,
    }