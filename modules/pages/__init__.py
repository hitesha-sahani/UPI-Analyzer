from modules.pages import ai_coach, budget, dashboard, financial_timeline, learn, leaks, merchants, transactions

PAGE_RENDERERS = {
    "Dashboard": dashboard.render,
    "Learn": learn.render,
    "Leaks": leaks.render,
    "Timeline": financial_timeline.render,
    "Transactions": transactions.render,
    "Merchants": merchants.render,
    "Budget": budget.render,
    "AI Coach": ai_coach.render,
}
