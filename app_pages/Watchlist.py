"""Persistent Sentinel AI stock watchlist page."""

from pathlib import Path
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.market_data import get_stock_data
from utils.explanations import explain_analysis
from utils.scanner_engine import analyze_stock
from utils.watchlist import add_symbol, load_watchlist, remove_symbols


st.set_page_config(
    page_title="Sentinel AI Watchlist",
    page_icon=":material/star:",
    layout="wide",
)

st.title(":material/star: Watchlist")
st.caption("Save stocks locally and rescan the entire list with one click.")

add_column, scan_column = st.columns([3, 1])
with add_column:
    new_symbol = st.text_input(
        "Add a stock symbol",
        placeholder="Example: AAPL",
        max_chars=10,
    ).strip().upper()

with scan_column:
    st.write("")
    st.write("")
    add_clicked = st.button(
        "Add to watchlist",
        icon=":material/add:",
        width="stretch",
    )

if add_clicked:
    if not new_symbol:
        st.warning("Enter a stock symbol first.")
    else:
        try:
            if add_symbol(new_symbol):
                st.success(f"Added {new_symbol} to the watchlist.")
            else:
                st.info(f"{new_symbol} is already on the watchlist.")
        except ValueError as error:
            st.error(str(error))

symbols = load_watchlist()

if not symbols:
    st.info("Your watchlist is empty. Add a symbol above to get started.")
    st.stop()

st.write("Saved symbols: " + ", ".join(symbols))

remove_column, action_column = st.columns([3, 1])
with remove_column:
    selected_for_removal = st.multiselect(
        "Remove symbols",
        options=symbols,
        placeholder="Choose one or more symbols",
    )

with action_column:
    st.write("")
    st.write("")
    remove_clicked = st.button(
        "Remove selected",
        icon=":material/delete:",
        disabled=not selected_for_removal,
        width="stretch",
    )

if remove_clicked:
    remove_symbols(selected_for_removal)
    st.session_state.pop("watchlist_results", None)
    st.rerun()

if st.button(
    "Scan watchlist",
    icon=":material/query_stats:",
    type="primary",
    width="stretch",
):
    results = []
    progress = st.progress(0)
    status = st.empty()

    for index, symbol in enumerate(symbols):
        status.write(f"Analyzing {symbol}...")
        try:
            result = analyze_stock(symbol)
            if result is None:
                st.warning(f"{symbol}: Not enough market data.")
            else:
                results.append(result)
        except Exception as error:
            st.error(f"{symbol}: Analysis failed — {error}")

        progress.progress((index + 1) / len(symbols))

    status.empty()
    progress.empty()
    st.session_state["watchlist_results"] = results

results = st.session_state.get("watchlist_results", [])
if not results:
    st.info("Click Scan Watchlist to load current analysis.")
    st.stop()

results_table = pd.DataFrame(
    {
        "Symbol": [item["Symbol"] for item in results],
        "Price": [item["Price"] for item in results],
        "Daily Change (%)": [item["Daily Change (%)"] for item in results],
        "Score": [f'{item["Score"]}/4' for item in results],
        "Rating": [item["Rating"] for item in results],
        "Signal": [item["Signal"] for item in results],
    }
)

st.subheader("Watchlist Results")
st.dataframe(results_table, width="stretch", hide_index=True)

selected_symbol = st.selectbox(
    "Detailed analysis",
    options=[item["Symbol"] for item in results],
)
selected_result = next(
    item for item in results if item["Symbol"] == selected_symbol
)

metric_1, metric_2, metric_3, metric_4 = st.columns(4, border=True)
metric_1.metric("Price", f'${selected_result["Price"]:,.2f}')
metric_2.metric("Daily Change", f'{selected_result["Daily Change (%)"]:.2f}%')
metric_3.metric("Score", f'{selected_result["Score"]}/4')
metric_4.metric("Signal", selected_result["Signal"])

st.info(explain_analysis(selected_result))

if st.button(
    f"Paper Trade {selected_symbol}",
    icon=":material/account_balance_wallet:",
    type="primary",
    width="stretch",
):
    st.session_state["paper_trade_symbol_input"] = selected_symbol
    st.session_state["paper_trade_context"] = {
        "Symbol": selected_symbol,
        "Score": selected_result["Score"],
        "Rating": selected_result["Rating"],
        "Signal": selected_result["Signal"],
        "Explanation": explain_analysis(selected_result),
    }
    st.session_state.pop("pending_buy", None)
    st.switch_page("app_pages/Paper_Trading.py")

chart_data = get_stock_data(selected_symbol, period="6mo", interval="1d")
required_columns = {"Open", "High", "Low", "Close"}
if not chart_data.empty and required_columns.issubset(chart_data.columns):
    open_prices = chart_data["Open"]
    high_prices = chart_data["High"]
    low_prices = chart_data["Low"]
    close_prices = chart_data["Close"]

    if isinstance(open_prices, pd.DataFrame):
        open_prices = open_prices.iloc[:, 0]
    if isinstance(high_prices, pd.DataFrame):
        high_prices = high_prices.iloc[:, 0]
    if isinstance(low_prices, pd.DataFrame):
        low_prices = low_prices.iloc[:, 0]
    if isinstance(close_prices, pd.DataFrame):
        close_prices = close_prices.iloc[:, 0]

    figure = go.Figure(
        data=[
            go.Candlestick(
                x=chart_data.index,
                open=open_prices,
                high=high_prices,
                low=low_prices,
                close=close_prices,
                name=selected_symbol,
                increasing_line_color="#22c55e",
                decreasing_line_color="#ef4444",
            )
        ]
    )
    figure.update_layout(
        height=520,
        template="plotly_dark",
        margin={"l": 10, "r": 10, "t": 20, "b": 10},
        xaxis_rangeslider_visible=True,
        yaxis_title="Price ($)",
    )
    st.plotly_chart(
        figure,
        width="stretch",
        config={"displaylogo": False, "scrollZoom": True},
    )

st.caption("Technical research only—not financial advice.")
