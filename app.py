"""Sentinel AI application shell and navigation."""

import streamlit as st

from utils.data_management import DataRestoreError, ensure_daily_backup


st.set_page_config(
    page_title="Sentinel AI",
    page_icon=":material/shield:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Protect local personal data once per day without including API secrets.
backup_warning = None
try:
    ensure_daily_backup()
except (DataRestoreError, OSError) as error:
    backup_warning = str(error)

pages = {
    "Overview": [
        st.Page(
            "app_pages/Dashboard.py",
            title="Dashboard",
            icon=":material/dashboard:",
            default=True,
        ),
    ],
    "Research": [
        st.Page(
            "app_pages/Market_Analysis.py",
            title="Market analysis",
            icon=":material/finance_mode:",
        ),
        st.Page(
            "app_pages/News_Sentiment.py",
            title="News & sentiment",
            icon=":material/newspaper:",
        ),
        st.Page(
            "app_pages/Scanner.py",
            title="Market scanner",
            icon=":material/query_stats:",
        ),
        st.Page(
            "app_pages/Stock_Universe.py",
            title="Stock universe",
            icon=":material/public:",
        ),
        st.Page(
            "app_pages/Watchlist.py",
            title="Watchlist",
            icon=":material/star:",
        ),
        st.Page(
            "app_pages/Backtester.py",
            title="Backtester",
            icon=":material/science:",
        ),
        st.Page(
            "app_pages/Trade_Planner.py",
            title="Trade planner",
            icon=":material/calculate:",
        ),
    ],
    "Portfolio": [
        st.Page(
            "app_pages/Paper_Trading.py",
            title="Paper trading",
            icon=":material/account_balance_wallet:",
        ),
        st.Page(
            "app_pages/Portfolio_Performance.py",
            title="Portfolio performance",
            icon=":material/monitoring:",
        ),
        st.Page(
            "app_pages/Risk_Center.py",
            title="Risk center",
            icon=":material/health_and_safety:",
        ),
        st.Page(
            "app_pages/Trade_History.py",
            title="Trade history",
            icon=":material/receipt_long:",
        ),
    ],
    "Monitoring": [
        st.Page(
            "app_pages/Alerts.py",
            title="Alerts",
            icon=":material/notifications:",
        ),
        st.Page(
            "app_pages/Performance.py",
            title="Strategy performance",
            icon=":material/analytics:",
        ),
    ],
    "System": [
        st.Page(
            "app_pages/Data_Management.py",
            title="Data management",
            icon=":material/database:",
        ),
    ],
}

with st.sidebar:
    st.markdown("## :material/shield: Sentinel AI")
    st.caption("Market intelligence and simulated execution")

page = st.navigation(pages, position="sidebar", expanded=True)

with st.sidebar:
    st.badge("System online", icon=":material/check_circle:", color="green")
    st.caption("Research and simulation only · No live orders")
    if backup_warning:
        st.warning(f"Daily backup needs attention: {backup_warning}")

page.run()
