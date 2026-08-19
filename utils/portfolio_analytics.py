"""Pure calculation helpers for paper-portfolio performance and risk."""

import pandas as pd


def enrich_position_rows(position_rows, portfolio_value):
    """Add cost basis, allocation, and P/L percentages to position rows."""
    portfolio_value = float(portfolio_value)
    enriched = []

    for row in position_rows:
        item = dict(row)
        shares = int(item["Shares"])
        average_cost = float(item["Average Cost"])
        market_value = float(item["Market Value"])
        profit = float(item["Unrealized P/L"])
        cost_basis = shares * average_cost

        item["Cost Basis"] = round(cost_basis, 2)
        item["Allocation (%)"] = round(
            (market_value / portfolio_value) * 100 if portfolio_value else 0.0,
            2,
        )
        item["Return (%)"] = round(
            (profit / cost_basis) * 100 if cost_basis else 0.0,
            2,
        )
        enriched.append(item)

    return enriched


def concentration_summary(position_rows, warning_threshold=25.0):
    """Return the largest allocation and positions over the risk threshold."""
    if not position_rows:
        return {
            "largest_symbol": None,
            "largest_weight": 0.0,
            "concentrated_symbols": [],
        }

    largest = max(position_rows, key=lambda row: row["Allocation (%)"])
    concentrated = [
        row["Symbol"]
        for row in position_rows
        if float(row["Allocation (%)"]) > float(warning_threshold)
    ]
    return {
        "largest_symbol": largest["Symbol"],
        "largest_weight": float(largest["Allocation (%)"]),
        "concentrated_symbols": concentrated,
    }


def equity_drawdown(history):
    """Add drawdown columns and return the maximum drawdown percentage."""
    frame = pd.DataFrame(history).copy()
    if frame.empty or "portfolio_value" not in frame.columns:
        return frame, 0.0

    frame["portfolio_value"] = pd.to_numeric(
        frame["portfolio_value"], errors="coerce"
    )
    frame = frame.dropna(subset=["portfolio_value"])
    if frame.empty:
        return frame, 0.0

    frame["peak_value"] = frame["portfolio_value"].cummax()
    frame["drawdown_percent"] = (
        (frame["portfolio_value"] / frame["peak_value"]) - 1
    ) * 100
    maximum_drawdown = abs(float(frame["drawdown_percent"].min()))
    return frame, round(maximum_drawdown, 2)
