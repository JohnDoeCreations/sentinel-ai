"""Explainable single-symbol market analysis for Sentinel AI."""

from pathlib import Path
import sys

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.market_data import MarketDataError, clear_market_data_cache
from utils.market_analysis import build_market_analysis
from utils.watchlist import add_symbol


st.set_page_config(
    page_title="Sentinel AI market analysis",
    page_icon=":material/finance_mode:",
    layout="wide",
)

st.title(":material/finance_mode: Market analysis")
st.caption(
    "Turn price, momentum, trend, and volatility data into an explainable market view."
)

with st.form("market_analysis_form", border=False):
    input_row = st.container(horizontal=True, vertical_alignment="bottom")
    symbol = input_row.text_input(
        "Stock symbol",
        value=st.session_state.get("analysis_symbol", "AAPL"),
        placeholder="AAPL",
        key="market_analysis_symbol_input",
    )
    analyze_clicked = input_row.form_submit_button(
        "Analyze stock",
        icon=":material/analytics:",
        type="primary",
    )

if st.button(
    "Refresh market data",
    icon=":material/refresh:",
    help="Clear cached quotes before running a new analysis.",
):
    clear_market_data_cache()
    st.session_state.pop("market_analysis_result", None)
    st.toast("Market-data cache cleared.")

if analyze_clicked:
    try:
        with st.spinner(f"Analyzing {symbol.strip().upper()}..."):
            result = build_market_analysis(symbol)
        if result is None:
            st.warning(
                "No usable analysis was returned. Check the symbol or choose one "
                "with at least 50 trading sessions."
            )
            st.session_state.pop("market_analysis_result", None)
        else:
            st.session_state["market_analysis_result"] = result
            st.session_state["analysis_symbol"] = result["Symbol"]
    except MarketDataError as error:
        st.error(str(error))
    except ValueError as error:
        st.error(str(error))
    except Exception as error:
        st.error(f"Analysis could not be completed: {error}")

result = st.session_state.get("market_analysis_result")
if not result:
    st.info("Enter a symbol and select **Analyze stock** to create a market report.")
    st.stop()

st.subheader(f'{result["Symbol"]} market view')

with st.container(horizontal=True):
    st.metric(
        "Price",
        f'${result["Price"]:,.2f}',
        f'{result["Daily Change (%)"]:+.2f}% today',
        border=True,
    )
    st.metric(
        "Technical bias",
        result["Bias"],
        result["Trend"],
        border=True,
    )
    st.metric("RSI (14)", f'{result["RSI"]:.1f}', border=True)
    st.metric(
        "Volatility",
        result["Volatility"],
        f'{result["ATR (%)"]:.2f}% ATR',
        delta_color="off",
        border=True,
    )
    st.metric(
        "5-day return",
        f'{result["5-Day Return (%)"]:+.2f}%',
        border=True,
    )

with st.container(border=True):
    st.subheader("Sentinel summary")
    st.write(result["Summary"])
    st.caption(result["Volume Context"])

chart_column, levels_column = st.columns([2, 1])

with chart_column:
    with st.container(border=True):
        st.subheader("Six-month price trend")
        chart_data = result["Chart Data"].copy()
        chart_data["20-day average"] = chart_data["Close"].rolling(20).mean()
        chart_data["50-day average"] = chart_data["Close"].rolling(50).mean()
        st.line_chart(
            chart_data[["Close", "20-day average", "50-day average"]],
            y_label="Price ($)",
        )

with levels_column:
    with st.container(border=True):
        st.subheader("Key price levels")
        st.metric(
            "Resistance",
            f'${result["Resistance"]:,.2f}',
            f'{result["Distance to Resistance (%)"]:.2f}% away',
            delta_color="off",
        )
        st.metric(
            "Support",
            f'${result["Support"]:,.2f}',
            f'{result["Distance to Support (%)"]:.2f}% cushion',
            delta_color="off",
        )
        st.metric("20-day average", f'${result["20-Day Average"]:,.2f}')
        st.metric("50-day average", f'${result["50-Day Average"]:,.2f}')

st.subheader("Scenario map")
scenario_columns = st.columns(3, border=True)
with scenario_columns[0]:
    st.markdown("**:green[:material/trending_up: Bull case]**")
    st.write(result["Bull Case"])
with scenario_columns[1]:
    st.markdown("**:blue[:material/horizontal_rule: Base case]**")
    st.write(result["Base Case"])
with scenario_columns[2]:
    st.markdown("**:red[:material/trending_down: Bear case]**")
    st.write(result["Bear Case"])

factor_columns = st.columns(2)
with factor_columns[0]:
    with st.container(border=True):
        st.subheader("Constructive factors")
        if result["Bullish Factors"]:
            for factor in result["Bullish Factors"]:
                st.write(f":material/check_circle: {factor}")
        else:
            st.write("No constructive factors were detected.")

with factor_columns[1]:
    with st.container(border=True):
        st.subheader("Risks to monitor")
        if result["Risk Factors"]:
            for factor in result["Risk Factors"]:
                st.write(f":material/warning: {factor}")
        else:
            st.write("No major technical risks were detected.")

with st.container(horizontal=True):
    if st.button(
        f'Save {result["Symbol"]} to watchlist',
        icon=":material/star:",
    ):
        if add_symbol(result["Symbol"]):
            st.success(f'Added {result["Symbol"]} to your watchlist.')
        else:
            st.info(f'{result["Symbol"]} is already on your watchlist.')

    if st.button(
        f'Paper trade {result["Symbol"]}',
        icon=":material/account_balance_wallet:",
        type="primary",
    ):
        st.session_state["paper_trade_symbol_input"] = result["Symbol"]
        st.session_state["paper_trade_context"] = {
            "Symbol": result["Symbol"],
            "Context Label": "Market analysis",
            "Rating": result["Bias"],
            "Signal": result["Trend"],
            "Explanation": result["Summary"],
        }
        st.session_state.pop("pending_buy", None)
        st.switch_page("app_pages/Paper_Trading.py")

st.caption(
    "Explainable, rule-based technical research only. Scenarios are not predictions "
    "or financial advice."
)
