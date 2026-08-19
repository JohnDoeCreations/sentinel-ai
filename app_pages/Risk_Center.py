"""Portfolio-wide protection and planned-risk dashboard."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.alerts import load_alert_state
from utils.paper_trading import load_portfolio
from utils.portfolio_analytics import (
    protection_risk_rows,
    protection_risk_summary,
)


st.set_page_config(
    page_title="Sentinel AI risk center",
    page_icon=":material/health_and_safety:",
    layout="wide",
)

st.title(":material/health_and_safety: Portfolio risk center")
st.caption(
    "See which simulated positions are protected and how much capital is at risk."
)
st.warning(
    "Alerts notify you when a threshold is reached; they do not automatically "
    "sell shares or place brokerage orders."
)

portfolio = load_portfolio()
alert_state = load_alert_state()
rows = protection_risk_rows(portfolio["positions"], alert_state["alerts"])
summary = protection_risk_summary(rows)

with st.container(horizontal=True):
    st.metric("Open positions", summary["positions"], border=True)
    st.metric(
        "Protection coverage",
        f'{summary["coverage_percent"]:.0f}%',
        f'{summary["protected_positions"]} protected',
        border=True,
    )
    st.metric(
        "Planned capital at risk",
        f'${summary["planned_risk"]:,.2f}',
        border=True,
    )
    st.metric(
        "Unprotected cost basis",
        f'${summary["unprotected_value"]:,.2f}',
        border=True,
    )
    st.metric(
        "Needs attention",
        summary["attention_count"],
        border=True,
    )

if not rows:
    st.info(
        "Open a simulated position in Paper trading to begin portfolio risk tracking."
    )
    st.stop()

if summary["unprotected_value"] > 0:
    unprotected = ", ".join(
        row["Symbol"] for row in rows if row["Status"] != "Protected"
    )
    st.warning(
        f"Protection needed for: {unprotected}. Add protection from a new "
        "paper buy or create matching position alerts on the Alerts page."
    )
elif summary["attention_count"]:
    st.warning(
        "Every position is protected, but one or more linked alerts has "
        "triggered or encountered a monitoring error."
    )
else:
    st.success("Every open position has active stop-loss and take-profit alerts.")

with st.container(border=True):
    st.subheader("Protection by position")
    risk_table = pd.DataFrame(rows)
    st.dataframe(
        risk_table,
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

with st.container(border=True):
    st.subheader("Capital exposure")
    exposure = risk_table[["Symbol", "Cost Basis"]].sort_values(
        "Cost Basis", ascending=True
    )
    st.bar_chart(
        exposure,
        x="Symbol",
        y="Cost Basis",
        horizontal=True,
        x_label="Cost basis ($)",
        y_label="Symbol",
    )

st.caption(
    "Planned capital at risk is estimated from each position's cost basis and "
    "linked stop percentage. Market gaps can cause actual outcomes to differ."
)
