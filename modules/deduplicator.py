import pandas as pd
import numpy as np
import hashlib
import re
from typing import Callable, Dict, List, Optional

try:
    from rapidfuzz import fuzz
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False


# ---------------- CONFIG ---------------- #
FUZZY_THRESHOLD = 70
AMOUNT_TOLERANCE = 1.0
DATE_WINDOW_DAYS = 1

REVIEW_PENDING = "Pending"
REVIEW_DUPLICATE = "Duplicate"
REVIEW_KEEP = "Keep"
REVIEW_UNREVIEWED = "Unreviewed"


# ---------------- HELPERS ---------------- #
def _stable_id(row: pd.Series) -> str:
    key = f"{row['date'].date()}|{row['amount']:.2f}|{str(row['description'])[:50]}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def tag_source(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    df = df.copy()
    df["source"] = source_name
    df["txn_id"] = df.apply(_stable_id, axis=1)
    return df


def merge_accounts(
    dfs: List[pd.DataFrame],
    source_names: Optional[List[str]] = None
) -> pd.DataFrame:

    if source_names is None:
        source_names = [f"Account {i+1}" for i in range(len(dfs))]

    tagged = [
        tag_source(df, name)
        for df, name in zip(dfs, source_names)
    ]

    return (
        pd.concat(tagged, ignore_index=True)
        .sort_values("date")
        .reset_index(drop=True)
    )


def _is_real_ref(ref):
    ref = str(ref).strip().lower()

    if ref in ("", "nan", "none", "n/a"):
        return False

    if "@" in ref:   # UPI VPA
        return False

    if len(ref) < 6:
        return False

    return True


def normalize_description(desc):
    desc = str(desc).lower()

    remove_words = [
        "payment",
        "purchase",
        "subscription",
        "monthly",
        "shopping",
        "station",
        "txn",
        "upi",
        "paid",
        "transfer"
    ]

    for word in remove_words:
        desc = desc.replace(word, "")

    desc = re.sub(r'[^a-z0-9\s]', '', desc)
    desc = re.sub(r'\s+', ' ', desc).strip()

    return desc


def fuzzy_score(a, b):
    a = normalize_description(a)
    b = normalize_description(b)

    if not a or not b:
        return 0

    if not FUZZY_AVAILABLE:
        set_a = set(a.split())
        set_b = set(b.split())

        if not set_a or not set_b:
            return 0

        return len(set_a & set_b) / len(set_a | set_b) * 100

    return fuzz.token_sort_ratio(a, b)


