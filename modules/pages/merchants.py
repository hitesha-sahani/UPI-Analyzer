from __future__ import annotations

from modules.merchant_review_ui import render_merchant_review
from modules.pages.common import PageContext


def render(context: PageContext) -> None:
    render_merchant_review(
        context.df,
        user_id=context.user_id,
        load_and_process_fn=context.load_and_process_fn,
    )
