
import pandas as pd
import numpy as np
from scipy import stats


# ── Thresholds ─────────────────────────────────────────────────────────────────
Z_SCORE_THRESHOLD     = 2.5   # Flag if |z| > this
IQR_MULTIPLIER        = 2.0   # Flag if > Q3 + multiplier * IQR
ODD_HOUR_START        = 23    # 11 PM
ODD_HOUR_END          = 5     # 5 AM
LARGE_ROUND_THRESHOLD = 5000  # Flag round numbers above this
FREQUENCY_WINDOW_DAYS = 7     # Days to check for frequency spike
FREQUENCY_MULTIPLIER  = 2.5   # Flag if txns in window > multiplier * avg weekly


def _zscore_flags(df: pd.DataFrame) -> pd.Series:
    """Z-score on all debit amounts. Returns boolean Series."""
    debits = df[df["type"] == "Debit"]["amount"]
    if len(debits) < 5:
        return pd.Series(False, index=df.index)

    z = np.abs(stats.zscore(debits, nan_policy="omit"))
    flag = pd.Series(False, index=df.index)
    flag.loc[debits.index] = z > Z_SCORE_THRESHOLD
    return flag


def _iqr_flags(df: pd.DataFrame) -> pd.Series:
    """IQR outlier detection per category."""
    flag = pd.Series(False, index=df.index)
    debits = df[df["type"] == "Debit"]

    for cat, group in debits.groupby("category"):
        if len(group) < 4:
            continue
        Q1 = group["amount"].quantile(0.25)
        Q3 = group["amount"].quantile(0.75)
        IQR = Q3 - Q1
        upper = Q3 + IQR_MULTIPLIER * IQR
        flag.loc[group[group["amount"] > upper].index] = True

    return flag


def _odd_hour_flags(df: pd.DataFrame) -> pd.Series:
    """Flag transactions in late-night / early-morning hours."""
    hour = df["hour"]
    return (hour >= ODD_HOUR_START) | (hour <= ODD_HOUR_END)


def _round_number_flags(df: pd.DataFrame) -> pd.Series:
    """Flag large suspiciously round amounts (multiples of 500 or 1000)."""
    is_large = df["amount"] >= LARGE_ROUND_THRESHOLD
    is_round = (df["amount"] % 500 == 0) | (df["amount"] % 1000 == 0)
    is_debit = df["type"] == "Debit"
    return is_large & is_round & is_debit


def _new_merchant_flags(df: pd.DataFrame) -> pd.Series:
    """Flag first-ever transaction with a merchant as 'new merchant'."""
    flag = pd.Series(False, index=df.index)
    seen_merchants = set()

    for idx, row in df.sort_values("date").iterrows():
        if row["type"] != "Debit":
            continue
        merchant = row.get("merchant", row["description"])
        if merchant not in seen_merchants:
            seen_merchants.add(merchant)
            flag.at[idx] = True

    return flag


def _frequency_spike_flags(df: pd.DataFrame) -> pd.Series:
    """Flag days with unusually high transaction count (rolling 7-day window)."""
    flag = pd.Series(False, index=df.index)
    debits = df[df["type"] == "Debit"].copy()

    if len(debits) < 14:
        return flag

    daily_count = debits.groupby(debits["date"].dt.date)["amount"].count()
    avg_daily = daily_count.mean()

    spike_dates = set(daily_count[daily_count > avg_daily * FREQUENCY_MULTIPLIER].index)

    for idx, row in debits.iterrows():
        if row["date"].date() in spike_dates:
            flag.at[idx] = True

    return flag


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Master function: runs all detectors and adds result columns.

    Adds to DataFrame:
    - is_zscore_anomaly      : bool
    - is_iqr_anomaly         : bool
    - is_odd_hour            : bool
    - is_round_number        : bool
    - is_new_merchant        : bool
    - is_frequency_spike     : bool
    - anomaly_flags          : list of str — readable flag names
    - anomaly_score          : int — count of flags (0 = clean)
    - anomaly_severity       : str — "Low" / "Medium" / "High"
    """
    df = df.copy()

    # Run all detectors
    df["is_zscore_anomaly"]   = _zscore_flags(df)
    df["is_iqr_anomaly"]      = _iqr_flags(df)
    df["is_odd_hour"]         = _odd_hour_flags(df)
    df["is_round_number"]     = _round_number_flags(df)
    df["is_new_merchant"]     = _new_merchant_flags(df)
    df["is_frequency_spike"]  = _frequency_spike_flags(df)

    # Combine into readable flag list
    flag_col_map = {
        "is_zscore_anomaly":  "🔺 Unusually large amount",
        "is_iqr_anomaly":     "📊 Outlier in category",
        "is_odd_hour":        "🌙 Late-night transaction",
        "is_round_number":    "🔢 Suspicious round amount",
        "is_new_merchant":    "🆕 New merchant",
        "is_frequency_spike": "⚡ High activity day",
    }

    def _collect_flags(row):
        flags = []
        for col, label in flag_col_map.items():
            if row.get(col, False):
                flags.append(label)
        return flags

    df["anomaly_flags"] = df.apply(_collect_flags, axis=1)
    df["anomaly_score"] = df["anomaly_flags"].apply(len)

    def _severity(score):
        if score == 0:   return "Clean"
        if score == 1:   return "Low"
        if score == 2:   return "Medium"
        return "High"

    df["anomaly_severity"] = df["anomaly_score"].apply(_severity)

    return df


def get_anomaly_summary(df: pd.DataFrame) -> dict:
    """Returns aggregate stats on detected anomalies."""
    flagged = df[df["anomaly_score"] > 0]

    return {
        "total_flagged": len(flagged),
        "high_severity": len(df[df["anomaly_severity"] == "High"]),
        "medium_severity": len(df[df["anomaly_severity"] == "Medium"]),
        "low_severity": len(df[df["anomaly_severity"] == "Low"]),
        "flagged_amount": flagged[flagged["type"] == "Debit"]["amount"].sum(),
        "top_flagged": flagged[flagged["type"] == "Debit"]
            .sort_values("anomaly_score", ascending=False)
            .head(10)[["date", "description", "amount", "anomaly_flags", "anomaly_severity"]],
    }
