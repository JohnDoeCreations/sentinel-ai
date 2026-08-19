"""Performance analytics for the Sentinel AI paper portfolio."""

from pathlib import Path
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.market_data import get_stock_data
from utils.alerts import load_alert_state, paper_trade_protection_status
from utils.paper_trading import load_portfolio, record_equity_snapshot
from utils.portfolio_analytics import (
    concentration_summary,
    enrich_position_rows,
    equity_drawdown,
    protection_risk_rows,
    protection_risk_summary,
)


def latest_price(symbol):
    """Return the latest available adjusted close for one symbol."""
    data = get_stock_data(symbol, period="5d", interval="1d")
    if data.empty or "Close" not in data.columns:
        raise ValueError("No current price available.")

    close_prices = data["Close"].dropna()
    if isinstance(close_prices, pd.DataFrame):
        close_prices = close_prices.iloc[:, 0]
    if close_prices.empty:
        raise ValueError("No current price available.")
    return float(close_prices.iloc[-1])


st.set_page_config(
    page_title="Sentinel AI portfolio intelligence",
    page_icon=":material/monitoring:",
    layout="wide",
)

with st.container(horizontal=True, vertical_alignment="center"):
    with st.container():
        st.title(":material/monitoring: Portfolio intelligence")
        st.caption(
            "Performance, allocation, drawdown, and position protection in "
            "one portfolio workspace."
        )
    st.badge("Simulation", icon=":material/science:", color="violet")
st.caption("Paper-trading analytics only · No real brokerage account connected")

portfolio = load_portfolio()
saved_alerts = load_alert_state()["alerts"]
starting_cash = float(portfolio["starting_cash"])
cash = float(portfolio["cash"])

position_rows = []
market_value = 0.0
unrealized_profit = 0.0

for symbol, position in portfolio["positions"].items():
    try:
        price = latest_price(symbol)
        shares = int(position["shares"])
        average_cost = float(position["average_cost"])
        value = shares * price
        profit = (price - average_cost) * shares
        return_percent = ((price / average_cost) - 1) * 100
        market_value += value
        unrealized_profit += profit
        position_rows.append(
            {
                "Symbol": symbol,
                "Shares": shares,
                "Average Cost": round(average_cost, 2),
                "Current Price": round(price, 2),
                "Market Value": round(value, 2),
                "Unrealized P/L": round(profit, 2),
                "Return (%)": round(return_percent, 2),
                "Protection": paper_trade_protection_status(
                    symbol, saved_alerts
                )["label"],
            }
        )
    except Exception as error:
        st.warning(f"{symbol}: Could not update performance — {error}")

portfolio_value = cash + market_value
total_profit = portfolio_value - starting_cash
total_return_percent = (total_profit / starting_cash) * 100
position_rows = enrich_position_rows(position_rows, portfolio_value)
invested_cost_basis = sum(row["Cost Basis"] for row in position_rows)
concentration = concentration_summary(position_rows)
protection_rows = protection_risk_rows(portfolio["positions"], saved_alerts)
protection_summary = protection_risk_summary(protection_rows)

sell_transactions = [
    transaction
    for transaction in portfolio["transactions"]
    if transaction.get("side") == "SELL"
]
realized_profit = sum(
    float(transaction.get("realized_profit", 0.0))
    for transaction in sell_transactions
)
winning_sales = sum(
    1
    for transaction in sell_transactions
    if float(transaction.get("realized_profit", 0.0)) > 0
)
closed_trade_win_rate = (
    (winning_sales / len(sell_transactions)) * 100
    if sell_transactions
    else 0.0
)

record_equity_snapshot(portfolio_value, cash, market_value)
portfolio = load_portfolio()
history, maximum_drawdown = equity_drawdown(portfolio.get("equity_history", []))

with st.container(horizontal=True):
    st.metric("Portfolio value", f"${portfolio_value:,.2f}", border=True)
    st.metric(
        "Total return",
        f"${total_profit:,.2f}",
        delta=f"{total_return_percent:.2f}%",
        border=True,
    )
    st.metric("Realized P/L", f"${realized_profit:,.2f}", border=True)
    st.metric("Unrealized P/L", f"${unrealized_profit:,.2f}", border=True)

with st.container(horizontal=True):
    st.metric("Available cash", f"${cash:,.2f}", border=True)
    st.metric("Invested value", f"${market_value:,.2f}", border=True)
    st.metric("Maximum drawdown", f"{maximum_drawdown:.2f}%", border=True)
    st.metric(
        "Protection coverage",
        f'{protection_summary["coverage_percent"]:.0f}%'
        if position_rows
        else "No positions",
        f'{protection_summary["protected_positions"]} protected',
        border=True,
        delta_color="off",
    )

st.subheader("Portfolio equity curve")
if history.empty:
    st.info("Equity history will appear after the first portfolio snapshot.")
else:
    history["date"] = pd.to_datetime(history["date"])
    history = history.sort_values("date")

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=history["date"],
            y=history["portfolio_value"],
            mode="lines+markers",
            name="Portfolio Value",
            line={"color": "#8B5CF6", "width": 3},
        )
    )
    figure.add_hline(
        y=starting_cash,
        line_dash="dash",
        line_color="#9ca3af",
        annotation_text="Starting Value",
    )
    figure.update_layout(
        height=480,
        template="plotly_dark",
        margin={"l": 10, "r": 10, "t": 20, "b": 10},
        xaxis_title="Date",
        yaxis_title="Portfolio Value ($)",
        hovermode="x unified",
    )
    st.plotly_chart(
        figure,
        width="stretch",
        config={"displaylogo": False, "scrollZoom": True},
    )

