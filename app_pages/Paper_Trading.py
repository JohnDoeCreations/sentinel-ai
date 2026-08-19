"""Sentinel AI simulated portfolio page."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.market_data import get_stock_data
from utils.alerts import (
    disable_paper_trade_protection,
    ensure_paper_trade_protection,
    load_alert_state,
    paper_trade_protection_status,
)
from utils.paper_trading import (
    buy_shares,
    calculate_position_size,
    load_portfolio,
    sell_shares,
)
from utils.watchlist import load_watchlist


def current_price(symbol):
    """Return the latest available adjusted closing price."""
    data = get_stock_data(symbol, period="5d", interval="1d")
    if data.empty or "Close" not in data.columns:
        raise ValueError(f"No current market price is available for {symbol}.")

    close_prices = data["Close"].dropna()
    if isinstance(close_prices, pd.DataFrame):
        close_prices = close_prices.iloc[:, 0]
    if close_prices.empty:
        raise ValueError(f"No current market price is available for {symbol}.")

    return float(close_prices.iloc[-1])


st.set_page_config(
    page_title="Sentinel AI Paper Trading",
    page_icon=":material/account_balance_wallet:",
    layout="wide",
)

st.title(":material/account_balance_wallet: Paper trading")
st.caption("Practice position management with simulated money and live market prices.")
st.warning("Simulation only. No real brokerage orders are submitted.")

trade_notice = st.session_state.pop("paper_trade_notice", None)
if trade_notice:
    if trade_notice["level"] == "success":
        st.success(trade_notice["message"])
    else:
        st.warning(trade_notice["message"])

portfolio = load_portfolio()
positions = portfolio["positions"]
saved_alerts = load_alert_state()["alerts"]

position_rows = []
market_value = 0.0
unrealized_profit = 0.0

for symbol, position in positions.items():
    try:
        price = current_price(symbol)
        shares = int(position["shares"])
        average_cost = float(position["average_cost"])
        value = shares * price
        profit = (price - average_cost) * shares
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
                "Return (%)": round(((price / average_cost) - 1) * 100, 2),
                "Protection": paper_trade_protection_status(
                    symbol, saved_alerts
                )["label"],
            }
        )
    except Exception as error:
        st.warning(f"{symbol}: Could not update market value — {error}")

total_value = portfolio["cash"] + market_value
total_return = total_value - float(portfolio["starting_cash"])

metric_1, metric_2, metric_3, metric_4 = st.columns(4, border=True)
metric_1.metric("Cash", f'${portfolio["cash"]:,.2f}')
metric_2.metric("Positions", f"${market_value:,.2f}")
metric_3.metric("Portfolio Value", f"${total_value:,.2f}")
metric_4.metric(
    "Total Return",
    f"${total_return:,.2f}",
    delta=f"{(total_return / portfolio['starting_cash']) * 100:.2f}%",
)

trade_context = st.session_state.get("paper_trade_context")
if trade_context:
    context_label = trade_context.get("Context Label", "Research context")
    st.subheader(f'{context_label}: {trade_context["Symbol"]}')
    context_columns = st.columns(3, border=True)
    if "Score" in trade_context:
        context_columns[0].metric("Scanner score", f'{trade_context["Score"]}/4')
    else:
        context_columns[0].metric("Source", context_label)
    context_columns[1].metric("Rating", trade_context.get("Rating", "—"))
    context_columns[2].metric("Signal", trade_context.get("Signal", "—"))
    st.info(trade_context["Explanation"])

buy_tab, sell_tab = st.tabs(["Buy Shares", "Sell Shares"])

with buy_tab:
    watchlist = load_watchlist()
    default_symbol = watchlist[0] if watchlist else "AAPL"
    if "paper_trade_symbol_input" not in st.session_state:
        st.session_state["paper_trade_symbol_input"] = default_symbol

    with st.form("paper_buy_form"):
        buy_symbol = st.text_input(
            "Symbol",
            max_chars=10,
            key="paper_trade_symbol_input",
        ).strip().upper()
        risk_percent = st.number_input(
            "Account risk per trade (%)",
            min_value=0.1,
            max_value=5.0,
            value=1.0,
            step=0.1,
        )
        stop_loss_percent = st.number_input(
            "Planned stop-loss distance (%)",
            min_value=0.5,
            max_value=25.0,
            value=5.0,
            step=0.5,
        )
        automatic_protection = st.checkbox(
            "Create automatic stop-loss and take-profit alerts",
            value=True,
            help=(
                "Sentinel AI will monitor both rules in the cloud and email "
                "you when either threshold is reached."
            ),
        )
        reward_risk_ratio = st.number_input(
            "Profit target (reward-to-risk ratio)",
            min_value=1.0,
            max_value=5.0,
            value=2.0,
            step=0.5,
            disabled=not automatic_protection,
        )
        buy_submitted = st.form_submit_button(
            "Calculate safe position size",
            icon=":material/calculate:",
            type="primary",
            width="stretch",
        )

    if buy_submitted:
        try:
            price = current_price(buy_symbol)
            existing_value = next(
                (
                    row["Market Value"]
                    for row in position_rows
                    if row["Symbol"] == buy_symbol
                ),
                0.0,
            )
            sizing = calculate_position_size(
                portfolio_value=total_value,
                available_cash=portfolio["cash"],
                price=price,
                stop_loss_percent=stop_loss_percent,
                risk_percent=risk_percent,
                maximum_position_percent=20.0,
                existing_position_value=existing_value,
            )
            st.session_state["pending_buy"] = {
                "symbol": buy_symbol,
                "price": price,
                "automatic_protection": automatic_protection,
                "stop_loss_percent": stop_loss_percent,
                "take_profit_percent": stop_loss_percent * reward_risk_ratio,
                **sizing,
            }
        except Exception as error:
            st.error(f"Could not calculate position size: {error}")

    pending_buy = st.session_state.get("pending_buy")
    if pending_buy:
        st.subheader("Order Preview")
        preview_1, preview_2, preview_3, preview_4 = st.columns(4, border=True)
        preview_1.metric("Current Price", f'${pending_buy["price"]:,.2f}')
        preview_2.metric("Suggested Shares", pending_buy["suggested_shares"])
        preview_3.metric("Estimated Cost", f'${pending_buy["estimated_cost"]:,.2f}')
        preview_4.metric("Planned Stop", f'${pending_buy["stop_loss_price"]:,.2f}')
        st.caption(
            f'Maximum planned loss: ${pending_buy["risk_budget"]:,.2f}. '
            f'Risk per share: ${pending_buy["risk_per_share"]:,.2f}. '
            "Position allocation is capped at 20% of portfolio value."
        )
        if pending_buy.get("automatic_protection", False):
            st.info(
                f'Automatic protection: alert at '
                f'-{pending_buy["stop_loss_percent"]:.1f}% and '
                f'+{pending_buy["take_profit_percent"]:.1f}%.'
            )

        if pending_buy["suggested_shares"] < 1:
            st.warning(
                "No shares fit the current cash, risk, and 20% allocation limits."
            )
        elif st.button(
            "Confirm simulated buy",
            icon=":material/check_circle:",
            type="primary",
            width="stretch",
        ):
            try:
                buy_shares(
                    pending_buy["symbol"],
                    pending_buy["suggested_shares"],
                    pending_buy["price"],
                )
            except Exception as error:
                st.error(f"Buy order rejected: {error}")
            else:
                protection_error = None
                if pending_buy.get("automatic_protection", False):
                    try:
                        ensure_paper_trade_protection(
                            pending_buy["symbol"],
                            pending_buy["stop_loss_percent"],
                            pending_buy["take_profit_percent"],
                        )
                    except Exception as error:
                        protection_error = str(error)

                if protection_error:
                    st.session_state["paper_trade_notice"] = {
                        "level": "warning",
                        "message": (
                            "The simulated buy succeeded, but automatic "
                            f"protection could not be saved: {protection_error}"
                        ),
                    }
                else:
                    protection_text = (
                        " Automatic protection is active."
                        if pending_buy.get("automatic_protection", False)
                        else ""
                    )
                    st.session_state["paper_trade_notice"] = {
                        "level": "success",
                        "message": (
                            f'Bought {pending_buy["suggested_shares"]} '
                            f'share(s) of {pending_buy["symbol"]}.'
                            + protection_text
                        ),
                    }
                st.session_state.pop("pending_buy", None)
                st.session_state.pop("paper_trade_context", None)
                st.rerun()

with sell_tab:
    owned_symbols = list(positions)
    if not owned_symbols:
        st.info("Buy a position before placing a sell order.")
    else:
        with st.form("paper_sell_form"):
            sell_symbol = st.selectbox("Position", options=owned_symbols)
            maximum_shares = int(positions[sell_symbol]["shares"])
            sell_quantity = st.number_input(
                "Shares to sell",
                min_value=1,
                max_value=maximum_shares,
                value=1,
                step=1,
            )
            sell_submitted = st.form_submit_button(
                "Sell at current price",
                icon=":material/sell:",
                type="primary",
                width="stretch",
            )

        if sell_submitted:
            try:
                price = current_price(sell_symbol)
                updated_portfolio = sell_shares(
                    sell_symbol, sell_quantity, price
                )
                if sell_symbol not in updated_portfolio["positions"]:
                    disable_paper_trade_protection(sell_symbol)
                st.success(
                    f"Sold {int(sell_quantity)} share(s) of {sell_symbol} "
                    f"at ${price:,.2f}."
                )
                st.rerun()
            except Exception as error:
                st.error(f"Sell order rejected: {error}")

st.subheader("Open Positions")
if position_rows:
    st.dataframe(pd.DataFrame(position_rows), width="stretch", hide_index=True)
    st.caption(f"Combined unrealized profit/loss: ${unrealized_profit:,.2f}")
else:
    st.info("No open positions yet.")

st.subheader("Transaction History")
transactions = portfolio["transactions"]
if transactions:
    transaction_table = pd.DataFrame(reversed(transactions)).rename(
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
    st.dataframe(transaction_table, width="stretch", hide_index=True)
else:
    st.info("No simulated transactions have been recorded.")
