"""Decision-focused command center for Sentinel AI."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.alerts import load_alert_state
from utils.bulk_scanner import load_bulk_scan_state
from utils.paper_trading import load_portfolio
from utils.portfolio_analytics import protection_risk_rows, protection_risk_summary
from utils.stock_universe import load_universe
from utils.watchlist import load_watchlist


st.set_page_config(
    page_title="Sentinel AI command center",
    page_icon=":material/dashboard:",
    layout="wide",
)

watchlist = load_watchlist()
alert_state = load_alert_state()
scan_state = load_bulk_scan_state()
universe = load_universe()
portfolio = load_portfolio()

positions = portfolio.get("positions", {})
transactions = portfolio.get("transactions", [])
equity_history = portfolio.get("equity_history", [])
alerts = alert_state.get("alerts", [])
alert_history = alert_state.get("history", [])
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

scan_results = list(scan_state.get("results", {}).values())
ranked_results = sorted(
    scan_results,
    key=lambda item: (
        float(item.get("Score", 0) or 0),
        float(item.get("Daily Change (%)", 0) or 0),
    ),
    reverse=True,
)
opportunity_count = sum(
    float(item.get("Score", 0) or 0) >= 3 for item in scan_results
)
positive_count = sum(
    float(item.get("Daily Change (%)", 0) or 0) > 0 for item in scan_results
)
breadth_percent = (
    positive_count / len(scan_results) * 100 if scan_results else 0.0
)
average_change = (
    sum(float(item.get("Daily Change (%)", 0) or 0) for item in scan_results)
    / len(scan_results)
    if scan_results
    else 0.0
)
if not scan_results:
    scanner_tone = "Awaiting data"
    tone_color = "gray"
elif average_change >= 0.5:
    scanner_tone = "Constructive"
    tone_color = "green"
elif average_change <= -0.5:
    scanner_tone = "Defensive"
    tone_color = "red"
else:
    scanner_tone = "Mixed"
    tone_color = "orange"

risk_rows = protection_risk_rows(positions, alerts)
risk_summary = protection_risk_summary(risk_rows)

with st.container(horizontal=True, vertical_alignment="center"):
    with st.container():
        st.title(":material/dashboard: Command center")
        st.caption(
            "Market intelligence, portfolio exposure, and time-sensitive "
            "signals in one decision workspace."
        )
    st.badge(scanner_tone, icon=":material/pulse_alert:", color=tone_color)

with st.container(horizontal=True):
    st.page_link(
        "app_pages/Stock_Universe.py",
        label="Run market scan",
        icon=":material/radar:",
    )
    st.page_link(
        "app_pages/Trade_Planner.py",
        label="Plan a trade",
        icon=":material/calculate:",
    )
    st.page_link(
        "app_pages/Alerts.py",
        label="Review alerts",
        icon=":material/notifications:",
    )

with st.container(horizontal=True):
    st.metric(
        "Paper portfolio",
        f"${latest_value:,.2f}",
        f"{return_percent:+.2f}% total",
        border=True,
        chart_data=[
            float(row.get("portfolio_value", 0) or 0)
            for row in equity_history[-12:]
        ]
        or None,
        chart_type="line",
    )
    st.metric(
        "Scanner breadth",
        f"{breadth_percent:.0f}% positive" if scan_results else "No scan yet",
        f"{len(scan_results)} analyzed",
        border=True,
        delta_color="off",
    )
    st.metric(
        "High-score opportunities",
        opportunity_count,
        "Score 3 or higher",
        border=True,
        delta_color="off",
    )
    st.metric(
        "Active alerts",
        len(active_alerts),
        f"{len(triggered_alerts)} triggered",
        border=True,
        delta_color="off",
    )

intelligence_column, portfolio_column = st.columns([1.25, 1])

with intelligence_column:
    with st.container(border=True, height="stretch"):
        st.subheader(":material/query_stats: Scanner pulse")
        st.caption(
            f'Last scan: {scan_state.get("last_run_at") or "Not run yet"} · '
            f'Universe: {universe.get("name", "Not configured")}'
        )
        with st.container(horizontal=True):
            st.metric("Average move", f"{average_change:+.2f}%")
            st.metric("Advancing", positive_count)
            st.metric("Scan errors", len(scan_state.get("errors", {})))

        if ranked_results:
            opportunities = pd.DataFrame(ranked_results[:6])
            companies = universe.get("companies", {})
            opportunities.insert(
                0,
                "Company",
                opportunities["Symbol"].map(companies).fillna(
                    opportunities["Symbol"]
                ),
            )
            columns = [
                column
                for column in [
                    "Company",
                    "Symbol",
                    "Price",
                    "Daily Change (%)",
                    "Score",
                    "Signal",
                ]
                if column in opportunities
            ]
            st.dataframe(
                opportunities[columns],
                hide_index=True,
                height=250,
                column_config={
                    "Company": st.column_config.TextColumn(pinned=True),
                    "Price": st.column_config.NumberColumn(format="$%.2f"),
                    "Daily Change (%)": st.column_config.NumberColumn(
                        format="%+.2f%%"
                    ),
                    "Score": st.column_config.ProgressColumn(
                        min_value=0, max_value=4
                    ),
                },
            )
        else:
            st.info(
                "Run a stock-universe scan to populate ranked opportunities.",
                icon=":material/radar:",
            )

with portfolio_column:
    with st.container(border=True, height="stretch"):
        st.subheader(":material/account_balance_wallet: Portfolio trajectory")
        st.caption(
            f"${cash:,.2f} available cash · {len(positions)} open positions"
        )
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
            if not equity_table.empty:
                st.line_chart(
                    equity_table,
                    x="date",
                    y="portfolio_value",
                    x_label="Date",
                    y_label="Portfolio value ($)",
                    height=285,
                )
            else:
                st.info("No valid portfolio snapshots are available yet.")
        else:
            st.info(
                "Paper-trading activity will create the portfolio trend.",
                icon=":material/show_chart:",
            )

risk_column, alerts_column = st.columns(2)

with risk_column:
    with st.container(border=True, height="stretch"):
        st.subheader(":material/health_and_safety: Risk posture")
        with st.container(horizontal=True):
            st.metric(
                "Protection coverage",
                f'{risk_summary["coverage_percent"]:.0f}%'
                if positions
                else "No positions",
            )
            st.metric(
                "Planned risk",
                f'${risk_summary["planned_risk"]:,.2f}',
            )
            st.metric(
                "Needs attention",
                risk_summary["attention_count"],
            )
        if not positions:
            st.caption("Risk coverage appears after a paper position is opened.")
        elif risk_summary["coverage_percent"] < 100:
            st.warning(
                f'{risk_summary["protected_positions"]} of '
                f'{risk_summary["positions"]} positions have stop and target '
                "protection.",
                icon=":material/gpp_maybe:",
            )
        else:
            st.success(
                "Every open position has stop and target protection.",
                icon=":material/verified_user:",
            )

with alerts_column:
    with st.container(border=True, height="stretch"):
        st.subheader(":material/notifications_active: Alert center")
        if triggered_alerts:
            for alert in triggered_alerts[:3]:
                st.warning(
                    f'**{alert.get("symbol", "—")}** · '
                    f'{alert.get("type", "Alert").replace("_", " ")} · '
                    f'Target {alert.get("target", "—")}',
                    icon=":material/notification_important:",
                )
        elif active_alerts:
            st.success(
                f"{len(active_alerts)} alerts are monitoring normally.",
                icon=":material/check_circle:",
            )
        else:
            st.info(
                "Create an alert to monitor a price, signal, or position.",
                icon=":material/add_alert:",
            )
        monitor = alert_state.get("monitor", {})
        st.caption(
            f'Last checked: {monitor.get("last_checked_at") or "Not checked yet"}'
        )

activity_column, focus_column = st.columns([1.35, 1])

with activity_column:
    with st.container(border=True, height="stretch"):
        st.subheader(":material/history: Recent activity")
        activity_rows = []
        for trade in transactions[-4:]:
            activity_rows.append(
                {
                    "Time": trade.get("timestamp"),
                    "Activity": f'{trade.get("side", "Trade")} '
                    f'{trade.get("symbol", "")}',
                    "Detail": f'{int(trade.get("shares", 0))} shares at '
                    f'${float(trade.get("price", 0)):,.2f}',
                }
            )
        for event in alert_history[-4:]:
            activity_rows.append(
                {
                    "Time": event.get("timestamp"),
                    "Activity": f'Alert · {event.get("symbol", "")}',
                    "Detail": event.get("message", "Alert triggered"),
                }
            )
        if activity_rows:
            activity_table = pd.DataFrame(activity_rows)
            activity_table["Time"] = pd.to_datetime(
                activity_table["Time"], errors="coerce", utc=True
            )
            activity_table = activity_table.sort_values(
                "Time", ascending=False
            ).head(6)
            st.dataframe(
                activity_table,
                hide_index=True,
                column_config={
                    "Time": st.column_config.DatetimeColumn(
                        format="MMM DD, h:mm a"
                    ),
                    "Activity": st.column_config.TextColumn(pinned=True),
                },
            )
        else:
            st.caption("Recent trades and triggered alerts will appear here.")

with focus_column:
    with st.container(border=True, height="stretch"):
        st.subheader(":material/star: Research focus")
        st.metric("Watchlist", len(watchlist))
        if watchlist:
            st.caption(" · ".join(watchlist[:12]))
            if len(watchlist) > 12:
                st.caption(f"+{len(watchlist) - 12} additional symbols")
        else:
            st.caption("Save important symbols to keep them in focus.")
        st.page_link(
            "app_pages/Watchlist.py",
            label="Open watchlist",
            icon=":material/arrow_forward:",
        )

st.caption(
    "Sentinel AI provides research and simulated execution only. "
    "It does not place live orders or provide financial advice."
)
