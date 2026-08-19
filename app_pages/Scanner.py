"""Sentinel AI market scanner page."""

from pathlib import Path
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# Make imports work when Streamlit runs this file from the pages folder.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.market_data import (
    clear_market_data_cache,
    get_stock_data,
)
from utils.explanations import explain_analysis
from utils.scanner_engine import analyze_stock
from utils.watchlist import add_symbol


st.set_page_config(
    page_title="Sentinel AI Scanner",
    page_icon=":material/query_stats:",
    layout="wide",
)

st.title(":material/query_stats: Market scanner")
st.caption(
    "Analyze price action using RSI, MACD, daily momentum, "
    "and the 5-day moving average."
)

watchlist_text = st.text_input(
    "Stock symbols",
    value="AAPL, TSLA, NVDA, MSFT",
    help="Separate symbols with commas.",
)

# dict.fromkeys removes duplicates while preserving the entered order.
symbols = list(
    dict.fromkeys(
        symbol.strip().upper()
        for symbol in watchlist_text.split(",")
        if symbol.strip()
    )
)

scan_column, refresh_column = st.columns([3, 1])

scan_clicked = scan_column.button(
    "Scan Market",
    icon=":material/query_stats:",
    type="primary",
    width="stretch",
)
refresh_clicked = refresh_column.button(
    "Refresh Data",
    icon=":material/refresh:",
    help="Clear cached quotes and download fresh market data.",
    width="stretch",
)

if refresh_clicked:
    clear_market_data_cache()
    st.session_state.pop("scanner_results", None)
    st.toast("Market-data cache cleared.")
    st.rerun()

if scan_clicked:
    if not symbols:
        st.warning("Enter at least one stock symbol.")
    else:
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        for index, symbol in enumerate(symbols):
            status_text.write(f"Analyzing {symbol}...")

            try:
                result = analyze_stock(symbol)

                if result is None:
                    st.warning(
                        f"{symbol}: No usable data was returned. Check the symbol "
                        "or choose one with at least 26 trading sessions."
                    )
                else:
                    results.append(result)
            except RuntimeError as error:
                st.error(f"{symbol}: Market-data service error — {error}")
            except ValueError as error:
                st.error(f"{symbol}: Invalid market data — {error}")
            except Exception as error:
                st.error(f"{symbol}: Analysis failed — {error}")

            progress_bar.progress((index + 1) / len(symbols))

        status_text.empty()
        progress_bar.empty()
        st.session_state["scanner_results"] = results

        if results:
            st.success(f"Analyzed {len(results)} stock(s) successfully.")

results = st.session_state.get("scanner_results", [])

if not results:
    st.info("Enter one or more symbols and click Scan Market.")
    st.stop()

results_table = pd.DataFrame(
    [
        {
            "Symbol": item["Symbol"],
            "Price": item["Price"],
            "Daily Change (%)": item["Daily Change (%)"],
            "5-Day Average": item["5-Day Average"],
            "RSI": item["RSI"],
            "MACD": item["MACD"],
            "Signal Line": item["Signal Line"],
            "Score": f'{item["Score"]}/4',
            "Rating": item["Rating"],
            "Signal": item["Signal"],
        }
        for item in results
    ]
)

st.subheader("Scan Results")
st.dataframe(
    results_table,
    width="stretch",
    hide_index=True,
)

st.subheader("Detailed Analysis")
selected_symbol = st.selectbox(
    "Select a stock",
    options=[item["Symbol"] for item in results],
)
selected_result = next(
    item for item in results if item["Symbol"] == selected_symbol
)

metric_1, metric_2, metric_3, metric_4 = st.columns(4, border=True)
metric_1.metric("Current Price", f'${selected_result["Price"]:,.2f}')
metric_2.metric(
    "Daily Change",
    f'{selected_result["Daily Change (%)"]:.2f}%',
)
metric_3.metric("Score", f'{selected_result["Score"]}/4')
metric_4.metric("Signal", selected_result["Signal"])

st.subheader("Sentinel Explanation")
st.info(explain_analysis(selected_result))
st.caption(
    "Rule-based technical analysis for research and education, not financial advice."
)

watchlist_action, alert_action, trade_action = st.columns(3)

if watchlist_action.button(
    f"Save {selected_symbol} to Watchlist",
    icon=":material/star:",
    width="stretch",
):
    if add_symbol(selected_symbol):
        st.success(f"Added {selected_symbol} to your watchlist.")
    else:
        st.info(f"{selected_symbol} is already on your watchlist.")

if alert_action.button(
    f"Create Alert for {selected_symbol}",
    icon=":material/notifications:",
    width="stretch",
):
    st.session_state["alert_symbol_input"] = selected_symbol
    st.switch_page("app_pages/Alerts.py")

if trade_action.button(
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

st.subheader(f"{selected_symbol} Price Chart")

try:
    chart_data = get_stock_data(
        selected_symbol,
        period="6mo",
        interval="1d",
    )

    required_columns = {"Open", "High", "Low", "Close"}
    if chart_data.empty or not required_columns.issubset(chart_data.columns):
        st.info("Candlestick data is not available for this symbol.")
    else:
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

        moving_average_5 = close_prices.rolling(window=5).mean()

        figure = go.Figure()
        figure.add_trace(
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
        )
        figure.add_trace(
            go.Scatter(
                x=chart_data.index,
                y=moving_average_5,
                mode="lines",
                name="5-Day Average",
                line={"color": "#38bdf8", "width": 2},
            )
        )
        figure.update_layout(
            height=560,
            margin={"l": 10, "r": 10, "t": 20, "b": 10},
            xaxis_title="Date",
            yaxis_title="Price ($)",
            hovermode="x unified",
            template="plotly_dark",
            xaxis_rangeslider_visible=True,
            legend={"orientation": "h", "y": 1.02, "x": 0},
        )

        st.plotly_chart(
            figure,
            width="stretch",
            config={
                "displaylogo": False,
                "scrollZoom": True,
            },
        )
except Exception as error:
    st.warning(f"Could not load the candlestick chart: {error}")

strengths_column, weaknesses_column = st.columns(2)

with strengths_column:
    st.success("Strengths")
    if selected_result["Strengths"]:
        for strength in selected_result["Strengths"]:
            st.write(f"✓ {strength}")
    else:
        st.write("No strengths detected.")

with weaknesses_column:
    st.error("Weaknesses")
    if selected_result["Weaknesses"]:
        for weakness in selected_result["Weaknesses"]:
            st.write(f"• {weakness}")
    else:
        st.write("No weaknesses detected.")
