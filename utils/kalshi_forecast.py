"""Transparent baseline probability estimates for 15-minute direction contracts."""

from datetime import datetime, timedelta, timezone
from math import erf, log, sqrt

import pandas as pd


def _normal_cdf(value):
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


def estimate_direction_probability(bars, close_time, now=None):
    """Estimate P(final price >= 15-minute starting price) from minute bars."""
    if not isinstance(bars, pd.DataFrame) or len(bars) < 20:
        raise ValueError("At least 20 one-minute bars are required for a forecast.")
    close_at = datetime.fromisoformat(str(close_time).replace("Z", "+00:00"))
    now = now or datetime.now(timezone.utc)
    start_at = close_at - timedelta(minutes=15)
    usable = bars.dropna(subset=["Time", "Close"]).copy()
    usable["Time"] = pd.to_datetime(usable["Time"], utc=True)
    before_start = usable[usable["Time"] <= start_at]
    if before_start.empty:
        raise ValueError("The contract starting price is not available yet.")

    start_price = float(before_start.iloc[-1]["Close"])
    current_price = float(usable.iloc[-1]["Close"])
    log_returns = usable["Close"].astype(float).map(log).diff().dropna().tail(60)
    minute_volatility = max(float(log_returns.std()), 0.00005)
    remaining_minutes = max((close_at - now).total_seconds() / 60, 0.25)
    distance = log(current_price / start_price)
    standardized = distance / (minute_volatility * sqrt(remaining_minutes))
    probability = min(0.98, max(0.02, _normal_cdf(standardized)))
    return {
        "probability_yes": probability,
        "start_price": start_price,
        "current_price": current_price,
        "move_percent": (current_price / start_price - 1) * 100,
        "minute_volatility": minute_volatility,
        "minutes_remaining": remaining_minutes,
        "method": "Volatility-adjusted distance baseline",
        "data_provider": bars.attrs.get("provider", "Unknown"),
    }


def forecast_decision(forecast_probability, yes_ask, no_ask, minimum_edge=0.05):
    """Return YES, NO, or NO TRADE after price and safety-margin comparison."""
    yes_edge = float(forecast_probability) - float(yes_ask)
    no_edge = (1.0 - float(forecast_probability)) - float(no_ask)
    if yes_edge >= minimum_edge and yes_edge >= no_edge:
        return {"decision": "PAPER YES", "edge": yes_edge}
    if no_edge >= minimum_edge:
        return {"decision": "PAPER NO", "edge": no_edge}
    return {"decision": "NO TRADE", "edge": max(yes_edge, no_edge)}
