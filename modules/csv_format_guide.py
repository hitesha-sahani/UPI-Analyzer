"""
modules/csv_format_guide.py
───────────────────────────
Uses only native Streamlit components — no unsafe_allow_html blocks
that break inside expanders.
"""

import streamlit as st


def _chip_row(chips: list[tuple[str, bool]]):
    """Render a row of code chips using st.code inline style via columns."""
    cols = st.columns(len(chips))
    for col, (label, highlight) in zip(cols, chips):
        if highlight:
            col.markdown(f"`{label}`")
        else:
            col.caption(f"`{label}`")


def render_csv_guide():

    with st.expander("🛠️  Error after uploading? We got you", expanded=False):

        # ── Warning box ───────────────────────────────────────────────────────
        st.warning(
            "**Most common reason uploads silently fail:** your bank uses "
            "`Withdrawal Amt` or `Deposit Amt` as column names. "
            "The parser doesn't recognise these — rename them to "
            "`Debit Amount` and `Credit Amount` in Excel/Sheets before uploading.",
            icon="⚠️",
        )

        st.divider()

        # ── Required ──────────────────────────────────────────────────────────
        st.markdown("##### 🔴 Required — parser fails without these")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Date**")
            st.caption("Any of these column names work:")
            for name, primary in [("Date", True), ("Txn Date", True),
                                   ("Transaction Date", False), ("Value Date", False),
                                   ("Posting Date", False)]:
                st.markdown(f"`{name}`" + (" ✦" if primary else ""))

        with c2:
            st.markdown("**Amount**")
            st.caption("Any of these column names work:")
            for name, primary in [("Amount", True), ("Dr Amount", True),
                                   ("Cr Amount", True), ("Debit Amount", False),
                                   ("Credit Amount", False), ("Transaction Amount", False)]:
                st.markdown(f"`{name}`" + (" ✦" if primary else ""))

        st.caption("✦ = verified working with your parser")
        st.divider()

        # ── Recommended ───────────────────────────────────────────────────────
        st.markdown("##### 🟡 Recommended — needed for useful analysis")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Debit / Credit flag**")
            st.caption("Without this, all transactions show as Debit")
            for name in ["Type ✦", "DR/CR ✦", "Debit/Credit", "Txn Type", "Transaction Type"]:
                st.markdown(f"`{name}`")

        with c2:
            st.markdown("**Description**")
            st.caption("Used for merchant ID and categorisation")
            for name in ["Description ✦", "Narration ✦", "Particulars",
                         "Details", "Remarks", "Transaction Details", "Note", "Comment"]:
                st.markdown(f"`{name}`")

        st.divider()

        # ── Optional ──────────────────────────────────────────────────────────
        st.markdown("##### 🟢 Optional — unlocks extra features")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**UPI ID**")
            st.caption("Better payee names in merchant review")
            for name in ["UPI ID ✦", "VPA", "UPI Ref", "Reference ID", "UPI Transaction ID"]:
                st.markdown(f"`{name}`")

        with c2:
            st.markdown("**Transaction number**")
            st.caption("Enables cross-account duplicate detection")
            for name in ["Txn No. ✦", "Chq/Ref No ✦", "Ref No", "Reference", "Order ID", "Txn ID"]:
                st.markdown(f"`{name}`")

        st.divider()

        # ── Date formats ──────────────────────────────────────────────────────
        st.markdown("##### 📅 Accepted date formats")
        formats = [
            "DD/MM/YYYY", "DD-MM-YYYY", "YYYY-MM-DD", "MM/DD/YYYY", "DD MMM YYYY",
            "DD Month YYYY", "Mon DD, YYYY", "Month DD, YYYY", "DD/MM/YY", "DD-MM-YY",
        ]
        # display in two rows of 5
        cols = st.columns(5)
        for i, fmt in enumerate(formats):
            cols[i % 5].code(fmt, language=None)

        st.divider()

        # ── Amount formats ────────────────────────────────────────────────────
        st.markdown("##### 💰 Amount column — what works")

        data = {
            "Format": ["Split columns ✅", "Single + type ✅", "Signed values ✅", "₹ symbol / commas ✅"],
            "How": [
                "Separate Dr Amount + Cr Amount columns — merged automatically",
                "One Amount column (positive) + a DR/CR or Type column",
                "Single Amount column with negative values for debits",
                "₹1,234.56 — symbol and commas stripped automatically",
            ]
        }
        st.table(data)

        # ── Quick fix tip ─────────────────────────────────────────────────────
        st.info(
            "💡 **Quick fix:** Open your CSV in Excel or Google Sheets and rename "
            "the headers to match any accepted name above. "
            "Minimum needed: **Date** + any **Amount** column. "
            "Everything else improves the analysis but won't break the upload.",
            icon="💡",
        ) 