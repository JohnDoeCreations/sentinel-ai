from pathlib import Path

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Sentinel AI Trade History",
    page_icon=":material/receipt_long:",
    layout="wide",
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_FOLDER = PROJECT_ROOT / "backtesting" / "results"


st.title(":material/receipt_long: Trade history")

st.caption(
    "Review saved trades from previous backtests."
)


trade_files = sorted(
    RESULTS_FOLDER.glob("*_backtest.csv")
)


if not trade_files:
    st.warning("No saved trade logs were found.")

    st.info(
        "Run a backtest first so Sentinel AI can create "
        "CSV trade logs inside backtesting/results."
    )

    st.stop()


symbol_options = [
    file_path.stem.replace("_backtest", "")
    for file_path in trade_files
]


selected_symbol = st.selectbox(
    "Select a stock",
    options=symbol_options,
)


selected_file = (
    RESULTS_FOLDER
    / f"{selected_symbol}_backtest.csv"
)


trade_data = pd.read_csv(selected_file)


if trade_data.empty:
    st.info(
        f"{selected_symbol} has a saved trade log, "
        "but no qualifying trades were recorded."
    )

    st.stop()


numeric_columns = [
    "Entry Price",
    "Exit Price",
    "Shares",
    "Profit ($)",
    "Return (%)",
    "Score",
    "RSI",
    "MACD",
    "Signal Line",
    "EMA 20",
    "EMA 50",
    "ATR",
]


for column in numeric_columns:
    if column in trade_data.columns:
        trade_data[column] = pd.to_numeric(
            trade_data[column],
            errors="coerce",
        )


total_trades = len(trade_data)

wins = 0
losses = 0

if "Result" in trade_data.columns:
    wins = (
        trade_data["Result"]
        .astype(str)
        .str.lower()
        .eq("win")
        .sum()
    )

    losses = (
        trade_data["Result"]
        .astype(str)
        .str.lower()
        .eq("loss")
        .sum()
    )


win_rate = (
    wins / total_trades * 100
    if total_trades > 0
    else 0
)


net_profit = (
    trade_data["Profit ($)"].sum()
    if "Profit ($)" in trade_data.columns
    else 0
)


average_return = (
    trade_data["Return (%)"].mean()
    if "Return (%)" in trade_data.columns
    else 0
)


best_trade = (
    trade_data["Return (%)"].max()
    if "Return (%)" in trade_data.columns
    else 0
)


worst_trade = (
    trade_data["Return (%)"].min()
    if "Return (%)" in trade_data.columns
    else 0
)


metric_1, metric_2, metric_3, metric_4 = st.columns(4, border=True)


metric_1.metric(
    "Total Trades",
    total_trades,
)


metric_2.metric(
    "Win Rate",
    f"{win_rate:.2f}%",
)


metric_3.metric(
    "Net Profit",
    f"${net_profit:,.2f}",
)


metric_4.metric(
    "Average Return",
    f"{average_return:.2f}%",
)


metric_5, metric_6, metric_7, metric_8 = st.columns(4, border=True)


metric_5.metric(
    "Wins",
    int(wins),
)


metric_6.metric(
    "Losses",
    int(losses),
)


metric_7.metric(
    "Best Trade",
    f"{best_trade:.2f}%",
)


metric_8.metric(
    "Worst Trade",
    f"{worst_trade:.2f}%",
)



st.subheader("Filter Trades")


filter_column_1, filter_column_2 = st.columns(2)


with filter_column_1:
    result_filter = st.selectbox(
        "Result",
        options=[
            "All",
            "Win",
            "Loss",
        ],
    )


with filter_column_2:
    exit_reason_options = ["All"]

    if "Exit Reason" in trade_data.columns:
        exit_reason_options += sorted(
            trade_data["Exit Reason"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

    exit_reason_filter = st.selectbox(
        "Exit reason",
        options=exit_reason_options,
    )


filtered_data = trade_data.copy()


if (
    result_filter != "All"
    and "Result" in filtered_data.columns
):
    filtered_data = filtered_data[
        filtered_data["Result"] == result_filter
    ]


if (
    exit_reason_filter != "All"
    and "Exit Reason" in filtered_data.columns
):
    filtered_data = filtered_data[
        filtered_data["Exit Reason"]
        == exit_reason_filter
    ]


st.subheader("Saved Trades")


st.dataframe(
    filtered_data,
    width="stretch",
    hide_index=True,
)


if "Profit ($)" in trade_data.columns:
    st.subheader("Profit by Trade")

    profit_chart_data = (
        trade_data[["Profit ($)"]]
        .reset_index()
        .rename(
            columns={
                "index": "Trade Number"
            }
        )
        .set_index("Trade Number")
    )

    st.bar_chart(
        profit_chart_data,
        width="stretch",
    )


if (
    "Exit Reason" in trade_data.columns
    and not trade_data["Exit Reason"].dropna().empty
):
    st.subheader("Exit Reason Breakdown")

    exit_reason_counts = (
        trade_data["Exit Reason"]
        .value_counts()
        .rename_axis("Exit Reason")
        .to_frame("Trades")
    )

    st.bar_chart(
        exit_reason_counts,
        width="stretch",
    )



download_data = filtered_data.to_csv(
    index=False
).encode("utf-8")


st.download_button(
    label="Download Filtered Trade History",
    data=download_data,
    file_name=(
        f"{selected_symbol}_filtered_trades.csv"
    ),
    mime="text/csv",
    width="stretch",
)