st.subheader("Allocation and concentration")
if position_rows:
    allocation_table = pd.DataFrame(position_rows).sort_values(
        "Allocation (%)", ascending=False
    )
    st.bar_chart(
        allocation_table,
        x="Symbol",
        y="Allocation (%)",
        horizontal=True,
    )
    if concentration["concentrated_symbols"]:
        names = ", ".join(concentration["concentrated_symbols"])
        st.warning(
            f"Concentration risk: {names} exceed 25% of total portfolio value. "
            "Consider whether that exposure matches your risk plan."
        )
    else:
        st.success(
            "No individual holding exceeds 25% of total portfolio value."
        )
else:
    st.info("Allocation analysis will appear after you open a position.")

st.subheader("Position protection")
st.caption(
    f'Invested cost basis: \\${invested_cost_basis:,.2f} · '
    f'Planned capital at risk: '
    f'\\${protection_summary["planned_risk"]:,.2f}'
)
if protection_rows:
    if protection_summary["unprotected_value"] > 0:
        unprotected = ", ".join(
            row["Symbol"]
            for row in protection_rows
            if row["Status"] != "Protected"
        )
        st.warning(
            f"Protection needed for {unprotected}. Add stop and target alerts "
            "from Paper trading or Alerts.",
            icon=":material/gpp_maybe:",
        )
    elif protection_summary["attention_count"]:
        st.warning(
            "Protection is configured, but one or more linked alerts needs "
            "attention.",
            icon=":material/notification_important:",
        )
    else:
        st.success(
            "Every open position has active stop and target protection.",
            icon=":material/verified_user:",
        )

    st.dataframe(
        pd.DataFrame(protection_rows),
        hide_index=True,
        column_config={
            "Symbol": st.column_config.TextColumn(pinned=True),
            "Cost Basis": st.column_config.NumberColumn(format="$%.2f"),
            "Stop (%)": st.column_config.NumberColumn(format="%.2f%%"),
            "Target (%)": st.column_config.NumberColumn(format="%.2f%%"),
            "Planned Risk ($)": st.column_config.NumberColumn(format="$%.2f"),
            "Needs Attention": st.column_config.CheckboxColumn(),
        },
    )
else:
    st.info("Open a simulated position to begin protection tracking.")

st.subheader("Open-position performance")
if position_rows:
    positions_table = pd.DataFrame(position_rows).sort_values(
        "Return (%)",
        ascending=False,
    )
    best_position = positions_table.iloc[0]
    worst_position = positions_table.iloc[-1]

    best_column, worst_column = st.columns(2)
    with best_column:
        st.success(
            f'Best open position: {best_position["Symbol"]} '
            f'({best_position["Return (%)"]:+.2f}%)'
        )
    with worst_column:
        weakest_message = (
            f'Weakest open position: {worst_position["Symbol"]} '
            f'({worst_position["Return (%)"]:+.2f}%)'
        )
        if float(worst_position["Return (%)"]) < 0:
            st.error(weakest_message)
        else:
            st.info(weakest_message)

    st.dataframe(
        positions_table,
        width="stretch",
        hide_index=True,
        column_config={
            "Average Cost": st.column_config.NumberColumn(format="$%.2f"),
            "Current Price": st.column_config.NumberColumn(format="$%.2f"),
            "Cost Basis": st.column_config.NumberColumn(format="$%.2f"),
            "Market Value": st.column_config.NumberColumn(format="$%.2f"),
            "Unrealized P/L": st.column_config.NumberColumn(format="$%.2f"),
            "Return (%)": st.column_config.NumberColumn(format="%.2f%%"),
            "Allocation (%)": st.column_config.ProgressColumn(
                format="%.2f%%", min_value=0, max_value=100
            ),
        },
    )
else:
    st.info("Open a simulated position to begin position-level tracking.")

st.subheader("Closed sales")
st.caption(f"Closed-sale win rate: {closed_trade_win_rate:.2f}%")
if sell_transactions:
    closed_table = pd.DataFrame(reversed(sell_transactions)).rename(
        columns={
            "timestamp": "Time (UTC)",
            "symbol": "Symbol",
            "shares": "Shares",
            "price": "Sale Price",
            "total": "Proceeds",
            "realized_profit": "Realized P/L",
        }
    )
    display_columns = [
        "Time (UTC)",
        "Symbol",
        "Shares",
        "Sale Price",
        "Proceeds",
        "Realized P/L",
    ]
    st.dataframe(
        closed_table[display_columns],
        width="stretch",
        hide_index=True,
        column_config={
            "Sale Price": st.column_config.NumberColumn(format="$%.2f"),
            "Proceeds": st.column_config.NumberColumn(format="$%.2f"),
            "Realized P/L": st.column_config.NumberColumn(format="$%.2f"),
        },
    )
else:
    st.info("Closed-trade statistics will appear after the first simulated sale.")
