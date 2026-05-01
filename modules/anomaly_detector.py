import pandas as pd
import numpy as np
from scipy import stats


# ── Thresholds ─────────────────────────────────────────────────────────────────
Z_SCORE_THRESHOLD     = 2.5
IQR_MULTIPLIER        = 2.0
ODD_HOUR_START        = 23    # 11 PM — informational only, not scored
ODD_HOUR_END          = 5     # 5 AM  — informational only, not scored
LARGE_ROUND_THRESHOLD = 5000
FREQUENCY_WINDOW_DAYS = 7
FREQUENCY_MULTIPLIER  = 2.5
NEW_MERCHANT_MIN_AMT  = 1000  # Only flag new merchants above this amount
DUPLICATE_WINDOW_DAYS = 2     # Days within which same charge = possible duplicate
DUPLICATE_ROUTINE_MAX = 3     # Combos appearing more than this are routine payments


# Categories where large round amounts are normal (rent, EMI, fees)
ROUND_NUMBER_EXEMPT_CATEGORIES = [
    "Housing & Rent",
    "Education",
    "Insurance",
    "Investment",
    "Loan & EMI",
]


def _zscore_flags(df: pd.DataFrame) -> pd.Series:
    """Flags debits that are unusually large compared to overall spending."""
    debits = df[df["type"] == "Debit"]["amount"]
    if len(debits) < 5:
        return pd.Series(False, index=df.index)

    z = np.abs(stats.zscore(debits, nan_policy="omit"))
    flag = pd.Series(False, index=df.index)
    flag.loc[debits.index] = z > Z_SCORE_THRESHOLD
    return flag


def _iqr_flags(df: pd.DataFrame) -> pd.Series:
    """Flags debits that are outliers within their own category."""
    flag = pd.Series(False, index=df.index)
    debits = df[df["type"] == "Debit"]

    for cat, group in debits.groupby("category"):
        if len(group) < 4:
            continue
        Q1 = group["amount"].quantile(0.25)
        Q3 = group["amount"].quantile(0.75)
        IQR = Q3 - Q1
        upper_bound = Q3 + IQR_MULTIPLIER * IQR
        flag.loc[group[group["amount"] > upper_bound].index] = True

    return flag


def _odd_hour_flags(df: pd.DataFrame) -> pd.Series:
    """
    Flags late-night transactions (11pm–5am).
    Informational only — excluded from anomaly score.
    """
    hour = df["hour"]
    has_time = (
        df["has_time"] if "has_time" in df.columns
        else pd.Series(True, index=df.index)
    )
    return has_time & ((hour >= ODD_HOUR_START) | (hour <= ODD_HOUR_END))


def _round_number_flags(df: pd.DataFrame) -> pd.Series:
    """
    Flags large round amounts (multiples of 500/1000 above ₹5000).
    Exempt categories: rent, EMI, education, insurance, investment.
    """
    is_large  = df["amount"] >= LARGE_ROUND_THRESHOLD
    is_round  = (df["amount"] % 500 == 0) | (df["amount"] % 1000 == 0)
    is_debit  = df["type"] == "Debit"
    is_exempt = df["category"].isin(ROUND_NUMBER_EXEMPT_CATEGORIES)
    return is_large & is_round & is_debit & ~is_exempt


def _new_merchant_flags(df: pd.DataFrame) -> pd.Series:
    """
    Flags first-ever transaction with a merchant, only if amount > ₹1000.
    Small first purchases are ignored as low risk.
    """
    flag = pd.Series(False, index=df.index)
    seen_merchants = set()

    for idx, row in df.sort_values("date").iterrows():
        if row["type"] != "Debit":
            continue
        if row["amount"] < NEW_MERCHANT_MIN_AMT:
            continue
        merchant = row.get("merchant", row["description"])
        if merchant not in seen_merchants:
            seen_merchants.add(merchant)
            flag.at[idx] = True

    return flag


def _frequency_spike_flags(df: pd.DataFrame) -> pd.Series:
    """Flags all transactions on days with 2.5x the usual daily activity."""
    flag = pd.Series(False, index=df.index)
    debits = df[df["type"] == "Debit"].copy()

    if len(debits) < 14:
        return flag

    daily_count = debits.groupby(debits["date"].dt.date)["amount"].count()
    avg_daily   = daily_count.mean()
    spike_dates = set(
        daily_count[daily_count > avg_daily * FREQUENCY_MULTIPLIER].index
    )

    for idx, row in debits.iterrows():
        if row["date"].date() in spike_dates:
            flag.at[idx] = True

    return flag


