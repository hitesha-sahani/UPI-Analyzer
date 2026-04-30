"""
forecaster.py
-------------
Spend Forecasting — Feature 2

Uses Auto-ARIMA (pmdarima) with statsmodels fallback to forecast
next month's spending per category.

Strategy:
  1. Build monthly time-series per category from transaction history
  2. Fit Auto-ARIMA model (automatically selects p,d,q parameters)
  3. Forecast next N months with 80% + 95% confidence intervals
  4. Fallback: linear trend extrapolation if < 3 data points
  5. Return structured results for chart rendering

Output per category:
  - point forecast (₹)
  - lower_80, upper_80 confidence bounds
  - trend direction (increasing / decreasing / stable)
  - narrative string: "Based on your habits, you'll spend ₹X–₹Y next month"
"""

import pandas as pd
import numpy as np
import warnings
from typing import Dict, Optional, Tuple

warnings.filterwarnings("ignore")  # Suppress ARIMA convergence warnings


# ── Try importing pmdarima; fall back gracefully ───────────────────────────────
try:
    from pmdarima import auto_arima
    ARIMA_AVAILABLE = True
except ImportError:
    ARIMA_AVAILABLE = False

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    ETS_AVAILABLE = True
except ImportError:
    ETS_AVAILABLE = False


# ── Minimum data points needed for ARIMA ──────────────────────────────────────
MIN_ARIMA_POINTS = 4
MIN_ETS_POINTS   = 3


def _build_monthly_series(df: pd.DataFrame, category: str) -> pd.Series:
    """Build monthly spend time-series for a single category."""
    debits = df[(df["type"] == "Debit") & (df["category"] == category)]
    monthly = (
        debits.groupby("month")["amount"]
        .sum()
        .reset_index()
        .rename(columns={"amount": "spend"})
    )
    monthly["period"] = pd.to_datetime(monthly["month"] + "-01")
    monthly = monthly.set_index("period").sort_index()
    return monthly["spend"]


def _next_month_label(series: pd.Series) -> str:
    """Return the next month label after the series ends."""
    last = series.index[-1]
    nxt = (last + pd.DateOffset(months=1))
    return nxt.strftime("%Y-%m")


def _linear_forecast(series: pd.Series, steps: int = 1) -> Tuple[float, float, float]:
    """Simple linear trend forecast when data is sparse. Returns (point, lower, upper)."""
    x = np.arange(len(series))
    y = series.values
    if len(x) < 2:
        point = float(y[-1]) if len(y) > 0 else 0.0
        return point, point * 0.7, point * 1.3

    coeffs = np.polyfit(x, y, 1)
    next_x = len(series) + steps - 1
    point = max(float(np.polyval(coeffs, next_x)), 0)

    # Uncertainty: 20% band around linear forecast
    lower = point * 0.80
    upper = point * 1.20
    return point, lower, upper


def _arima_forecast(series: pd.Series, steps: int = 1) -> Tuple[float, float, float]:
    """Auto-ARIMA forecast. Returns (point, lower_80, upper_80)."""
    model = auto_arima(
        series,
        start_p=0, start_q=0,
        max_p=3,   max_q=3,
        seasonal=False,
        stepwise=True,
        suppress_warnings=True,
        error_action="ignore",
        information_criterion="aic",
    )
    forecast, conf_int = model.predict(n_periods=steps, return_conf_int=True, alpha=0.20)
    point = max(float(forecast[0]), 0)
    lower = max(float(conf_int[0][0]), 0)
    upper = max(float(conf_int[0][1]), 0)
    return point, lower, upper


def _ets_forecast(series: pd.Series, steps: int = 1) -> Tuple[float, float, float]:
    """Holt-Winters ETS fallback. Returns (point, lower_80, upper_80)."""
    model = ExponentialSmoothing(series, trend="add", seasonal=None).fit(
        optimized=True, use_brute=False
    )
    forecast = model.forecast(steps)
    point = max(float(forecast.iloc[0]), 0)
    # ETS doesn't give CI directly — use residual std as proxy
    residuals = series - model.fittedvalues
    std = float(residuals.std()) if residuals.std() > 0 else point * 0.1
    lower = max(point - 1.28 * std, 0)
    upper = point + 1.28 * std
    return point, lower, upper


