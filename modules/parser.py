import pandas as pd
import numpy as np
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
        "amount": ["amount (inr)", "amount"],
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

    # Added bank compatibility
    "generic": {
        "date": [
            "date",
            "txn date",
            "transaction date",
            "value date",
            "posting date"
        ],

        "description": [
            "description",
            "narration",
            "particulars",
            "details",
            "remarks"
        ],

        "amount": [
            "amount",
            "debit amount",
            "credit amount",
            "transaction amount",
            "dr amount",
            "cr amount"
        ],

        "type": [
            "type",
            "dr/cr",
            "debit/credit",
            "txn type"
        ],

        "upi_id": [
            "upi id",
            "ref no",
            "reference",
            "upi ref",
            "chq/ref no",
            "txn no."
        ],

        "balance": [
            "balance",
            "available balance",
            "closing balance"
        ],
    }
}


DATE_FORMATS = [
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d/%m/%y",
    "%d-%m-%y"
]


def _try_parse_date(val):
    val = str(val).strip()

    for fmt in DATE_FORMATS:
        try:
            return pd.to_datetime(val, format=fmt)
        except:
            pass

    try:
        return pd.to_datetime(val, errors="coerce")
    except:
        return pd.NaT


def _find_col(df, names):
    lower_cols = {c.lower().strip(): c for c in df.columns}

    for name in names:
        if name in lower_cols:
            return lower_cols[name]

    return None


def _normalize_columns(df):
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

    # smarter fallback
    if "date" not in mapping:
        mapping["date"] = _find_col(
            df,
            ["txn date", "transaction date", "date", "value date"]
        )

    if "description" not in mapping:
        mapping["description"] = _find_col(
            df,
            ["description", "details", "narration"]
        )

    if "amount" not in mapping:
        mapping["amount"] = _find_col(
            df,
            ["dr amount", "cr amount", "amount"]
        )

    return mapping


def _money_to_number(series):
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.replace("Cr.", "", regex=False)
        .str.replace("Dr.", "", regex=False)
        .str.strip()
    )

    return pd.to_numeric(cleaned, errors="coerce")


def _detect_type(raw_df):
    # FIRST priority → explicit Type column
    type_col = _find_col(raw_df, [
        "type",
        "transaction type",
        "dr/cr",
        "debit/credit",
        "txn type"
    ])

    if type_col:
        raw_type = raw_df[type_col].astype(str).str.lower().str.strip()

        return raw_type.apply(
            lambda x: "Credit"
            if any(word in x for word in ["credit", "cr"])
            else "Debit"
        )

    # SECOND priority → separate debit/credit columns
    debit_col = _find_col(raw_df, [
        "debit amount",
        "dr amount",
        "debit"
    ])

    credit_col = _find_col(raw_df, [
        "credit amount",
        "cr amount",
        "credit"
    ])

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
            np.where(
                credit_vals.fillna(0) > 0,
                "Credit",
                "Debit"
            ),
            index=raw_df.index
        )

    # THIRD priority → amount sign
    amount_col = _find_col(raw_df, ["amount"])

    if amount_col:
        amounts = _money_to_number(raw_df[amount_col])

        if (amounts < 0).any():
            return amounts.apply(
                lambda x: "Debit" if x < 0 else "Credit"
            )

    # LAST fallback → description keywords
    desc_col = _find_col(raw_df, [
        "description",
        "details",
        "transaction details"
    ])

    if desc_col:
        descriptions = raw_df[desc_col].astype(str).str.lower()

        return descriptions.apply(
            lambda x: "Credit"
            if any(word in x for word in [
                "salary",
                "credited",
                "refund",
                "cashback",
                "received"
            ])
            else "Debit"
        )

    return pd.Series("Debit", index=raw_df.index)

def parse_csv(file_obj):

    if isinstance(file_obj, (str, bytes)):
        raw_df = pd.read_csv(
            file_obj,
            encoding="utf-8",
            on_bad_lines="skip"
        )
    else:
        content = file_obj.read()

        if isinstance(content, bytes):
            content = content.decode(
                "utf-8",
                errors="replace"
            )

        raw_df = pd.read_csv(
            io.StringIO(content),
            on_bad_lines="skip"
        )

    # clean weird bank exports
    raw_df.columns = raw_df.columns.str.strip()
    raw_df = raw_df.loc[:, ~raw_df.columns.str.contains("^Unnamed")]
    raw_df = raw_df.dropna(axis=1, how="all")
    raw_df = raw_df.dropna(how="all")

    col_map = _normalize_columns(raw_df)

    df = pd.DataFrame()

    # date
    date_col = col_map.get("date")
    df["date"] = raw_df[date_col].apply(_try_parse_date)

    # description
    desc_col = col_map.get("description")
    df["description"] = (
        raw_df[desc_col].astype(str).str.strip()
        if desc_col else "Unknown"
    )

    # amount
    debit_col = _find_col(raw_df, ["debit amount", "dr amount"])
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

        df["amount"] = (
            debit_vals.fillna(0).abs() +
            credit_vals.fillna(0).abs()
        )

    else:
        amt_col = col_map.get("amount")

        if amt_col:
            df["amount"] = _money_to_number(raw_df[amt_col]).abs()
        else:
            df["amount"] = np.nan

    # type
    df["type"] = _detect_type(raw_df)

    # upi id
    upi_col = col_map.get("upi_id")

    if upi_col:
        df["upi_id"] = raw_df[upi_col].astype(str)
    else:
        df["upi_id"] = "N/A"

    # balance
    bal_col = col_map.get("balance")

    if bal_col:
        df["balance"] = _money_to_number(raw_df[bal_col])
    else:
        df["balance"] = np.nan

    # clean
    df = df.dropna(subset=["date", "amount"])
    df = df[df["amount"] > 0]

    df = df.sort_values("date").reset_index(drop=True)

    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["day_of_week"] = df["date"].dt.day_name()
    df["hour"] = df["date"].dt.hour.fillna(12).astype(int)
    df["week"] = df["date"].dt.isocalendar().week.astype(int)

    return df


def get_summary_stats(df):
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