# ---------------- REVIEW STATE ---------------- #
def _ensure_review_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    defaults = {
        "is_potential_duplicate": False,
        "is_duplicate": False,
        "duplicate_of": None,
        "duplicate_reason": None,
        "duplicate_pair_id": None,
        "review_status": REVIEW_UNREVIEWED,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    return df


def _flag_duplicate_candidate(
    df: pd.DataFrame,
    duplicate_idx,
    keep_idx,
    pair_id: str,
    reason: str,
) -> None:
    df.at[duplicate_idx, "is_potential_duplicate"] = True
    df.at[duplicate_idx, "is_duplicate"] = False
    df.at[duplicate_idx, "duplicate_of"] = df.at[keep_idx, "txn_id"]
    df.at[duplicate_idx, "duplicate_reason"] = reason
    df.at[duplicate_idx, "review_status"] = REVIEW_PENDING

    df.at[keep_idx, "duplicate_pair_id"] = pair_id
    df.at[duplicate_idx, "duplicate_pair_id"] = pair_id


def _has_real_time(value) -> bool:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        return False
    return any([timestamp.hour, timestamp.minute, timestamp.second, timestamp.microsecond])


def _flag_group_candidates(
    df: pd.DataFrame,
    group: pd.DataFrame,
    reason: str,
    pair_counter: int,
    used_duplicates: set,
) -> int:
    if len(group) <= 1:
        return pair_counter

    if group["source"].nunique() <= 1:
        return pair_counter

    keep_idx = group.index[0]

    for dup_idx in group.index[1:]:
        if df.at[dup_idx, "txn_id"] in used_duplicates:
            continue

        pair_id = f"DUP_{pair_counter}"
        pair_counter += 1

        _flag_duplicate_candidate(
            df,
            duplicate_idx=dup_idx,
            keep_idx=keep_idx,
            pair_id=pair_id,
            reason=reason,
        )
        used_duplicates.add(df.at[dup_idx, "txn_id"])

    return pair_counter


# ---------------- MAIN DEDUP ---------------- #
def deduplicate(df):
    """Detect possible duplicate transactions without removing them.

    The returned DataFrame keeps every row. Suspected duplicates are marked with
    ``is_potential_duplicate=True`` and ``review_status='Pending'``. A later
    review step should mark the row as ``Duplicate`` or ``Keep``.
    """
    df = df.copy()

    if "txn_id" not in df.columns:
        df["txn_id"] = df.apply(_stable_id, axis=1)

    if "source" not in df.columns:
        df["source"] = "Single Account"

    df = _ensure_review_columns(df)
    df["is_potential_duplicate"] = False
    df["is_duplicate"] = False
    df["duplicate_of"] = None
    df["duplicate_reason"] = None
    df["duplicate_pair_id"] = None
    df["review_status"] = REVIEW_UNREVIEWED

    if df["source"].nunique() <= 1:
        return df

    debits = df[df["type"] == "Debit"].copy()
    used_duplicates = set()
    pair_counter = 1

    # ---------------- Stage 1: Exact Ref Match ---------------- #
    if "ref_no" in debits.columns:
        valid_refs = debits[
            debits["ref_no"].apply(_is_real_ref)
        ]

        grouped = valid_refs.groupby(["ref_no", "amount"])

        for (_, _), group in grouped:
            pair_counter = _flag_group_candidates(
                df,
                group,
                "Exact reference match",
                pair_counter,
                used_duplicates,
            )

    # ---------------- Stage 2: Exact Transaction/Timestamp Match ------------- #
    for _, group in debits.groupby("txn_id"):
        pair_counter = _flag_group_candidates(
            df,
            group,
            "Exact transaction ID match",
            pair_counter,
            used_duplicates,
        )

    timed_debits = debits[debits["date"].apply(_has_real_time)]
    for _, group in timed_debits.groupby(["date", "amount"]):
        pair_counter = _flag_group_candidates(
            df,
            group,
            "Exact timestamp and amount match",
            pair_counter,
            used_duplicates,
        )

    # ---------------- Stage 3: Fuzzy Matching ---------------- #
    rows = list(debits.iterrows())

    for pos_i, (i, row_i) in enumerate(rows):

        if row_i["txn_id"] in used_duplicates:
            continue

        for pos_j in range(pos_i + 1, len(rows)):
            j, row_j = rows[pos_j]

            if row_j["txn_id"] in used_duplicates:
                continue

            if row_i["source"] == row_j["source"]:
                continue

            amount_match = (
                abs(float(row_i["amount"]) - float(row_j["amount"]))
                <= AMOUNT_TOLERANCE
            )

            if not amount_match:
                continue

            date_match = (
                abs(
                    pd.Timestamp(row_i["date"]) -
                    pd.Timestamp(row_j["date"])
                ).days <= DATE_WINDOW_DAYS
            )

            if not date_match:
                continue

            score = fuzzy_score(
                row_i["description"],
                row_j["description"]
            )

            merchant_match = (
                str(row_i.get("merchant", "")).lower()
                ==
                str(row_j.get("merchant", "")).lower()
            )

            if score >= FUZZY_THRESHOLD:
                reason = f"Fuzzy duplicate ({score:.0f}% similarity)"

            elif merchant_match:
                reason = "Merchant match duplicate"

            else:
                continue

            pair_id = f"DUP_{pair_counter}"
            pair_counter += 1

            keep_i = len(str(row_i["description"])) >= len(
                str(row_j["description"])
            )

            keep_idx = i if keep_i else j
            dup_idx = j if keep_i else i

            _flag_duplicate_candidate(
                df,
                duplicate_idx=dup_idx,
                keep_idx=keep_idx,
                pair_id=pair_id,
                reason=reason,
            )

            used_duplicates.add(df.at[dup_idx, "txn_id"])
            break

    return df


def apply_manual_review(
    df: pd.DataFrame,
    decisions: Dict[str, str],
) -> pd.DataFrame:
    """Apply user decisions to duplicate candidates.

    ``decisions`` can be keyed by ``duplicate_pair_id`` or by the duplicate
    transaction's ``txn_id``. Values accept ``Duplicate``/``Keep`` as well as
    simple aliases like ``remove`` or ``keep``.
    """
    reviewed = _ensure_review_columns(df)

    normalized = {
        str(key): str(value).strip().lower()
        for key, value in decisions.items()
    }

    candidates = reviewed[reviewed["is_potential_duplicate"] == True]

    for idx, row in candidates.iterrows():
        pair_id = str(row.get("duplicate_pair_id", ""))
        txn_id = str(row.get("txn_id", ""))
        decision = normalized.get(pair_id, normalized.get(txn_id))

        if decision in ("duplicate", "remove", "remove duplicate", "d", "yes", "y"):
            reviewed.at[idx, "is_duplicate"] = True
            reviewed.at[idx, "review_status"] = REVIEW_DUPLICATE
        elif decision in ("keep", "keep both", "not duplicate", "k", "no", "n"):
            reviewed.at[idx, "is_duplicate"] = False
            reviewed.at[idx, "review_status"] = REVIEW_KEEP
        elif row.get("review_status") not in (REVIEW_DUPLICATE, REVIEW_KEEP):
            reviewed.at[idx, "is_duplicate"] = False
            reviewed.at[idx, "review_status"] = REVIEW_PENDING

    return reviewed


def manual_review_console(
    df: pd.DataFrame,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> pd.DataFrame:
    """Prompt through pending duplicate candidates one by one in the console."""
    decisions = {}

    for pair in get_duplicate_pairs(df):
        original = pair["original"]
        duplicate = pair["duplicate"]
        pair_id = pair["pair_id"]

        output_func("\nPotential duplicate: " + str(pair_id))
        output_func(
            "Original:  "
            f"{original.get('date')} | {original.get('description')} | "
            f"{original.get('amount')} | {original.get('source')}"
        )
        output_func(
            "Flagged:   "
            f"{duplicate.get('date')} | {duplicate.get('description')} | "
            f"{duplicate.get('amount')} | {duplicate.get('source')}"
        )
        output_func("Reason:    " + str(duplicate.get("duplicate_reason")))

        while True:
            choice = input_func("Mark as [D]uplicate or [K]eep? ").strip().lower()
            if choice in ("d", "duplicate"):
                decisions[pair_id] = REVIEW_DUPLICATE
                break
            if choice in ("k", "keep"):
                decisions[pair_id] = REVIEW_KEEP
                break
            output_func("Please enter D for Duplicate or K for Keep.")

    return apply_manual_review(df, decisions)


def _read_upi_csv(csv_file, parser: Optional[Callable] = None) -> pd.DataFrame:
    df = parser(csv_file) if parser is not None else pd.read_csv(csv_file)
    df = df.copy()

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    if "type" not in df.columns:
        df["type"] = "Debit"

    return df


def read_and_detect_duplicates(
    csv_a,
    csv_b,
    source_names: Optional[List[str]] = None,
    parser: Optional[Callable] = None,
) -> pd.DataFrame:
    """Read two UPI CSVs, merge them, and flag potential duplicates.

    Pass ``modules.parser.parse_csv`` as ``parser`` when the raw CSVs need the
    app's normal UPI column normalization. Without a parser, ``pd.read_csv`` is
    used directly.
    """
    if source_names is None:
        source_names = ["Account 1", "Account 2"]

    dfs = [
        _read_upi_csv(csv_a, parser=parser),
        _read_upi_csv(csv_b, parser=parser),
    ]
    return deduplicate(merge_accounts(dfs, source_names))
# ---------------- REPORTING ---------------- #
def get_dedup_report(df):
    df = _ensure_review_columns(df)
    flagged = df[df["is_potential_duplicate"] == True]
    confirmed = df[df["is_duplicate"] == True]

    exact_dups = flagged[
        flagged["duplicate_reason"].str.contains(
            "Exact",
            na=False
        )
    ]

    fuzzy_dups = flagged[
        flagged["duplicate_reason"].str.contains(
            "Fuzzy",
            na=False
        )
    ]

    return {
        "total_duplicates": len(flagged),
        "confirmed_duplicates": len(confirmed),
        "pending_review": len(flagged[flagged["review_status"] == REVIEW_PENDING]),
        "kept_after_review": len(flagged[flagged["review_status"] == REVIEW_KEEP]),

        # keep old keys for app compatibility
        "exact_ref_dups": len(exact_dups),
        "fuzzy_dups": len(fuzzy_dups),
        "amount_deduplicated": confirmed["amount"].sum(),
        "amount_flagged": flagged["amount"].sum(),

        "sources": df["source"].unique().tolist(),

        "duplicate_rows": flagged[
            [
                "date",
                "description",
                "amount",
                "source",
                "duplicate_reason"
            ]
        ].copy(),

        "review_rows": flagged[
            [
                "date",
                "description",
                "amount",
                "source",
                "duplicate_reason",
                "review_status",
            ]
        ].copy()
    }

def get_clean_df(
    df,
    decisions: Optional[Dict[str, str]] = None,
    drop_pending: bool = False,
):
    reviewed = apply_manual_review(df, decisions) if decisions else _ensure_review_columns(df)

    if drop_pending:
        return reviewed[reviewed["is_potential_duplicate"] == False].copy()

    return reviewed[reviewed["is_duplicate"] == False].copy()


def get_duplicate_pairs(df):
    df = _ensure_review_columns(df)
    duplicate_rows = df[df["is_potential_duplicate"] == True].copy()

    output = []

    for _, dup_row in duplicate_rows.iterrows():
        original_txn = df[
            df["txn_id"] == dup_row["duplicate_of"]
        ]

        if original_txn.empty:
            continue

        original_txn = original_txn.iloc[0]

        output.append({
            "pair_id": dup_row["duplicate_pair_id"],
            "original": original_txn.to_dict(),
            "duplicate": dup_row.to_dict()
        })

    return output
