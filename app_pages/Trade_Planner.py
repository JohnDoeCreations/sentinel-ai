"""Risk-first position planning page for Sentinel AI."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.market_data import MarketDataError, get_stock_data
from strategies.indicators import calculate_atr
from utils.paper_trading import load_portfolio
from utils.symbols import normalize_symbol
from utils.trade_planner import calculate_trade_plan


def load_trade_defaults(symbol):
    """Return the latest price and ATR-based planning defaults."""
    clean_symbol = normalize_symbol(symbol)
    data = get_stock_data(clean_symbol, period="3mo", interval="1d")
    required = {"High", "Low", "Close"}
    if data.empty or not required.issubset(data.columns):
        raise ValueError(f"No usable market data is available for {clean_symbol}.")

    normalized = pd.DataFrame()
    for column in required:
        values = data[column]
        if isinstance(values, pd.DataFrame):
            values = values.iloc[:, 0]
        normalized[column] = pd.to_numeric(values, errors="coerce")
    normalized = normalized.dropna()
    if len(normalized) < 14:
        raise ValueError(f"Not enough recent data is available for {clean_symbol}.")

    price = float(normalized["Close"].iloc[-1])
    atr = calculate_atr(normalized, period=14)
    stop = max(0.01, price - 2 * atr)
    target = price + 2 * (price - stop)
    return clean_symbol, price, atr, stop, target


st.set_page_config(
    page_title="Sentinel AI trade planner",
    page_icon=":material/calculate:",
    layout="wide",
)

st.title(":material/calculate: Trade planner")
st.caption(
    "Size a potential long position from the loss you can afford—not the profit you hope to make."
)

portfolio = load_portfolio()
cost_basis = sum(
    int(position.get("shares", 0)) * float(position.get("average_cost", 0.0))
    for position in portfolio.get("positions", {}).values()
)
default_account_value = max(
    1.0,
    float(portfolio.get("cash", 0.0)) + cost_basis,
)

st.session_state.setdefault("planner_symbol", "AAPL")
st.session_state.setdefault("planner_entry", 100.0)
st.session_state.setdefault("planner_stop", 95.0)
st.session_state.setdefault("planner_target", 110.0)

with st.container(border=True):
    st.subheader("Market defaults")
    quote_row = st.container(horizontal=True, vertical_alignment="bottom")
    quote_symbol = quote_row.text_input(
        "Symbol",
        key="planner_symbol",
        max_chars=10,
    )
    load_quote = quote_row.button(
        "Load quote and ATR levels",
        icon=":material/download:",
        type="primary",
    )

    if load_quote:
        try:
            with st.spinner(f"Loading {quote_symbol.strip().upper()}..."):
                clean_symbol, price, atr, stop, target = load_trade_defaults(
                    quote_symbol
                )
            st.session_state["planner_entry"] = round(price, 2)
            st.session_state["planner_stop"] = round(stop, 2)
            st.session_state["planner_target"] = round(target, 2)
            st.session_state["planner_atr"] = round(atr, 2)
            st.session_state.pop("trade_plan", None)
            st.rerun()
        except (MarketDataError, ValueError) as error:
            st.error(str(error))
        except Exception as error:
            st.error(f"Could not load market defaults: {error}")

    if "planner_atr" in st.session_state:
        st.caption(
            f'ATR-based defaults use a two-ATR stop. Current ATR: '
            f'${st.session_state["planner_atr"]:,.2f}.'
        )

with st.form("trade_planner_form"):
    st.subheader("Plan inputs")
    account_columns = st.columns(4)
    account_value = account_columns[0].number_input(
        "Account value ($)",
        min_value=1.0,
        value=default_account_value,
        step=100.0,
    )
    available_cash = account_columns[1].number_input(
        "Available cash ($)",
        min_value=0.0,
        value=float(portfolio.get("cash", 0.0)),
        step=100.0,
    )
    risk_percent = account_columns[2].number_input(
        "Risk per trade (%)",
        min_value=0.1,
        max_value=10.0,
        value=1.0,
        step=0.1,
    )
    maximum_allocation = account_columns[3].number_input(
        "Maximum allocation (%)",
        min_value=1.0,
        max_value=100.0,
        value=20.0,
        step=1.0,
    )

    price_columns = st.columns(3)
    entry_price = price_columns[0].number_input(
        "Planned entry ($)",
        min_value=0.01,
        key="planner_entry",
        step=0.50,
    )
    stop_price = price_columns[1].number_input(
        "Stop loss ($)",
        min_value=0.01,
        key="planner_stop",
        step=0.50,
    )
    target_price = price_columns[2].number_input(
        "Profit target ($)",
        min_value=0.01,
        key="planner_target",
        step=0.50,
    )

    submitted = st.form_submit_button(
        "Calculate trade plan",
        icon=":material/calculate:",
        type="primary",
        width="stretch",
    )

if submitted:
    try:
        clean_symbol = normalize_symbol(st.session_state["planner_symbol"])
        existing_position = portfolio.get("positions", {}).get(clean_symbol, {})
        existing_position_value = (
            int(existing_position.get("shares", 0))
            * float(existing_position.get("average_cost", 0.0))
        )
        plan = calculate_trade_plan(
            account_value=account_value,
            available_cash=available_cash,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            risk_percent=risk_percent,
            maximum_position_percent=maximum_allocation,
            existing_position_value=existing_position_value,
        )
        st.session_state["trade_plan"] = {
            "symbol": clean_symbol,
            "entry_price": float(entry_price),
            "stop_price": float(stop_price),
            "target_price": float(target_price),
            "risk_percent": float(risk_percent),
            **plan,
        }
    except ValueError as error:
        st.error(str(error))

plan = st.session_state.get("trade_plan")
if not plan:
    st.info("Enter your risk limits and prices, then calculate the trade plan.")
    st.stop()

st.subheader(f'{plan["symbol"]} position plan')
with st.container(horizontal=True):
    st.metric("Suggested shares", plan["suggested_shares"], border=True)
    st.metric("Position value", f'${plan["position_value"]:,.2f}', border=True)
    st.metric("Planned loss", f'${plan["planned_loss"]:,.2f}', border=True)
    st.metric("Planned profit", f'${plan["planned_profit"]:,.2f}', border=True)
    st.metric("Reward / risk", f'{plan["reward_to_risk"]:.2f}R', border=True)

details_column, targets_column = st.columns(2)
with details_column:
    with st.container(border=True):
        st.subheader("Risk details")
        st.write(f'**Risk budget:** ${plan["risk_budget"]:,.2f}')
        st.write(f'**Risk per share:** ${plan["risk_per_share"]:,.2f}')
        st.write(f'**Stop distance:** {plan["stop_distance_percent"]:.2f}%')
        st.write(f'**Portfolio allocation:** {plan["allocation_percent"]:.2f}%')
        st.write(f'**Binding limit:** {plan["limiting_factor"]}')

with targets_column:
    with st.container(border=True):
        st.subheader("Reward checkpoints")
        st.metric("1R target", f'${plan["one_r_target"]:,.2f}')
        st.metric("2R target", f'${plan["two_r_target"]:,.2f}')
        st.metric("3R target", f'${plan["three_r_target"]:,.2f}')

if plan["warnings"]:
    with st.container(border=True):
        st.subheader("Risk checks")
        for warning in plan["warnings"]:
            st.warning(warning)
else:
    st.success("This plan passes Sentinel's basic risk checks.")

if plan["suggested_shares"] > 0 and st.button(
    "Send plan to paper trading",
    icon=":material/account_balance_wallet:",
    type="primary",
):
    st.session_state["paper_trade_symbol_input"] = plan["symbol"]
    st.session_state["paper_trade_context"] = {
        "Symbol": plan["symbol"],
        "Context Label": "Trade plan",
        "Rating": f'{plan["reward_to_risk"]:.2f}R target',
        "Signal": f'{plan["risk_percent"]:.1f}% account risk',
        "Explanation": (
            f'Plan: {plan["suggested_shares"]} shares near '
            f'${plan["entry_price"]:,.2f}, stop ${plan["stop_price"]:,.2f}, '
            f'target ${plan["target_price"]:,.2f}. Maximum planned loss is '
            f'${plan["planned_loss"]:,.2f}.'
        ),
    }
    st.session_state["pending_buy"] = {
        "symbol": plan["symbol"],
        "price": plan["entry_price"],
        "suggested_shares": plan["suggested_shares"],
        "estimated_cost": plan["position_value"],
        "stop_loss_price": plan["stop_price"],
        "risk_budget": plan["risk_budget"],
        "risk_per_share": plan["risk_per_share"],
    }
    st.switch_page("app_pages/Paper_Trading.py")

st.caption("Planning support only. Review every assumption before simulating a trade.")
