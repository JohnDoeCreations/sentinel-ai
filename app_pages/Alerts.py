"""Persistent in-app alerts for Sentinel AI."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.alerts import (
    add_alert,
    delete_alert,
    load_alert_state,
    set_alert_enabled,
)
from utils.alert_monitor import check_enabled_alerts
from data.market_data import clear_market_data_cache
from utils.paper_trading import load_portfolio
from utils.scanner_engine import analyze_stock
from utils.watchlist import load_watchlist


ALERT_TYPES = {
    "Price rises above": "price_above",
    "Price falls below": "price_below",
    "Scanner score reaches": "score_at_least",
    "Signal becomes": "signal_equals",
    "RSI rises above": "rsi_above",
    "RSI falls below": "rsi_below",
    "Paper position gain reaches (%)": "position_gain_at_least",
    "Paper position loss reaches (%)": "position_loss_at_most",
}
TYPE_LABELS = {value: label for label, value in ALERT_TYPES.items()}
SIGNALS = [
    "BULLISH WATCH",
    "BEARISH WATCH",
    "OVERBOUGHT WATCH",
    "OVERSOLD WATCH",
    "NEUTRAL",
]


st.set_page_config(
    page_title="Sentinel AI monitoring center",
    page_icon=":material/notifications:",
    layout="wide",
)
with st.container(horizontal=True, vertical_alignment="center"):
    with st.container():
        st.title(":material/notifications: Monitoring center")
        st.caption(
            "Track persistent market rules, position protection, and newly "
            "triggered conditions."
        )
    st.badge(
        "Cloud monitoring",
        icon=":material/cloud_done:",
        color="violet",
    )

st.caption(
    "Enabled alerts are checked every 30 minutes during regular U.S. market "
    "hours—even when the browser is closed. New triggers can also be emailed."
)

overview_state = load_alert_state()
overview_alerts = overview_state["alerts"]
overview_monitor = overview_state.get("monitor", {})
overview_enabled = [
    alert for alert in overview_alerts if alert.get("enabled", True)
]
overview_triggered = [
    alert for alert in overview_enabled if alert.get("is_triggered")
]

with st.container(horizontal=True):
    st.metric("Active rules", len(overview_enabled), border=True)
    st.metric("Triggered now", len(overview_triggered), border=True)
    st.metric(
        "Last cloud check",
        overview_monitor.get("last_checked_at") or "Not checked yet",
        border=True,
    )
    st.metric(
        "Check errors",
        overview_monitor.get("errors", 0),
        border=True,
    )

if overview_triggered:
    with st.container(border=True):
        st.subheader(":material/notification_important: Needs attention")
        for alert in overview_triggered[:5]:
            label = TYPE_LABELS.get(alert["type"], alert["type"])
            st.warning(
                f'**{alert["symbol"]}** · {label} {alert["target"]}',
                icon=":material/notifications_active:",
            )

watchlist = load_watchlist()
portfolio = load_portfolio()
available_symbols = list(
    dict.fromkeys(watchlist + list(portfolio["positions"]) + ["AAPL"])
)
preferred_symbol = st.session_state.get("alert_symbol_input")
if preferred_symbol and preferred_symbol not in available_symbols:
    available_symbols.insert(0, preferred_symbol)
preferred_symbol_index = (
    available_symbols.index(preferred_symbol)
    if preferred_symbol in available_symbols
    else 0
)

with st.expander(
    "Create a monitoring rule",
    icon=":material/add_alert:",
    expanded=not bool(overview_alerts),
):
    alert_label = st.selectbox("Condition", options=list(ALERT_TYPES))
    alert_type = ALERT_TYPES[alert_label]

    with st.form("create_alert_form"):
        symbol = st.selectbox(
            "Symbol",
            options=available_symbols,
            index=preferred_symbol_index,
        )

        if alert_type == "signal_equals":
            target = st.selectbox("Target signal", options=SIGNALS)
        elif alert_type == "score_at_least":
            target = st.number_input(
                "Target score",
                min_value=1,
                max_value=4,
                value=3,
                step=1,
            )
        elif alert_type in {"rsi_above", "rsi_below"}:
            target = st.number_input(
                "Target RSI",
                min_value=0.0,
                max_value=100.0,
                value=70.0 if alert_type == "rsi_above" else 30.0,
                step=1.0,
            )
        elif alert_type in {"position_gain_at_least", "position_loss_at_most"}:
            target = st.number_input(
                "Target move (%)",
                min_value=0.1,
                value=5.0,
                step=0.5,
            )
        else:
            target = st.number_input(
                "Target price ($)",
                min_value=0.01,
                value=100.0,
                step=1.0,
            )

        create_submitted = st.form_submit_button(
            "Save alert",
            icon=":material/save:",
            type="primary",
            width="stretch",
        )

    if create_submitted:
        add_alert(symbol, alert_type, target)
        st.success(f"Alert saved for {symbol}.")
        st.rerun()

st.subheader("Monitor and manage")
st.caption(
    "Run an immediate check or enable a faster browser-based interval while "
    "this page remains open."
)
monitor_controls = st.container(horizontal=True, vertical_alignment="bottom")
automatic_monitoring = monitor_controls.toggle(
    "Automatic monitoring",
    value=False,
    key="automatic_alert_monitoring",
    help="Checks enabled alerts while this page stays open.",
)
interval_label = monitor_controls.selectbox(
    "Check interval",
    options=["5 minutes", "15 minutes", "30 minutes"],
    index=0,
    disabled=not automatic_monitoring,
)
intervals = {
    "5 minutes": "5m",
    "15 minutes": "15m",
    "30 minutes": "30m",
}
run_every = intervals[interval_label] if automatic_monitoring else None


@st.fragment(run_every=run_every)
def alert_monitor():
    state = load_alert_state()
    alerts = state["alerts"]
    enabled_count = sum(alert.get("enabled", True) for alert in alerts)

    manual_check = st.button(
        "Check alerts now",
        icon=":material/refresh:",
        type="primary",
        disabled=enabled_count == 0,
        key="manual_alert_check",
    )

    should_check = automatic_monitoring or manual_check
    if should_check and enabled_count:
        if manual_check:
            clear_market_data_cache()
        with st.spinner(f"Checking {enabled_count} active alert(s)..."):
            result = check_enabled_alerts(
                analyze_stock,
                positions=load_portfolio()["positions"],
            )
        state = load_alert_state()
        alerts = state["alerts"]

        for trigger in result["newly_triggered"]:
            st.warning(trigger["message"], icon=":material/notifications_active:")
        for error in result["errors"]:
            st.error(
                f'{error["symbol"]}: Alert check failed — {error["message"]}'
            )
        if manual_check and not result["errors"]:
            st.success("Alert check complete.")

    monitor = state.get("monitor", {})
    st.caption(
        f'Latest check: {monitor.get("last_checked_at") or "Not checked yet"} · '
        f'{monitor.get("new_triggers", 0)} new triggers · '
        f'{monitor.get("errors", 0)} errors'
    )

    if automatic_monitoring:
        st.caption(
            f"Automatic monitoring is active every {interval_label.lower()}. "
            "This faster in-page check supplements the 30-minute cloud monitor."
        )

    st.subheader("Active and saved rules")
    if not alerts:
        st.info("No alerts saved yet.")
    else:
        for alert in alerts:
            status = "Triggered" if alert.get("is_triggered") else "Waiting"
            enabled = alert.get("enabled", True)
            label = TYPE_LABELS.get(alert["type"], alert["type"])
            target = alert["target"]

            with st.container(border=True):
                details_column, toggle_column, delete_column = st.columns([4, 1, 1])
                with details_column:
                    st.write(f'**{alert["symbol"]} — {label} {target}**')
                    if alert.get("source") == "paper_trade":
                        st.badge(
                            "Paper-trade protection",
                            icon=":material/health_and_safety:",
                            color="blue",
                        )
                    st.caption(
                        f'Status: {status} · Last checked: '
                        f'{alert.get("last_checked_at") or "Never"} · '
                        f'Last value: {alert.get("last_value")}'
                    )
                    if alert.get("last_error"):
                        st.caption(f'Last error: {alert["last_error"]}')
                with toggle_column:
                    toggle_label = "Disable" if enabled else "Enable"
                    if st.button(
                        toggle_label,
                        key=f'toggle_{alert["id"]}',
                    ):
                        set_alert_enabled(alert["id"], not enabled)
                        st.rerun(scope="fragment")
                with delete_column:
                    if st.button(
                        "Delete",
                        icon=":material/delete:",
                        key=f'delete_{alert["id"]}',
                    ):
                        delete_alert(alert["id"])
                        st.rerun(scope="fragment")

    st.subheader("Trigger history")
    history = state["history"]
    if history:
        history_table = pd.DataFrame(reversed(history)).rename(
            columns={
                "timestamp": "Time (UTC)",
                "symbol": "Symbol",
                "type": "Rule",
                "message": "Trigger",
            }
        )
        history_table["Rule"] = history_table["Rule"].map(TYPE_LABELS).fillna(
            history_table["Rule"]
        )
        st.dataframe(
            history_table,
            hide_index=True,
            column_config={
                "Time (UTC)": st.column_config.DatetimeColumn(
                    format="MMM DD, YYYY h:mm a"
                ),
                "Symbol": st.column_config.TextColumn(pinned=True),
            },
        )
    else:
        st.info("No alerts have triggered yet.")


alert_monitor()
