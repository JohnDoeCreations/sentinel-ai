"""Pure calculation helpers for paper-portfolio performance and risk."""

import pandas as pd


def protection_risk_rows(positions, alerts):
    """Build paper-position protection and planned-risk rows."""
    rows = []
    for symbol, position in positions.items():
        shares = int(position.get("shares", 0))
        average_cost = float(position.get("average_cost", 0.0))
        cost_basis = shares * average_cost
        linked = [
            alert
            for alert in alerts
            if alert.get("symbol") == symbol
            and alert.get("source") == "paper_trade"
            and alert.get("enabled", True)
        ]
        stop_alert = next(
            (
                alert
                for alert in linked
                if alert.get("type") == "position_loss_at_most"
            ),
            None,
        )
        target_alert = next(
            (
                alert
                for alert in linked
                if alert.get("type") == "position_gain_at_least"
            ),
            None,
        )
        protected = stop_alert is not None and target_alert is not None
        stop_percent = float(stop_alert["target"]) if stop_alert else None
        target_percent = float(target_alert["target"]) if target_alert else None
        planned_risk = (
            cost_basis * stop_percent / 100 if stop_percent is not None else None
        )
        attention = any(
            alert.get("is_triggered") or alert.get("last_error")
            for alert in linked
        )
        rows.append(
            {
                "Symbol": symbol,
                "Shares": shares,
                "Cost Basis": round(cost_basis, 2),
                "Status": "Protected" if protected else "Needs protection",
                "Stop (%)": stop_percent,
                "Target (%)": target_percent,
                "Planned Risk ($)": (
                    round(planned_risk, 2) if planned_risk is not None else None
                ),
                "Needs Attention": attention,
            }
        )
    return rows


def protection_risk_summary(rows):
    """Summarize coverage and known capital at risk."""
    protected = [row for row in rows if row["Status"] == "Protected"]
    total_cost = sum(float(row["Cost Basis"]) for row in rows)
    unprotected_value = sum(
        float(row["Cost Basis"])
        for row in rows
        if row["Status"] != "Protected"
    )
    planned_risk = sum(
        float(row["Planned Risk ($)"] or 0.0) for row in rows
    )
    coverage = (len(protected) / len(rows) * 100) if rows else 0.0
    return {
        "positions": len(rows),
        "protected_positions": len(protected),
        "coverage_percent": round(coverage, 2),
        "total_cost_basis": round(total_cost, 2),
        "unprotected_value": round(unprotected_value, 2),
        "planned_risk": round(planned_risk, 2),
        "attention_count": sum(bool(row["Needs Attention"]) for row in rows),
    }


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
