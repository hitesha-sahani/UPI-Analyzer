from modules.pages import ai_coach, budget, dashboard, learn, leaks, merchants, transactions

PAGE_RENDERERS = {
    "Dashboard": dashboard.render,
    "Learn": learn.render,
    "Leaks": leaks.render,
    "Transactions": transactions.render,
    "Merchants": merchants.render,
    "Budget": budget.render,
    "AI Coach": ai_coach.render,
}
