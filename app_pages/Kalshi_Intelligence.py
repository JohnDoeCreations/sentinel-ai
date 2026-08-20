"""Kalshi 15-minute crypto intelligence and paper-contract execution."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.kalshi import (
    CRYPTO_15M_SERIES,
    KalshiDataError,
    buy_paper_contract,
    close_paper_contract,
    fetch_crypto_15m_markets,
    load_kalshi_paper_portfolio,
)


st.set_page_config(
    page_title="Sentinel AI Kalshi intelligence",
    page_icon=":material/candlestick_chart:",
    layout="wide",
)


@st.cache_data(ttl=10, max_entries=10, show_spinner=False)
def load_live_markets(assets):
    """Cache the public feed briefly so normal interactions stay fast."""
    return fetch_crypto_15m_markets(tuple(assets))


with st.container(horizontal=True, vertical_alignment="center"):
    with st.container():
        st.title(":material/candlestick_chart: Kalshi intelligence")
        st.caption(
            "Explore active 15-minute crypto event contracts and test ideas "
            "with simulated money before any live-trading connection."
        )
    st.badge("Paper mode", icon=":material/science:", color="violet")

st.warning(
    "This workspace does not place real orders or provide guaranteed predictions. "
    "Contract prices represent market-implied probabilities, not Sentinel forecasts.",
    icon=":material/shield:",
)

selected_assets = st.pills(
    "Crypto markets",
    list(CRYPTO_15M_SERIES),
    default=["BTC", "ETH", "SOL"],
    selection_mode="multi",
    key="kalshi_assets",
)
selected_assets = selected_assets or []

market_slot = st.container()
try:
    with market_slot.skeleton(height=260):
        markets = load_live_markets(tuple(selected_assets)) if selected_assets else []
except KalshiDataError as error:
    markets = []
    market_slot.error(str(error), icon=":material/cloud_off:")

portfolio = load_kalshi_paper_portfolio()
market_by_ticker = {market["ticker"]: market for market in markets}
position_rows = []
market_value = 0.0
unrealized_profit = 0.0
for key, position in portfolio["positions"].items():
    live_market = market_by_ticker.get(position["ticker"], {})
    bid_field = "yes_bid" if position["side"] == "YES" else "no_bid"
    current_bid = live_market.get(bid_field)
    mark_price = (
        float(current_bid)
        if current_bid is not None
        else float(position["average_cost"])
    )
    value = int(position["contracts"]) * mark_price
    profit = (
        mark_price - float(position["average_cost"])
    ) * int(position["contracts"])
    market_value += value
    unrealized_profit += profit
    position_rows.append(
        {
            "Position key": key,
            "Asset": position.get("asset", "—"),
            "Contract": position["title"],
            "Side": position["side"],
            "Contracts": int(position["contracts"]),
            "Average cost": float(position["average_cost"]),
            "Current bid": mark_price,
            "Market value": value,
            "Unrealized P/L": profit,
        }
    )

with st.container(horizontal=True):
    st.metric("Active contracts", len(markets), border=True)
    st.metric(
        "Paper cash",
        f'${float(portfolio["cash"]):,.2f}',
        border=True,
    )
    st.metric("Open positions", len(position_rows), border=True)
    st.metric(
        "Paper equity",
        f'${float(portfolio["cash"]) + market_value:,.2f}',
        delta=f"${unrealized_profit:+,.2f} open P/L",
        border=True,
    )

live_tab, portfolio_tab = st.tabs(
    [
        ":material/monitoring: Live market board",
        ":material/account_balance_wallet: Paper portfolio",
    ]
)

with live_tab:
    st.subheader("Select a contract")
    st.caption(
        "The midpoint is a market-implied probability. Wider spreads and lower "
        "liquidity generally make entries and exits more expensive."
    )
    if not selected_assets:
        st.info("Choose at least one crypto market above.")
    elif not markets:
        st.info("No active contracts were returned for the selected markets.")
    else:
        market_table = pd.DataFrame(
            [
                {
                    "Asset": market["asset"],
                    "Contract": market["title"],
                    "YES bid": market["yes_bid"],
                    "YES ask": market["yes_ask"],
                    "Implied probability": market["market_probability"],
                    "Spread": market["spread"],
                    "24h volume": market["volume_24h"],
                    "Liquidity": market["liquidity"],
                    "Closes": market["close_time"],
                    "Ticker": market["ticker"],
                }
                for market in markets
            ]
        )
        selection = st.dataframe(
            market_table,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="kalshi_market_table",
            column_config={
                "Asset": st.column_config.TextColumn(pinned=True),
                "YES bid": st.column_config.NumberColumn(format="$%.3f"),
                "YES ask": st.column_config.NumberColumn(format="$%.3f"),
                "Implied probability": st.column_config.ProgressColumn(
                    format="percent", min_value=0, max_value=1
                ),
                "Spread": st.column_config.NumberColumn(format="$%.3f"),
                "24h volume": st.column_config.NumberColumn(format="compact"),
                "Liquidity": st.column_config.NumberColumn(format="$compact"),
                "Closes": st.column_config.DatetimeColumn(
                    format="MMM DD, h:mm:ss a"
                ),
                "Ticker": None,
            },
        )

        selected_rows = selection.selection.rows
        if selected_rows:
            selected = markets[selected_rows[0]]
            with st.container(border=True):
                st.subheader(selected["title"])
                with st.container(horizontal=True):
                    st.metric("YES ask", f'${selected["yes_ask"]:.3f}')
                    st.metric("NO ask", f'${selected["no_ask"]:.3f}')
                    st.metric("YES spread", f'${selected["spread"]:.3f}')
                    st.metric("Liquidity", f'${selected["liquidity"]:,.0f}')

                st.markdown("#### Simulate an entry")
                with st.form("kalshi_paper_order"):
                    side = st.segmented_control(
                        "Contract side",
                        ["YES", "NO"],
                        default="YES",
                        key="kalshi_order_side",
                    )
                    contracts = st.number_input(
                        "Contracts",
                        min_value=1,
                        max_value=1_000,
                        value=10,
                        step=1,
                    )
                    ask_price = (
                        selected["yes_ask"] if side == "YES" else selected["no_ask"]
                    )
                    st.caption(
                        f"Estimated paper cost: ${contracts * ask_price:,.2f} · "
                        f"Maximum settlement value: ${contracts:,.2f}"
                    )
                    submitted = st.form_submit_button(
                        "Place simulated order",
                        icon=":material/science:",
                        type="primary",
                        width="stretch",
                    )
                if submitted:
                    try:
                        buy_paper_contract(
                            selected["ticker"],
                            selected["title"],
                            selected["asset"],
                            side,
                            contracts,
                            ask_price,
                            selected["close_time"],
                        )
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        st.toast("Simulated contract order recorded.", icon=":material/check_circle:")
                        st.rerun()
        else:
            st.caption("Select one row to inspect it and open the paper trade ticket.")

with portfolio_tab:
    st.subheader("Open simulated contracts")
    if not position_rows:
        st.info("Your Kalshi paper portfolio has no open contracts yet.")
    else:
        positions_table = pd.DataFrame(position_rows)
        st.dataframe(
            positions_table.drop(columns=["Position key"]),
            hide_index=True,
            column_config={
                "Asset": st.column_config.TextColumn(pinned=True),
                "Average cost": st.column_config.NumberColumn(format="$%.3f"),
                "Current bid": st.column_config.NumberColumn(format="$%.3f"),
                "Market value": st.column_config.NumberColumn(format="$%.2f"),
                "Unrealized P/L": st.column_config.NumberColumn(format="$%+.2f"),
            },
        )
        with st.form("kalshi_close_position"):
            position_key = st.selectbox(
                "Position to close",
                options=[row["Position key"] for row in position_rows],
                format_func=lambda key: (
                    f'{portfolio["positions"][key]["asset"]} · '
                    f'{portfolio["positions"][key]["side"]} · '
                    f'{portfolio["positions"][key]["contracts"]} contracts'
                ),
            )
            position = portfolio["positions"][position_key]
            close_quantity = st.number_input(
                "Contracts to close",
                min_value=1,
                max_value=int(position["contracts"]),
                value=int(position["contracts"]),
                step=1,
            )
            live_market = market_by_ticker.get(position["ticker"])
            bid_field = "yes_bid" if position["side"] == "YES" else "no_bid"
            current_bid = live_market.get(bid_field, 0.0) if live_market else 0.0
            close_submitted = st.form_submit_button(
                f"Close at ${current_bid:.3f} bid",
                icon=":material/close:",
                disabled=current_bid <= 0,
                width="stretch",
            )
        if current_bid <= 0:
            st.caption(
                "This position cannot be closed from the current view because "
                "its live bid is unavailable. Select its asset above and refresh."
            )
        if close_submitted:
            try:
                close_paper_contract(position_key, close_quantity, current_bid)
            except ValueError as error:
                st.error(str(error))
            else:
                st.toast("Simulated position closed.", icon=":material/check_circle:")
                st.rerun()

    st.subheader("Recent paper activity")
    if portfolio["transactions"]:
        activity = pd.DataFrame(reversed(portfolio["transactions"]))
        st.dataframe(
            activity.head(20),
            hide_index=True,
            column_config={
                "timestamp": st.column_config.DatetimeColumn(
                    "Time (UTC)", format="MMM DD, YYYY h:mm:ss a"
                ),
                "action": "Action",
                "ticker": "Market",
                "side": "Side",
                "contracts": "Contracts",
                "price": st.column_config.NumberColumn("Price", format="$%.3f"),
                "total": st.column_config.NumberColumn("Total", format="$%.2f"),
                "realized_profit": st.column_config.NumberColumn(
                    "Realized P/L", format="$%+.2f"
                ),
            },
        )
    else:
        st.caption("No simulated Kalshi activity has been recorded.")

with st.expander("How Sentinel will become an AI forecasting assistant", icon=":material/psychology:"):
    st.markdown(
        """
        This first release captures the market and paper-execution foundation. The next
        stage will add calibrated probability estimates, compare them with the live
        market after spreads and fees, record every decision, and recommend **no trade**
        when there is no measurable advantage. Real-money automation remains disabled
        until the paper model passes forward-looking validation and risk controls.
        """
    )
