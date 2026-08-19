from pathlib import Path

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Sentinel AI Performance",
    page_icon=":material/analytics:",
    layout="wide",
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_FOLDER = PROJECT_ROOT / "backtesting" / "results"
SUMMARY_FILE = RESULTS_FOLDER / "watchlist_summary.csv"


st.title(":material/analytics: Strategy performance")

st.caption(
    "Compare saved backtest results across multiple stocks."
)


if not SUMMARY_FILE.exists():
    st.warning(
        "No watchlist summary was found yet."
    )

    st.info(
        "Run the multi-stock backtester first so Sentinel AI can "
        "create backtesting/results/watchlist_summary.csv."
    )

    st.code(
        "python main.py",
        language="powershell",
    )

    st.stop()


summary = pd.read_csv(SUMMARY_FILE)


required_columns = {
    "Symbol",
    "Trades",
    "Win Rate",
    "Profit Factor",
    "Strategy Return",
    "Buy & Hold",
    "Max Drawdown",
}

missing_columns = required_columns.difference(summary.columns)

if missing_columns:
    st.error(
        "The summary file is missing required columns: "
        + ", ".join(sorted(missing_columns))
    )

    st.dataframe(
        summary,
        width="stretch",
        hide_index=True,
    )

    st.stop()


numeric_columns = [
    "Trades",
    "Win Rate",
    "Profit Factor",
    "Strategy Return",
    "Buy & Hold",
    "Max Drawdown",
]

for column in numeric_columns:
    summary[column] = pd.to_numeric(
        summary[column],
        errors="coerce",
    )


summary = summary.dropna(
    subset=["Symbol", "Strategy Return"]
)


if summary.empty:
    st.warning(
        "The watchlist summary exists, but it does not contain "
        "usable backtest results."
    )

    st.stop()


summary["Outperformance"] = (
    summary["Strategy Return"]
    - summary["Buy & Hold"]
)


best_strategy_row = summary.loc[
    summary["Strategy Return"].idxmax()
]

best_win_rate_row = summary.loc[
    summary["Win Rate"].idxmax()
]

lowest_drawdown_row = summary.loc[
    summary["Max Drawdown"].idxmin()
]

best_profit_factor_row = summary.loc[
    summary["Profit Factor"].idxmax()
]


metric_1, metric_2, metric_3, metric_4 = st.columns(4, border=True)


metric_1.metric(
    "Best Strategy Return",
    f'{best_strategy_row["Strategy Return"]:.2f}%',
    delta=str(best_strategy_row["Symbol"]),
)


metric_2.metric(
    "Highest Win Rate",
    f'{best_win_rate_row["Win Rate"]:.2f}%',
    delta=str(best_win_rate_row["Symbol"]),
)


metric_3.metric(
    "Lowest Drawdown",
    f'{lowest_drawdown_row["Max Drawdown"]:.2f}%',
    delta=str(lowest_drawdown_row["Symbol"]),
)


metric_4.metric(
    "Best Profit Factor",
    f'{best_profit_factor_row["Profit Factor"]:.2f}',
    delta=str(best_profit_factor_row["Symbol"]),
)


st.subheader("Strategy Return vs Buy and Hold")


comparison = summary[
    [
        "Symbol",
        "Strategy Return",
        "Buy & Hold",
    ]
].copy()


comparison = comparison.set_index("Symbol")


st.bar_chart(
    comparison,
    width="stretch",
)


st.subheader("Win Rate by Stock")


win_rate_chart = summary[
    [
        "Symbol",
        "Win Rate",
    ]
].set_index("Symbol")


st.bar_chart(
    win_rate_chart,
    width="stretch",
)


st.subheader("Maximum Drawdown")


drawdown_chart = summary[
    [
        "Symbol",
        "Max Drawdown",
    ]
].set_index("Symbol")


st.bar_chart(
    drawdown_chart,
    width="stretch",
)


st.subheader("Ranked Results")


ranked_summary = summary.sort_values(
    by="Strategy Return",
    ascending=False,
).reset_index(drop=True)


display_columns = [
    "Symbol",
    "Trades",
    "Win Rate",
    "Profit Factor",
    "Strategy Return",
    "Buy & Hold",
    "Outperformance",
    "Max Drawdown",
]


st.dataframe(
    ranked_summary[display_columns],
    width="stretch",
    hide_index=True,
)


st.subheader("Best and Worst Performers")


left_column, right_column = st.columns(2)


with left_column:
    best_row = ranked_summary.iloc[0]

    st.success(
        f'Best performer: {best_row["Symbol"]}'
    )

    st.write(
        f'Strategy return: {best_row["Strategy Return"]:.2f}%'
    )

    st.write(
        f'Buy and hold: {best_row["Buy & Hold"]:.2f}%'
    )

    st.write(
        f'Outperformance: {best_row["Outperformance"]:.2f}%'
    )

    st.write(
        f'Win rate: {best_row["Win Rate"]:.2f}%'
    )


with right_column:
    worst_row = ranked_summary.iloc[-1]

    st.error(
        f'Weakest performer: {worst_row["Symbol"]}'
    )

    st.write(
        f'Strategy return: {worst_row["Strategy Return"]:.2f}%'
    )

    st.write(
        f'Buy and hold: {worst_row["Buy & Hold"]:.2f}%'
    )

    st.write(
        f'Outperformance: {worst_row["Outperformance"]:.2f}%'
    )

    st.write(
        f'Win rate: {worst_row["Win Rate"]:.2f}%'
    )



csv_data = ranked_summary.to_csv(
    index=False
).encode("utf-8")


st.download_button(
    label="Download Performance Summary",
    data=csv_data,
    file_name="watchlist_summary.csv",
    mime="text/csv",
    width="stretch",
)
