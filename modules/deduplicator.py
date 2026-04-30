import pandas as pd
import numpy as np
from typing import List, Optional
import hashlib

try:
    from rapidfuzz import fuzz
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False

FUZZY_THRESHOLD  = 72
AMOUNT_TOLERANCE = 1.0
DATE_WINDOW_DAYS = 1


def _stable_id(row: pd.Series) -> str:
    key = f"{row['date'].date()}|{row['amount']:.2f}|{str(row['description'])[:40]}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def tag_source(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    df = df.copy()
    df["source"] = source_name
    df["txn_id"] = df.apply(_stable_id, axis=1)
    return df


def merge_accounts(dfs: List[pd.DataFrame], source_names: Optional[List[str]] = None) -> pd.DataFrame:
    if source_names is None:
        source_names = [f"Account {i+1}" for i in range(len(dfs))]
    tagged = [tag_source(df, name) for df, name in zip(dfs, source_names)]
    merged = pd.concat(tagged, ignore_index=True).sort_values("date").reset_index(drop=True)
    return merged


def _fuzzy_match(desc1: str, desc2: str) -> float:
    if not FUZZY_AVAILABLE:
        a = set(str(desc1).lower().split())
        b = set(str(desc2).lower().split())
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b) * 100
    return fuzz.token_sort_ratio(str(desc1).lower(), str(desc2).lower())


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "txn_id" not in df.columns:
        df["txn_id"] = df.apply(_stable_id, axis=1)
    if "source" not in df.columns:
        df["source"] = "Single Account"

    df["is_duplicate"]     = False
    df["duplicate_of"]     = None
    df["duplicate_reason"] = None

    debits     = df[df["type"] == "Debit"].copy()
    dedup_set  = set()
    rows_list  = list(debits.iterrows())

    for pos_i, (i, row_i) in enumerate(rows_list):
        if row_i["txn_id"] in dedup_set:
            continue

        date_i   = pd.Timestamp(row_i["date"])
        amount_i = float(row_i["amount"])
        window   = pd.Timedelta(days=DATE_WINDOW_DAYS)

        for pos_j in range(pos_i + 1, len(rows_list)):
            j, row_j = rows_list[pos_j]

            if row_j["txn_id"] in dedup_set:
                continue

            date_j   = pd.Timestamp(row_j["date"])
            amount_j = float(row_j["amount"])

            if abs(amount_i - amount_j) > AMOUNT_TOLERANCE:
                continue
            if abs(date_i - date_j) > window:
                continue

            score = _fuzzy_match(row_i["description"], row_j["description"])
            merchant_match = (
                str(row_i.get("merchant", "")).lower() == str(row_j.get("merchant", "")).lower()
                and str(row_i.get("merchant", "")) not in ("Unknown", "N/A", "")
            )

            if score >= FUZZY_THRESHOLD or merchant_match:
                keep_i = len(str(row_i["description"])) >= len(str(row_j["description"]))
                dup_idx = j if keep_i else i
                ref_id  = row_i["txn_id"] if keep_i else row_j["txn_id"]
                same_source = row_i.get("source") == row_j.get("source")

                reason = (
                    f"Cross-account duplicate: score {score:.0f}/100"
                    if not same_source
                    else f"Possible re-import: score {score:.0f}/100"
                )

                df.at[dup_idx, "is_duplicate"]     = True
                df.at[dup_idx, "duplicate_of"]     = ref_id
                df.at[dup_idx, "duplicate_reason"] = reason
                dedup_set.add(df.at[dup_idx, "txn_id"])
                break

    return df


def get_dedup_report(df: pd.DataFrame) -> dict:
    dups         = df[df["is_duplicate"] == True]
    cross_source = dups[dups["duplicate_reason"].str.contains("Cross-account", na=False)]
    reimport     = dups[dups["duplicate_reason"].str.contains("re-import", na=False)]
    return {
        "total_duplicates":    len(dups),
        "cross_account_dups":  len(cross_source),
        "reimport_dups":       len(reimport),
        "amount_deduplicated": dups["amount"].sum(),
        "sources":             df["source"].unique().tolist(),
        "duplicate_rows":      dups[["date", "description", "amount", "source", "duplicate_reason"]].copy(),
    }


def get_clean_df(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["is_duplicate"] != True].copy()
