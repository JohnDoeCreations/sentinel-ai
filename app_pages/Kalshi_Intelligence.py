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
    fetch_market_result,
    load_kalshi_paper_portfolio,
)
from data.crypto_data import CryptoDataError, get_crypto_minute_bars
from utils.kalshi_forecast import (
    estimate_direction_probability,
    forecast_decision,
)
from utils.kalshi_journal import (
    forecast_breakdowns,
    load_forecast_journal,
    record_forecast,
    summarize_forecasts,
    update_forecast_results,
)
from utils.kalshi_collector_status import collector_health, load_collector_status


st.set_page_config(
    page_title="Sentinel AI Kalshi intelligence",
    page_icon=":material/candlestick_chart:",
    layout="wide",
)


@st.cache_data(ttl=10, max_entries=10, show_spinner=False)
def load_live_markets(assets):
    """Cache the public feed briefly so normal interactions stay fast."""
    return fetch_crypto_15m_markets(tuple(assets))


@st.cache_data(ttl=30, max_entries=20, show_spinner=False)
def load_crypto_bars(asset, _api_key):
    return get_crypto_minute_bars(asset, _api_key)


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

collector_status = load_collector_status()
health = collector_health(collector_status)
with st.container(border=True):
    health_row = st.container(horizontal=True, vertical_alignment="center")
    health_row.markdown("**Automatic collector**")
    health_row.badge(
        health["label"],
        icon=":material/monitor_heart:",
        color=health["color"],
    )
    if collector_status:
        with st.container(horizontal=True):
            st.metric("Markets scanned", collector_status["markets"])
            st.metric("Forecasts recorded", collector_status["recorded"])
            st.metric("Settlements updated", collector_status["settled"])
            st.metric("Cycle warnings", len(collector_status.get("errors", [])))
        st.caption(
            f'Last cycle: {collector_status["last_run"]} · '
            f'{health["age_minutes"]:.1f} minutes ago · scheduled every 5 minutes.'
        )
        if collector_status.get("errors"):
            with st.expander("Collector warnings", icon=":material/warning:"):
                for error in collector_status["errors"]:
                    st.caption(error)
    else:
        st.caption("No collector heartbeat has been recorded on this machine yet.")

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