def _duplicate_transaction_flags(df: pd.DataFrame) -> pd.Series:
    """
    Flags probable duplicate charges — same merchant, same amount, within 2 days.
    Skips merchant+amount combos that appear more than 3 times (routine payments).

    Example:
    - Maid ₹500 daily        → appears 30 times → routine → never flagged
    - Netflix charged twice   → appears 2 times  → flagged
    - UPI double charge ₹2000 → appears 2 times  → flagged
    """
    flag = pd.Series(False, index=df.index)
    debits = df[df["type"] == "Debit"].sort_values("date").copy()
    debits["_merchant"] = debits.apply(
        lambda r: r.get("merchant", r["description"]), axis=1
    )

    # Count occurrences of each merchant+amount combo across full dataset
    combo_counts = debits.groupby(["_merchant", "amount"]).size()

    for idx, row in debits.iterrows():
        merchant = row["_merchant"]
        amount   = row["amount"]
        date     = row["date"]

        # Routine payment — skip entirely
        if combo_counts.get((merchant, amount), 0) > DUPLICATE_ROUTINE_MAX:
            continue

        # Check for same merchant + same amount within 2 days
        duplicates = debits[
            (debits.index != idx) &
            (debits["_merchant"] == merchant) &
            (debits["amount"] == amount) &
            ((debits["date"] - date).abs() <= pd.Timedelta(days=DUPLICATE_WINDOW_DAYS))
        ]

        if not duplicates.empty:
            flag.at[idx] = True

    # Clean up temp column
    debits.drop(columns=["_merchant"], inplace=True)
    return flag


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Runs all detectors and adds anomaly columns to the dataframe.
    odd_hour is computed but excluded from scoring to reduce noise.
    """
    df = df.copy()

    df["is_zscore_anomaly"]  = _zscore_flags(df)
    df["is_iqr_anomaly"]     = _iqr_flags(df)
    df["is_odd_hour"]        = _odd_hour_flags(df)
    df["is_round_number"]    = _round_number_flags(df)
    df["is_new_merchant"]    = _new_merchant_flags(df)
    df["is_frequency_spike"] = _frequency_spike_flags(df)
    df["is_duplicate"]       = _duplicate_transaction_flags(df)

    # odd_hour excluded from scoring — informational only
    scored_flag_map = {
        "is_zscore_anomaly":  "🔺 Unusually large amount",
        "is_iqr_anomaly":     "📊 Outlier in category",
        "is_round_number":    "🔢 Suspicious round amount",
        "is_new_merchant":    "🆕 New merchant (large amount)",
        "is_frequency_spike": "⚡ High activity day",
        "is_duplicate":       "⚠️ Possible duplicate charge",
    }

    def _collect_flags(row):
        flags = [label for col, label in scored_flag_map.items() if row.get(col, False)]
        if row.get("is_odd_hour", False):
            flags.append("🌙 Late-night transaction (info only)")
        return flags

    df["anomaly_flags"] = df.apply(_collect_flags, axis=1)
    df["anomaly_score"] = df.apply(
        lambda row: sum(1 for col in scored_flag_map if row.get(col, False)), axis=1
    )

    def _severity(score: int) -> str:
        if score == 0: return "Clean"
        if score == 1: return "Low"
        if score == 2: return "Medium"
        return "High"

    df["anomaly_severity"] = df["anomaly_score"].apply(_severity)
    return df


def get_anomaly_summary(df: pd.DataFrame) -> dict:
    """Returns aggregate anomaly stats. Counts debit anomalies only."""
    flagged = df[(df["anomaly_score"] > 0) & (df["type"] == "Debit")]

    return {
        "total_flagged"   : len(flagged),
        "high_severity"   : len(df[(df["anomaly_severity"] == "High")   & (df["type"] == "Debit")]),
        "medium_severity" : len(df[(df["anomaly_severity"] == "Medium")  & (df["type"] == "Debit")]),
        "low_severity"    : len(df[(df["anomaly_severity"] == "Low")     & (df["type"] == "Debit")]),
        "flagged_amount"  : flagged["amount"].sum(),
        "top_flagged"     : (
            flagged
            .sort_values("anomaly_score", ascending=False)
            .head(10)[["date", "description", "amount", "anomaly_flags", "anomaly_severity"]]
        ),
    }