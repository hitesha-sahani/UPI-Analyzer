from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st


def format_inr(amount: float) -> str:
    return f"\u20b9{amount:,.0f}"


def apply_app_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap');

        :root {
            --mos-bg: #f6f3ee;
            --mos-panel: #ffffff;
            --mos-panel-soft: #fbf9f5;
            --mos-ink: #1b1a18;
            --mos-muted: #6e685f;
            --mos-line: #dfd8ce;
            --mos-line-strong: #cfc5b8;
            --mos-accent: #8daed4;
            --mos-accent-soft: #edf4fb;
            --mos-accent-strong: #7399c5;
            --mos-shadow: 0 1px 2px rgba(28, 24, 19, 0.06), 0 10px 24px rgba(28, 24, 19, 0.04);
            --mos-radius: 8px;
        }

        html, body, [class*="css"] {
            font-family: "DM Sans", sans-serif;
        }

        .stApp {
            background: var(--mos-bg);
            color: var(--mos-ink);
        }

        .block-container {
            max-width: 1180px;
            padding-top: 1.25rem;
            padding-bottom: 2rem;
        }

        section[data-testid="stSidebar"] {
            background: #fcfbf8;
            border-right: 1px solid var(--mos-line);
        }

        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] div {
            color: var(--mos-ink) !important;
        }

        section[data-testid="stSidebar"] label[data-baseweb="radio"] {
            display: block;
            width: 100%;
        }

        section[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-of-type {
            display: none !important;
        }

        section[data-testid="stSidebar"] label[data-baseweb="radio"] > div:last-of-type {
            width: 100%;
            padding: 10px 14px;
            border-radius: 999px;
            border: 1px solid var(--mos-line);
            background: #ffffff;
            transition: background 0.18s ease, border-color 0.18s ease, color 0.18s ease;
        }

        section[data-testid="stSidebar"] label[data-baseweb="radio"]:hover > div:last-of-type {
            background: #f4efe7;
            border-color: var(--mos-line-strong);
        }

        section[data-testid="stSidebar"] input:checked ~ div:last-of-type {
            background: var(--mos-accent-soft);
            border-color: #d1dceb;
            color: #4f6785;
        }

        .dashboard-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            background: linear-gradient(180deg, #ffffff 0%, #fbf9f5 100%);
            border: 1px solid var(--mos-line);
            border-radius: var(--mos-radius);
            padding: 18px 20px;
            margin: 2px 0 22px;
            box-shadow: var(--mos-shadow);
        }

        .dashboard-brand {
            display: flex;
            align-items: center;
            gap: 12px;
            min-width: 240px;
        }

        .dashboard-logo {
            width: 42px;
            height: 42px;
            border-radius: 8px;
            object-fit: cover;
            border: 1px solid var(--mos-line);
        }

        .dashboard-title {
            color: var(--mos-ink) !important;
            font-size: 1.42rem;
            font-weight: 800;
            line-height: 1.1;
        }

        .dashboard-subtitle {
            color: var(--mos-muted) !important;
            font-size: 0.82rem;
            margin-top: 4px;
        }

        .dashboard-meta {
            display: flex;
            flex-wrap: wrap;
            justify-content: flex-end;
            gap: 8px;
        }

        .header-chip {
            display: flex;
            flex-direction: column;
            gap: 2px;
            min-width: 118px;
            background: #ffffff;
            border: 1px solid var(--mos-line);
            border-radius: 8px;
            padding: 8px 10px;
        }

        .header-chip-label {
            color: var(--mos-muted) !important;
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        .header-chip-value {
            color: var(--mos-ink) !important;
            font-size: 0.88rem;
            font-weight: 700;
            line-height: 1.25;
        }

        .section-header {
            font-size: 1.02rem;
            font-weight: 700;
            color: var(--mos-ink);
            padding: 4px 0 12px;
            border-bottom: 1px solid var(--mos-line);
            margin: 0 0 16px;
            position: relative;
            letter-spacing: 0;
        }

        .section-header::after {
            content: "";
            position: absolute;
            bottom: -1px;
            left: 0;
            width: 32px;
            height: 2px;
            background: var(--mos-accent);
        }

        .kpi-card,
        .money-card,
        .insight-card,
        .action-card,
        .leak-card,
        .surface-card {
            background: var(--mos-panel);
            border: 1px solid var(--mos-line);
            border-radius: var(--mos-radius);
            box-shadow: var(--mos-shadow);
        }

        .kpi-card {
            padding: 18px 20px;
            min-height: 100%;
        }

        .money-card {
            padding: 24px;
            min-height: 230px;
        }

        .insight-card,
        .leak-card,
        .action-card,
        .surface-card {
            padding: 18px 20px;
            margin-bottom: 12px;
        }

        .kpi-card::before,
        .hero::after {
            content: none;
        }

        .kpi-card:hover {
            transform: none;
        }

        .kpi-value {
            color: var(--mos-ink);
            font-family: "DM Sans", sans-serif;
            font-size: 1.55rem;
            font-weight: 800;
            line-height: 1.2;
        }

        .kpi-label,
        .micro-label {
            color: var(--mos-muted);
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }

        .card-title {
            color: var(--mos-ink);
            font-weight: 700;
            font-size: 1rem;
            margin-top: 6px;
        }

        .card-detail {
            color: var(--mos-muted);
            font-size: 0.9rem;
            line-height: 1.55;
            margin-top: 6px;
        }

        .amount-line {
            color: var(--mos-ink);
            font-weight: 800;
            font-size: 1.6rem;
            margin-top: 8px;
        }

        .money-score {
            font-size: 4.4rem;
            line-height: 1;
            color: var(--mos-ink);
            font-weight: 800;
            letter-spacing: 0;
        }

        .action-card {
            background: linear-gradient(180deg, #ffffff 0%, #f6f9ff 100%);
            border-color: #d8e3ef;
        }

        .action-card .card-title {
            color: #58779d;
            font-size: 1.08rem;
        }

        .action-card .micro-label {
            color: #89a0ba;
        }

        .nudge-card {
            background: var(--mos-panel);
            border: 1px solid var(--mos-line);
            border-left: 4px solid var(--mos-accent);
            border-radius: var(--mos-radius);
            padding: 14px 16px;
            margin-bottom: 10px;
            font-size: 0.88rem;
            color: var(--mos-ink);
            line-height: 1.6;
            box-shadow: var(--mos-shadow);
        }

        .mini-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }

        .mini-table td {
            border-bottom: 1px solid var(--mos-line);
            padding: 10px 4px;
            color: var(--mos-ink);
        }

        .mini-table tr:last-child td {
            border-bottom: 0;
        }

        .mini-table td:last-child {
            text-align: right;
            font-weight: 700;
        }

        div[data-testid="stPlotlyChart"],
        div[data-testid="stDataFrame"] {
            background: var(--mos-panel);
            border: 1px solid var(--mos-line);
            border-radius: var(--mos-radius);
            overflow: hidden;
        }

        div[data-testid="stPlotlyChart"] {
            padding: 10px;
        }

        div.stButton > button,
        div[data-testid="stFormSubmitButton"] > button {
            background: var(--mos-accent);
            color: #ffffff;
            border: 1px solid var(--mos-accent);
            border-radius: 8px;
            font-weight: 700;
            min-height: 2.75rem;
            transition: background 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
        }

        div.stButton > button:hover,
        div[data-testid="stFormSubmitButton"] > button:hover {
            background: var(--mos-accent-strong);
            border-color: var(--mos-accent-strong);
            transform: translateY(-1px);
        }

        div.stButton > button[kind="secondary"] {
            background: #ffffff;
            color: var(--mos-ink);
            border-color: var(--mos-line-strong);
        }

        div.stButton > button[kind="secondary"]:hover {
            background: var(--mos-panel-soft);
            border-color: var(--mos-accent);
            color: var(--mos-accent);
        }

        .stTextInput input,
        .stNumberInput input,
        .stSelectbox div[data-baseweb="select"] > div,
        .stMultiSelect div[data-baseweb="select"] > div,
        .stDateInput input,
        [data-testid="stFileUploaderDropzone"] {
            background: #ffffff !important;
            color: var(--mos-ink) !important;
            border: 1px solid var(--mos-line) !important;
            border-radius: 8px !important;
        }

        [data-testid="stFileUploaderDropzone"] {
            background: var(--mos-panel-soft) !important;
        }

        [data-testid="stExpander"] {
            background: var(--mos-panel);
            border: 1px solid var(--mos-line);
            border-radius: 8px;
            box-shadow: var(--mos-shadow);
        }

        [data-testid="stExpander"] details summary p {
            color: var(--mos-ink) !important;
            font-weight: 600;
        }

        div[role="radiogroup"] label[data-baseweb="radio"] {
            display: block;
        }

        div[role="radiogroup"] label[data-baseweb="radio"] > div:first-of-type {
            display: none !important;
        }

        div[role="radiogroup"] label[data-baseweb="radio"] > div:last-of-type {
            background: #ffffff;
            border: 1px solid var(--mos-line);
            border-radius: 999px;
            padding: 8px 14px;
            min-height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.18s ease, border-color 0.18s ease, color 0.18s ease;
        }

        div[role="radiogroup"] label[data-baseweb="radio"]:hover > div:last-of-type {
            background: var(--mos-panel-soft);
            border-color: var(--mos-line-strong);
        }

        div[role="radiogroup"] input:checked ~ div:last-of-type {
            background: var(--mos-accent-soft);
            border-color: #d1dceb;
            color: #4f6785;
        }

        .stAlert {
            border-radius: 8px;
        }

        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-thumb {
            background: #d1c8bc;
            border-radius: 999px;
        }

        ::-webkit-scrollbar-track {
            background: transparent;
        }

        div,
        p,
        span,
        label,
        h1,
        h2,
        h3,
        h4,
        h5,
        h6,
        [data-testid="stMarkdownContainer"],
        [data-testid="stWidgetLabel"] {
            color: var(--mos-ink);
        }

        @media (max-width: 760px) {
            .dashboard-header {
                align-items: flex-start;
                flex-direction: column;
                padding: 16px;
            }

            .dashboard-meta {
                justify-content: flex-start;
                width: 100%;
            }

            .header-chip {
                flex: 1 1 140px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@dataclass
class PageContext:
    df: pd.DataFrame
    merged_raw: pd.DataFrame | None
    stats: dict[str, Any]
    cat_summary: pd.DataFrame
    top_merchants: pd.DataFrame
    insights: dict[str, Any]
    anomaly_info: dict[str, Any]
    leak_cards: list[dict[str, Any]]
    learning_cards: list[dict[str, Any]]
    money_score: dict[str, Any]
    next_action: str
    user_id: str
    load_and_process_fn: Any
