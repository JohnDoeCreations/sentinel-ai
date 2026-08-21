"""Profit analytics for the Kalshi simulated portfolio."""


def paper_profit_summary(portfolio, unrealized_profit=0.0):
    """Summarize simulated trading profit while excluding cash adjustments."""
    closed = [
        row for row in portfolio.get("transactions", [])
        if row.get("action") in {"CLOSE", "SETTLE"}
        and row.get("realized_profit") is not None
    ]
    realized = sum(float(row.get("realized_profit", 0)) for row in closed)
    wins = sum(float(row.get("realized_profit", 0)) > 0 for row in closed)
    cumulative = 0.0
    history = []
    for row in closed:
        profit = float(row.get("realized_profit", 0))
        cumulative += profit
        history.append(
            {
                "Time": row.get("timestamp"),
                "Market": row.get("ticker", ""),
                "Side": row.get("side", ""),
                "Trade P/L": profit,
                "Cumulative realized P/L": cumulative,
            }
        )
    unrealized = float(unrealized_profit)
    return {
        "realized_profit": realized,
        "unrealized_profit": unrealized,
        "total_profit": realized + unrealized,
        "closed_trades": len(closed),
        "win_rate": wins / len(closed) if closed else None,
        "history": history,
    }
