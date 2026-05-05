from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.ai_advisor import (
    ANTHROPIC_AVAILABLE,
    STARTER_QUESTIONS,
    chat_stream,
    generate_monthly_summary,
    get_api_client,
)
from modules.pages.common import PageContext


def render(context: PageContext) -> None:
    if not ANTHROPIC_AVAILABLE:
        st.error("Groq SDK not installed. Run: `pip install groq`")
        st.stop()

    client = get_api_client()
    if client is None:
        st.warning("API key not configured. Set GROQ_API_KEY environment variable.")
        st.stop()

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "questions_asked" not in st.session_state:
        st.session_state.questions_asked = 0
    if "last_reset_date" not in st.session_state:
        st.session_state.last_reset_date = pd.Timestamp.now().date()

    if st.session_state.last_reset_date != pd.Timestamp.now().date():
        st.session_state.questions_asked = 0
        st.session_state.last_reset_date = pd.Timestamp.now().date()

    daily_limit = 10
    remaining = daily_limit - st.session_state.questions_asked

    st.markdown(
        """
        <div style='padding: 8px 0 4px;'>
            <div style='font-family:"DM Sans",sans-serif; font-size:1.6rem; font-weight:700; color:#151515;'>
                Ask your money anything
            </div>
            <div style='font-size:0.88rem; color:#6c675f; margin-top:4px; font-family:"DM Sans",sans-serif;'>
                Powered by your actual transaction data · Not generic advice
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    pct = (remaining / daily_limit) * 100
    bar_color = "#1769ff" if remaining > 4 else "#FF9F43" if remaining > 2 else "#FF6B6B"
    st.markdown(
        f"""
        <div style='display:flex; align-items:center; gap:12px; margin:12px 0 20px;'>
            <div style='flex:1; background:#ede8e0; border-radius:99px; height:4px;'>
                <div style='width:{pct}%; height:4px; background:{bar_color}; border-radius:99px; transition:width 0.4s;'></div>
            </div>
            <div style='font-size:0.75rem; color:#6c675f; font-family:"DM Sans",sans-serif; white-space:nowrap;'>
                {remaining} of {daily_limit} questions left today
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if remaining <= 0:
        st.markdown(
            """
            <div style='background:#fff8f0; border:1px solid #FF9F43; border-radius:12px;
                        padding:20px 24px; text-align:center; font-family:"DM Sans",sans-serif;'>
                <div style='font-weight:600; color:#151515;'>You've used all 10 questions today</div>
                <div style='color:#6c675f; font-size:0.88rem; margin-top:4px;'>Come back tomorrow - your limit resets at midnight.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()

    _render_summary_button(client, daily_limit)
    _render_quick_questions()
    _render_quick_question_styles()
    _render_chat_history()
    _stream_pending_reply(client)
    _render_input_bar()


def _render_summary_button(client, daily_limit: int) -> None:
    col_btn, _ = st.columns([1, 3])
    with col_btn:
        gen_summary = st.button(
            "Monthly snapshot",
            use_container_width=True,
            type="secondary",
        )

    if gen_summary and st.session_state.questions_asked < daily_limit:
        with st.spinner(""):
            summary = generate_monthly_summary(client, st.session_state.ai_context)
        st.session_state.questions_asked += 1
        st.markdown(
            f"""
            <div style='background:#f0f4ff; border:1px solid #d0dbff; border-radius:12px;
                        padding:18px 22px; font-family:"DM Sans",sans-serif; font-size:0.9rem;
                        color:#151515; line-height:1.8; margin-bottom:16px;'>
                {summary}
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_quick_questions() -> None:
    st.markdown("<div style='margin:8px 0 10px;'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='font-size:0.75rem; text-transform:uppercase; letter-spacing:0.08em;
                    color:#6c675f; font-family:"DM Sans",sans-serif; margin-bottom:10px;'>
            Quick questions
        </div>
        """,
        unsafe_allow_html=True,
    )

    for row_start in range(0, len(STARTER_QUESTIONS), 4):
        cols = st.columns(4)
        for col_index, col in enumerate(cols):
            question_index = row_start + col_index
            if question_index >= len(STARTER_QUESTIONS):
                continue
            with col:
                if st.button(
                    STARTER_QUESTIONS[question_index],
                    key=f"chip_{question_index}",
                    use_container_width=True,
                ):
                    if st.session_state.questions_asked < 10:
                        st.session_state.chat_history.append(
                            {"role": "user", "content": STARTER_QUESTIONS[question_index]}
                        )
                        st.session_state.questions_asked += 1
                        st.rerun()


def _render_quick_question_styles() -> None:
    st.markdown(
        """
        <style>
        div[data-testid="stHorizontalBlock"] button[kind="secondary"] {
            background: #ffffff !important;
            border: 1px solid #ded9cf !important;
            border-radius: 99px !important;
            color: #151515 !important;
            font-size: 0.8rem !important;
            font-family: "DM Sans", sans-serif !important;
            padding: 6px 14px !important;
            transition: all 0.15s !important;
        }
        div[data-testid="stHorizontalBlock"] button[kind="secondary"]:hover {
            background: #f0f4ff !important;
            border-color: #1769ff !important;
            color: #1769ff !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_chat_history() -> None:
    st.markdown("<div style='margin:20px 0 8px;'></div>", unsafe_allow_html=True)
    if st.session_state.chat_history:
        for message in st.session_state.chat_history:
            if message["role"] == "user":
                st.markdown(
                    f"""
                    <div style='display:flex; justify-content:flex-end; margin-bottom:16px;'>
                        <div style='background:#151515; color:#ffffff; padding:12px 18px;
                                    border-radius:18px 18px 4px 18px; max-width:65%;
                                    font-family:"DM Sans",sans-serif; font-size:0.88rem;
                                    line-height:1.55;'>
                            {message["content"]}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div style='display:flex; justify-content:flex-start; margin-bottom:16px; gap:10px;'>
                        <div style='width:28px; height:28px; border-radius:50%; background:#1769ff;
                                    display:flex; align-items:center; justify-content:center;
                                    font-size:0.7rem; color:white; flex-shrink:0; margin-top:4px;
                                    font-family:"DM Sans",sans-serif; font-weight:700;'>A</div>
                        <div style='background:#ffffff; color:#151515; padding:12px 18px;
                                    border-radius:4px 18px 18px 18px; max-width:70%;
                                    font-family:"DM Sans",sans-serif; font-size:0.88rem;
                                    line-height:1.65; border:1px solid #ede8e0;'>
                            {message["content"]}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.markdown(
            """
            <div style='text-align:center; padding:40px 20px; color:#6c675f;
                        font-family:"DM Sans",sans-serif;'>
                <div style='font-weight:600; color:#151515; font-size:1rem;'>
                    Your financial data is loaded and ready
                </div>
                <div style='font-size:0.85rem; margin-top:6px;'>
                    Pick a quick question above or type anything below
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _stream_pending_reply(client) -> None:
    if not st.session_state.chat_history:
        return
    if st.session_state.chat_history[-1]["role"] != "user":
        return

    last_user_msg = st.session_state.chat_history[-1]["content"]
    history_for_api = st.session_state.chat_history[-10:]

    with st.chat_message("assistant", avatar="💙"):
        response = st.write_stream(
            chat_stream(client, st.session_state.ai_context, history_for_api[:-1], last_user_msg)
        )

    st.session_state.chat_history.append({"role": "assistant", "content": response})
    st.rerun()


def _render_input_bar() -> None:
    if "input_key" not in st.session_state:
        st.session_state.input_key = 0

    st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)
    col_input, col_send, col_clear = st.columns([7, 1.2, 0.9])

    with col_input:
        user_input = st.text_input(
            "chat_input_label",
            placeholder="Ask anything about your spending...",
            label_visibility="collapsed",
            key=f"chat_input_{st.session_state.input_key}",
        )
    with col_send:
        send = st.button("Send ->", type="primary", use_container_width=True)
    with col_clear:
        if st.button("Clear", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.input_key += 1
            st.rerun()

    if send and user_input.strip():
        if st.session_state.questions_asked < 10:
            st.session_state.chat_history.append(
                {"role": "user", "content": user_input.strip()}
            )
            st.session_state.questions_asked += 1
            st.session_state.input_key += 1
            st.rerun()
        else:
            st.warning("You've reached today's limit of 10 questions.")
