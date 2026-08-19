from pathlib import Path
import sys

import pandas as pd
import streamlit as st


# Make the main Sentinel-AI folder importable.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from backtesting.backtest import backtest


st.set_page_config(
    page_title="Sentinel AI Backtester",
    page_icon=":material/science:",
    layout="wide",
)


RESULTS_FOLDER = PROJECT_ROOT / "backtesting" / "results"


st.title(":material/science: Strategy backtester")

st.caption(
    "Test the Sentinel AI strategy against historical market data "
    "without risking real money."
)


with st.sidebar:
    st.subheader("Backtest settings")

    symbol = st.text_input(
        "Stock symbol",
        value="AAPL",
        max_chars=10,
    ).strip().upper()

    st.info(
        "The current engine uses its existing risk controls, "
        "EMA trend filter, ATR exits, and scoring rules."
    )


run_backtest = st.button(
    "Run backtest",
    icon=":material/play_arrow:",
    type="primary",
    width="stretch",
)


if run_backtest:
    if not symbol:
        st.warning("Enter a stock symbol first.")

    else:
        try:
            with st.spinner(
                f"Running historical backtest for {symbol}..."
            ):
                result = backtest(
                    symbol,
                    show_chart=False,
                )

            if result is None:
                st.error(
                    "The backtest did not return any results. "
                    "Check the VS Code terminal for details."
                )

            else:
                st.session_state["backtest_result"] = result
                st.session_state["backtest_symbol"] = symbol

                st.success(
                    f"{symbol} backtest completed successfully."
                )

        except Exception as error:
            st.error(f"Backtest failed: {error}")
            st.exception(error)


result = st.session_state.get("backtest_result")
saved_symbol = st.session_state.get("backtest_symbol")


if result and saved_symbol:
    st.subheader(f"{saved_symbol} Performance Summary")

    metric_1, metric_2, metric_3, metric_4 = st.columns(4, border=True)

    metric_1.metric(
        "Trades",
        int(result.get("Trades", 0)),
    )

    metric_2.metric(
        "Win Rate",
        f'{result.get("Win Rate", 0):.2f}%',
    )

    metric_3.metric(
        "Strategy Return",
        f'{result.get("Strategy Return", 0):.2f}%',
    )

    metric_4.metric(
        "Ending Balance",
        f'${result.get("Ending Balance", 0):,.2f}',
    )


    metric_5, metric_6, metric_7, metric_8 = st.columns(4, border=True)

    metric_5.metric(
        "Net Profit",
        f'${result.get("Net Profit", 0):,.2f}',
    )

    metric_6.metric(
        "Profit Factor",
        f'{result.get("Profit Factor", 0):.2f}',
    )

    metric_7.metric(
        "Sharpe Ratio",
        f'{result.get("Sharpe Ratio", 0):.2f}',
    )

    metric_8.metric(
        "Maximum Drawdown",
        f'{result.get("Max Drawdown", 0):.2f}%',
    )


    strategy_return = result.get(
        "Strategy Return",
        0,
    )

    buy_hold_return = result.get(
        "Buy & Hold",
        0,
    )

    st.subheader("Strategy Comparison")

    comparison_dataframe = pd.DataFrame(
        {
            "Approach": [
                "Sentinel AI Strategy",
                "Buy and Hold",
            ],
            "Return (%)": [
                strategy_return,
                buy_hold_return,
            ],
        }
    )

    st.bar_chart(
        comparison_dataframe.set_index("Approach")
    )


    if strategy_return > buy_hold_return:
        difference = strategy_return - buy_hold_return

        st.success(
            f"Sentinel AI beat buy-and-hold by "
            f"{difference:.2f} percentage points."
        )

    else:
        difference = buy_hold_return - strategy_return

        st.warning(
            f"Buy-and-hold performed better by "
            f"{difference:.2f} percentage points."
        )


    chart_path = (
        RESULTS_FOLDER
        / f"{saved_symbol}_equity_curve.png"
    )

    st.subheader("Equity Curve")

    if chart_path.exists():
        st.image(
            str(chart_path),
            caption=(
                f"{saved_symbol} simulated account balance "
                "after each completed trade"
            ),
            width="stretch",
        )

    else:
        st.info(
            "The equity-curve image was not found. "
            "Run the backtest again after confirming chart saving "
            "is enabled in backtest.py."
        )


    trade_log_path = (
        RESULTS_FOLDER
        / f"{saved_symbol}_backtest.csv"
    )

    st.subheader("Individual Trades")

    if trade_log_path.exists():
        trade_dataframe = pd.read_csv(
            trade_log_path
        )

        if trade_dataframe.empty:
            st.info(
                "The strategy did not create any qualifying trades."
            )

        else:
            st.dataframe(
                trade_dataframe,
                width="stretch",
                hide_index=True,
            )

            csv_data = trade_dataframe.to_csv(
                index=False
            ).encode("utf-8")

            st.download_button(
                label="Download Trade Log",
                data=csv_data,
                file_name=(
                    f"{saved_symbol}_backtest.csv"
                ),
                mime="text/csv",
                width="stretch",
            )

    else:
        st.info(
            "No saved trade log was found for this symbol."
        )


else:
    st.info(
        "Enter a stock symbol and click Run Backtest "
        "to generate historical performance results."
    )
