
import os
import pandas as pd
import streamlit as st
from typing import List, Dict, Generator

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

MODEL      = "llama-3.3-70b-versatile"
MAX_TOKENS = 1024


def _fmt_inr(x: float) -> str:
    if x >= 1_00_000:
        return f"₹{x/1_00_000:.1f}L"
    elif x >= 1000:
        return f"₹{x/1000:.1f}K"
    return f"₹{x:,.0f}"


def build_financial_context(df, cat_summary, insights, anomaly_info) -> str:
    debits  = df[df["type"] == "Debit"]
    credits = df[df["type"] == "Credit"]

    date_start = df["date"].min().strftime("%d %b %Y") if not df.empty else "N/A"
    date_end   = df["date"].max().strftime("%d %b %Y") if not df.empty else "N/A"
    months     = df["month"].nunique()

    monthly_rows = (
        debits.groupby("month")["amount"].sum().reset_index()
        .rename(columns={"amount": "spent"})
    )
    monthly_text = "\n".join(
        f"  {r['month']}: {_fmt_inr(r['spent'])}"
        for _, r in monthly_rows.iterrows()
    )

    cat_lines = [
        f"  {row['category']}: {_fmt_inr(row['total_spent'])} ({row['percentage']}%, {row['transaction_count']} txns)"
        for _, row in cat_summary.iterrows()
        if row["category"] != "Income"
    ]

    top_m = debits.groupby("merchant")["amount"].sum().nlargest(5).reset_index()
    merchant_lines = [f"  {r['merchant']}: {_fmt_inr(r['amount'])}" for _, r in top_m.iterrows()]

    subs = insights.get("subscriptions", pd.DataFrame())
    sub_lines = (
        [f"  {s['merchant']}: ₹{s['monthly_cost']:,.0f}/mo" for _, s in subs.iterrows()]
        if not subs.empty else ["  None detected"]
    )

    savings = insights.get("savings_rate", {})
    vel     = insights.get("spend_velocity", {})
    guilt   = insights.get("guilt_merchant", {})
    wknd    = insights.get("weekend_vs_weekday", {})

    return f"""You are a sharp, empathetic personal finance advisor for Indian households.
Speak directly to the user about THEIR OWN data. Be specific with real numbers. Keep answers under 200 words unless asked for more. Use ₹ for amounts.

=== USER FINANCIAL SUMMARY ===
Period: {date_start} to {date_end} ({months} months, {len(df)} transactions)

TOTALS:
  Spent: {_fmt_inr(debits['amount'].sum())}
  Received: {_fmt_inr(credits['amount'].sum())}
  Savings Rate: {savings.get('rate', 0)}%
  Daily Burn: {_fmt_inr(vel.get('avg_daily', 0))}/day

MONTHLY BREAKDOWN:
{monthly_text}

SPENDING BY CATEGORY:
{chr(10).join(cat_lines)}

TOP MERCHANTS:
{chr(10).join(merchant_lines)}

SUBSCRIPTIONS:
{chr(10).join(sub_lines)}

BEHAVIORAL:
  Guilty pleasure: {guilt.get('merchant', 'N/A')} ({guilt.get('visits', 0)} orders)
  Weekend spend: {wknd.get('weekend_pct', 0)}% of total
  Anomalies flagged: {anomaly_info.get('total_flagged', 0)}
=== END SUMMARY ===
""".strip()


def get_api_client():
    if not GROQ_AVAILABLE:
        return None
    api_key = None
    try:
        api_key = st.secrets.get("GROQ_API_KEY") or st.secrets.get("groq_api_key")
    except Exception:
        pass
    if not api_key:
        api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    return Groq(api_key=api_key)


def chat_once(client, system_prompt: str, history: List[Dict], user_message: str) -> str:
    messages = (
        [{"role": "system", "content": system_prompt}]
        + history
        + [{"role": "user", "content": user_message}]
    )
    response = client.chat.completions.create(
        model=MODEL, messages=messages, max_tokens=MAX_TOKENS, temperature=0.7
    )
    return response.choices[0].message.content


def chat_stream(client, system_prompt: str, history: List[Dict], user_message: str) -> Generator[str, None, None]:
    messages = (
        [{"role": "system", "content": system_prompt}]
        + history
        + [{"role": "user", "content": user_message}]
    )
    stream = client.chat.completions.create(
        model=MODEL, messages=messages, max_tokens=MAX_TOKENS, temperature=0.7, stream=True
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def generate_monthly_summary(client, system_prompt: str) -> str:
    prompt = (
        "Give me a concise financial health report based on my data. "
        "Include: 1) One key win 2) One area of concern 3) One specific action I should take this week. "
        "Use emojis. Keep it under 150 words."
    )
    return chat_once(client, system_prompt, [], prompt)


STARTER_QUESTIONS = [
    "Why did I overspend this month?",
    "Which category should I cut to save ₹2000/month?",
    "How does my food spending compare to last month?",
    "Am I on track to save 20% of my income?",
    "Which subscriptions are not worth keeping?",
    "What's my biggest financial risk right now?",
    "Give me a 30-day challenge to reduce spend by 15%.",
    "Which day of the week am I most impulsive?",
]

# Backward-compat alias used in app.py
ANTHROPIC_AVAILABLE = GROQ_AVAILABLE