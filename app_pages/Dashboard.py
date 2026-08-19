"""At-a-glance dashboard for Sentinel AI."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.alerts import load_alert_state
from utils.paper_trading import load_portfolio
from utils.watchlist import load_watchlist


st.set_page_config(
    page_title="Sentinel AI dashboard",
    page_icon=":material/dashboard:",
    layout="wide",
)

st.title(":material/dashboard: Sentinel AI dashboard")
st.caption("Your watchlist, alerts, and simulated portfolio in one place.")

watchlist = load_watchlist()
alert_state = load_alert_state()
portfolio = load_portfolio()

positions = portfolio.get("positions", {})
transactions = portfolio.get("transactions", [])
equity_history = portfolio.get("equity_history", [])
alerts = alert_state.get("alerts", [])
active_alerts = [alert for alert in alerts if alert.get("enabled", True)]
triggered_alerts = [alert for alert in active_alerts if alert.get("is_triggered")]

starting_cash = float(portfolio.get("starting_cash", 0.0))
cash = float(portfolio.get("cash", 0.0))
latest_value = (
    float(equity_history[-1].get("portfolio_value", cash))
    if equity_history
    else cash
)
total_return = latest_value - starting_cash
return_percent = (total_return / starting_cash * 100) if starting_cash else 0.0

with st.container(horizontal=True):
    st.metric(
        "Paper portfolio",
        f"${latest_value:,.2f}",
        f"{return_percent:+.2f}%",
        border=True,
    )
    st.metric("Cash", f"${cash:,.2f}", border=True)
    st.metric("Open positions", len(positions), border=True)
    st.metric("Watchlist symbols", len(watchlist), border=True)
    st.metric(
        "Active alerts",
        len(active_alerts),
        f"{len(triggered_alerts)} triggered",
        border=True,
    )

portfolio_column, activity_column = st.columns(2)

with portfolio_column:
    with st.container(border=True):
        st.subheader("Portfolio value")
        if equity_history:
            equity_table = pd.DataFrame(equity_history)
            equity_table["date"] = pd.to_datetime(
                equity_table["date"], errors="coerce"
            )
            equity_table["portfolio_value"] = pd.to_numeric(
                equity_table["portfolio_value"], errors="coerce"
            )
            equity_table = equity_table.dropna(
                subset=["date", "portfolio_value"]
            ).sort_values("date")

            if equity_table.empty:
                st.info("No valid portfolio snapshots are available yet.")
            else:
                st.line_chart(
                    equity_table,
                    x="date",
                    y="portfolio_value",
                    x_label="Date",
                    y_label="Portfolio value ($)",
                )
        else:
            st.info("Paper-trading activity will create portfolio snapshots.")

with activity_column:
    with st.container(border=True):
        st.subheader("Current activity")
        if positions:
            position_table = pd.DataFrame(
                [
                    {
                        "Symbol": symbol,
                        "Shares": int(position.get("shares", 0)),
                        "Average cost": float(position.get("average_cost", 0.0)),
                    }
                    for symbol, position in positions.items()
                ]
            )
            st.dataframe(
                position_table,
                column_config={
                    "Average cost": st.column_config.NumberColumn(
                        format="$%.2f"
                    )
                },
                hide_index=True,
            )
        else:
            st.info("No paper positions are open.")

        if watchlist:
            st.caption("Watchlist: " + ", ".join(watchlist))
        else:
            st.caption("Your watchlist is empty.")

with st.container(border=True):
    st.subheader("Recent simulated trades")
    if transactions:
        recent_trades = pd.DataFrame(transactions[-5:][::-1]).rename(
            columns={
                "timestamp": "Time (UTC)",
                "side": "Side",
                "symbol": "Symbol",
                "shares": "Shares",
                "price": "Price",
                "total": "Total",
                "realized_profit": "Realized P/L",
            }
        )
        visible_columns = [
            column
            for column in [
                "Time (UTC)",
                "Side",
                "Symbol",
                "Shares",
                "Price",
                "Total",
                "Realized P/L",
            ]
            if column in recent_trades.columns
        ]
        st.dataframe(
            recent_trades[visible_columns],
            column_config={
                "Price": st.column_config.NumberColumn(format="$%.2f"),
                "Total": st.column_config.NumberColumn(format="$%.2f"),
                "Realized P/L": st.column_config.NumberColumn(format="$%.2f"),
            },
            hide_index=True,
        )
    else:
        st.info("No simulated trades have been recorded.")

st.caption("Portfolio values are simulated and intended for education only.")