live_tab, portfolio_tab, journal_tab = st.tabs(
    [
        ":material/monitoring: Live market board",
        ":material/account_balance_wallet: Paper portfolio",
        ":material/lab_profile: Forecast journal",
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

                st.markdown("#### Experimental forecast")
                try:
                    massive_api_key = str(st.secrets.get("MASSIVE_API_KEY", "")).strip()
                except Exception:
                    massive_api_key = ""
                if not massive_api_key:
                    st.info("Add MASSIVE_API_KEY to enable the experimental forecast.")
                else:
                    try:
                        bars = load_crypto_bars(selected["asset"], massive_api_key)
                        forecast = estimate_direction_probability(
                            bars, selected["close_time"]
                        )
                        decision = forecast_decision(
                            forecast["probability_yes"],
                            selected["yes_ask"],
                            selected["no_ask"],
                        )
                    except (CryptoDataError, ValueError) as error:
                        st.warning(f"Forecast unavailable: {error}")
                    else:
                        with st.container(horizontal=True):
                            st.metric(
                                "Baseline YES probability",
                                f'{forecast["probability_yes"]:.1%}',
                                border=True,
                            )
                            st.metric(
                                "Price move since start",
                                f'{forecast["move_percent"]:+.3f}%',
                                border=True,
                            )
                            st.metric(
                                "Decision",
                                decision["decision"],
                                f'{decision["edge"]:+.1%} estimated edge',
                                border=True,
                            )
                        st.caption(
                            f'{forecast["method"]} · '
                            f'{forecast["data_provider"]} · '
                            f'{forecast["minutes_remaining"]:.1f} minutes remaining · '
                            "Experimental and not yet validated on forward results."
                        )
                        if st.button(
                            "Record forecast snapshot",
                            icon=":material/bookmark_add:",
                            key=f'journal_{selected["ticker"]}',
                        ):
                            try:
                                record_forecast(
                                    {
                                        "ticker": selected["ticker"],
                                        "asset": selected["asset"],
                                        "title": selected["title"],
                                        "close_time": selected["close_time"],
                                        "probability_yes": forecast["probability_yes"],
                                        "market_probability": selected["market_probability"],
                                        "yes_ask": selected["yes_ask"],
                                        "no_ask": selected["no_ask"],
                                        "decision": decision["decision"],
                                        "estimated_edge": decision["edge"],
                                        "start_price": forecast["start_price"],
                                        "current_price": forecast["current_price"],
                                        "minutes_remaining": forecast["minutes_remaining"],
                                        "minute_volatility": forecast["minute_volatility"],
                                        "move_percent": forecast["move_percent"],
                                        "spread": selected["spread"],
                                        "liquidity": selected["liquidity"],
                                        "volume_24h": selected["volume_24h"],
                                        "data_provider": forecast["data_provider"],
                                        "method": forecast["method"],
                                    }
                                )
                            except ValueError as error:
                                st.warning(str(error))
                            else:
                                st.toast("Forecast snapshot recorded.", icon=":material/check_circle:")
                                st.rerun()

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

with journal_tab:
    journal = load_forecast_journal()
    summary = summarize_forecasts(journal)
    with st.container(horizontal=True):
        st.metric("Recorded", summary["total"], border=True)
        st.metric("Settled", summary["settled"], border=True)
        st.metric(
            "Direction accuracy",
            f'{summary["accuracy"]:.1%}' if summary["accuracy"] is not None else "—",
            border=True,
        )
        st.metric(
            "Brier score",
            f'{summary["brier_score"]:.3f}' if summary["brier_score"] is not None else "—",
            help="Lower is better; 0 is perfect probability calibration.",
            border=True,
        )
    st.caption(
        f'Simulated decision profit: ${summary["paper_profit"]:+.2f} across '
        f'{summary["paper_trades"]} settled paper decisions.'
    )
    if st.button("Check official results", icon=":material/sync:", disabled=not journal):
        official_results = {}
        failures = 0
        for row in journal:
            if row.get("result") is not None:
                continue
            try:
                market_result = fetch_market_result(row["ticker"])
            except KalshiDataError:
                failures += 1
                continue
            if market_result["result"]:
                official_results[row["ticker"]] = market_result["result"]
        updated = update_forecast_results(official_results)
        st.toast(f"Updated {updated} settled forecast(s).")
        if failures:
            st.warning(f"{failures} result check(s) could not be completed.")
        if updated:
            st.rerun()
    if journal:
        breakdowns = forecast_breakdowns(journal)
        breakdown_columns = {
            "Accuracy": st.column_config.NumberColumn(format="percent"),
            "Brier score": st.column_config.NumberColumn(format="%.3f"),
            "Paper profit": st.column_config.NumberColumn(format="$%+.2f"),
        }
        st.markdown("#### Performance by asset")
        st.dataframe(
            pd.DataFrame(breakdowns["asset"]),
            hide_index=True,
            column_config=breakdown_columns,
        )
        st.markdown("#### Performance by forecast timing")
        st.dataframe(
            pd.DataFrame(breakdowns["timing"]),
            hide_index=True,
            column_config=breakdown_columns,
        )
        st.caption(
            "Breakdowns are experimental. Treat small groups as observations, not "
            "evidence of a repeatable forecasting advantage."
        )

        journal_table = pd.DataFrame(reversed(journal)).rename(
            columns={
                "recorded_at": "Recorded (UTC)",
                "asset": "Asset",
                "title": "Contract",
                "probability_yes": "Forecast YES",
                "market_probability": "Market probability",
                "decision": "Decision",
                "estimated_edge": "Estimated edge",
                "minutes_remaining": "Minutes remaining",
                "move_percent": "Price move",
                "minute_volatility": "Minute volatility",
                "spread": "YES spread",
                "data_provider": "Provider",
                "result": "Result",
            }
        )
        visible = [
            "Recorded (UTC)", "Asset", "Contract", "Forecast YES",
            "Market probability", "Decision", "Estimated edge", "Result",
            "Minutes remaining", "Price move", "Minute volatility", "YES spread",
            "Provider",
        ]
        st.dataframe(
            journal_table.reindex(columns=visible),
            hide_index=True,
            column_config={
                "Recorded (UTC)": st.column_config.DatetimeColumn(format="MMM DD, h:mm:ss a"),
                "Asset": st.column_config.TextColumn(pinned=True),
                "Forecast YES": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
                "Market probability": st.column_config.NumberColumn(format="percent"),
                "Estimated edge": st.column_config.NumberColumn(format="percent"),
                "Minutes remaining": st.column_config.NumberColumn(format="%.1f"),
                "Price move": st.column_config.NumberColumn(format="%+.3f%%"),
                "Minute volatility": st.column_config.NumberColumn(format="%.4f"),
                "YES spread": st.column_config.NumberColumn(format="$%.3f"),
            },
        )
    else:
        st.info("Record a forecast snapshot from the live market board to begin measuring results.")

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