def _trend_direction(series: pd.Series) -> str:
    """Classify trend from last 3 months."""
    if len(series) < 2:
        return "stable"
    recent = series.iloc[-3:] if len(series) >= 3 else series
    slope = np.polyfit(range(len(recent)), recent.values, 1)[0]
    mean  = recent.mean()
    if mean == 0:
        return "stable"
    pct_slope = slope / mean
    if pct_slope > 0.05:
        return "increasing"
    elif pct_slope < -0.05:
        return "decreasing"
    return "stable"


def _forecast_narrative(
    category: str, point: float, lower: float, upper: float, trend: str
) -> str:
    """Generate human-readable forecast string."""
    trend_phrase = {
        "increasing": "📈 Spending is trending up.",
        "decreasing": "📉 You've been spending less lately.",
        "stable":     "➡️  Spending has been consistent.",
    }.get(trend, "")

    return (
        f"Based on your habits, you'll spend "
        f"**₹{lower:,.0f}–₹{upper:,.0f}** on {category} next month "
        f"(best estimate: ₹{point:,.0f}). {trend_phrase}"
    )


def forecast_all_categories(
    df: pd.DataFrame,
    categories: Optional[list] = None,
    steps: int = 1,
) -> pd.DataFrame:
    """
    Forecast next month's spending for each category.

    Parameters
    ----------
    df         : Full transactions DataFrame
    categories : List of categories to forecast (None = all)
    steps      : How many months ahead to forecast

    Returns
    -------
    DataFrame with columns:
      category, forecast_month, point, lower_80, upper_80,
      trend, narrative, method, history_months
    """
    if categories is None:
        categories = df[df["type"] == "Debit"]["category"].unique().tolist()

    rows = []
    for cat in categories:
        series = _build_monthly_series(df, cat)

        if len(series) == 0:
            continue

        forecast_month = _next_month_label(series)
        trend = _trend_direction(series)
        n = len(series)

        # Choose method based on data availability
        try:
            if n >= MIN_ARIMA_POINTS and ARIMA_AVAILABLE:
                point, lower, upper = _arima_forecast(series, steps)
                method = "Auto-ARIMA"
            elif n >= MIN_ETS_POINTS and ETS_AVAILABLE:
                point, lower, upper = _ets_forecast(series, steps)
                method = "Holt-Winters ETS"
            else:
                point, lower, upper = _linear_forecast(series, steps)
                method = "Linear Trend"
        except Exception:
            point, lower, upper = _linear_forecast(series, steps)
            method = "Linear Trend (fallback)"

        rows.append({
            "category":       cat,
            "forecast_month": forecast_month,
            "point":          round(point, 2),
            "lower_80":       round(lower, 2),
            "upper_80":       round(upper, 2),
            "trend":          trend,
            "narrative":      _forecast_narrative(cat, point, lower, upper, trend),
            "method":         method,
            "history_months": n,
            "history_series": series.tolist(),
            "history_index":  [str(i) for i in series.index.strftime("%Y-%m")],
        })

    return pd.DataFrame(rows).sort_values("point", ascending=False).reset_index(drop=True)


def get_total_forecast(forecast_df: pd.DataFrame) -> dict:
    """Aggregate all category forecasts into a total spend forecast."""
    if forecast_df.empty:
        return {}
    return {
        "month":   forecast_df["forecast_month"].iloc[0],
        "point":   forecast_df["point"].sum(),
        "lower":   forecast_df["lower_80"].sum(),
        "upper":   forecast_df["upper_80"].sum(),
        "narrative": (
            f"Based on your habits, you'll spend "
            f"**₹{forecast_df['lower_80'].sum():,.0f}–"
            f"₹{forecast_df['upper_80'].sum():,.0f}** "
            f"next month (best estimate: ₹{forecast_df['point'].sum():,.0f})."
        ),
    }
