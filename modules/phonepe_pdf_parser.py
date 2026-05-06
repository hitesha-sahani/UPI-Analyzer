"""
modules/phonepe_pdf_parser.py
─────────────────────────────
Tested against actual PhonePe PDF text format:
  "Apr 26, 2026 Paid to NEWME DEBIT ₹1,599"
  "Mar 31, 2026 Received from PIYUSH VYAS CREDIT ₹200"
"""

import re
import io
import pdfplumber
import pandas as pd
import numpy as np


def parse_phonepe_pdf(file_obj) -> pd.DataFrame:
    """
    Accepts a file-like object (st.file_uploader result or open()).
    Returns DataFrame with same schema as parse_csv().
    """
    # ── Extract text ──────────────────────────────────────────────────────────
    raw_bytes = file_obj.read() if hasattr(file_obj, "read") else open(file_obj, "rb").read()

    full_text = ""
    with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

    # Clean null bytes (from emojis in merchant names) and normalise spaces
    full_text = full_text.replace("\x00", "").replace("￾", "")
    full_text = re.sub(r'\s+', ' ', full_text)

    # ── Parse transactions ────────────────────────────────────────────────────
    # Format: "Apr 26, 2026 Paid to NEWME DEBIT ₹1,599"
    #         "Mar 31, 2026 Received from PIYUSH VYAS CREDIT ₹200"
    pattern = re.compile(
        r'([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\s+'   # Date: Apr 26, 2026
        r'(?:Paid to|Received from)\s+'               # Direction (ignored)
        r'(.*?)\s+'                                    # Merchant name
        r'(DEBIT|CREDIT)\s+'                           # Type
        r'₹([\d,]+)',                                  # Amount
        re.IGNORECASE
    )

    # Also capture Transaction ID for upi_id
    txn_id_pattern = re.compile(r'Transaction ID\s+(T\w+)')

    txn_ids = txn_id_pattern.findall(full_text)
    matches = pattern.findall(full_text)

    if not matches:
        raise ValueError(
            "No transactions found. "
            "Make sure this is a PhonePe statement PDF (not scanned/image)."
        )

    rows = []
    for idx, (date_str, merchant, txn_type, amount_str) in enumerate(matches):
        rows.append({
            "date":        date_str.strip(),
            "description": merchant.strip(),
            "amount":      float(amount_str.replace(",", "")),
            "type":        "Debit" if txn_type.upper() == "DEBIT" else "Credit",
            "upi_id":      txn_ids[idx] if idx < len(txn_ids) else "N/A",
        })

    df = pd.DataFrame(rows)

    # ── Normalise to match parse_csv() schema ─────────────────────────────────
    df["date"]    = pd.to_datetime(df["date"], format="%b %d, %Y", errors="coerce")
    df = df.dropna(subset=["date"])
    df = df[df["amount"] > 0]
    df = df.sort_values("date").reset_index(drop=True)

    df["balance"]     = np.nan
    df["month"]       = df["date"].dt.to_period("M").astype(str)
    df["day_of_week"] = df["date"].dt.day_name()
    df["hour"]        = 12   # PhonePe PDF doesn't expose hour in extracted text
    df["week"]        = df["date"].dt.isocalendar().week.astype(int)

    return df