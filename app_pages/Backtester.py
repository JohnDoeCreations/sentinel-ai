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
    page_title="Sentinel AI strategy validation",
    page_icon=":material/science:",
    layout="wide",
)


RESULTS_FOLDER = PROJECT_ROOT / "backtesting" / "results"


with st.container(horizontal=True, vertical_alignment="center"):
    with st.container():
        st.title(":material/science: Strategy validation")
        st.caption(
            "Test Sentinel's historical behavior before turning an idea into "
            "a risk-controlled trade plan."
        )
    st.badge("Historical simulation", icon=":material/history:", color="violet")

with st.container(horizontal=True):
    st.page_link(
        "app_pages/Trade_Planner.py",
        label="Open trade planning",
        icon=":material/calculate:",
    )

st.caption(
    "The engine uses Sentinel's EMA trend filter, ATR exits, scoring rules, "
    "and existing risk controls."
)

with st.form("backtest_settings", border=False):
    settings_row = st.container(horizontal=True, vertical_alignment="bottom")
    symbol = settings_row.text_input(
        "Stock symbol",
        value=st.session_state.get(
            "strategy_symbol",
            st.session_state.get("research_symbol", "AAPL"),
        ),
        max_chars=10,
    ).strip().upper()
    run_backtest = settings_row.form_submit_button(
        "Run historical test",
        icon=":material/play_arrow:",
        type="primary",
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
                st.session_state["strategy_symbol"] = symbol
                st.session_state["planner_symbol"] = symbol

                st.success(
                    f"{symbol} backtest completed successfully."
                )

        except Exception as error:
            st.error(f"Backtest failed: {error}")
            st.exception(error)


result = st.session_state.get("backtest_result")
saved_symbol = st.session_state.get("backtest_symbol")


if result and saved_symbol:
    st.subheader(f"{saved_symbol} performance summary")

    with st.container(horizontal=True):
        st.metric("Trades", int(result.get("Trades", 0)), border=True)
        st.metric(
            "Win rate", f'{result.get("Win Rate", 0):.2f}%', border=True
        )
        st.metric(
            "Strategy return",
            f'{result.get("Strategy Return", 0):.2f}%',
            border=True,
        )
        st.metric(
            "Ending balance",
            f'${result.get("Ending Balance", 0):,.2f}',
            border=True,
        )

    with st.container(horizontal=True):
        st.metric(
            "Net profit", f'${result.get("Net Profit", 0):,.2f}', border=True
        )
        st.metric(
            "Profit factor",
            f'{result.get("Profit Factor", 0):.2f}',
            border=True,
        )
        st.metric(
            "Sharpe ratio", f'{result.get("Sharpe Ratio", 0):.2f}', border=True
        )
        st.metric(
            "Maximum drawdown",
            f'{result.get("Max Drawdown", 0):.2f}%',
            border=True,
        )


    strategy_return = result.get(
        "Strategy Return",
        0,
    )

    buy_hold_return = result.get(
        "Buy & Hold",
        0,
    )

    st.subheader("Strategy comparison")

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

    st.subheader("Equity curve")

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

    st.subheader("Individual trades")

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
                hide_index=True,
            )

            csv_data = trade_dataframe.to_csv(
                index=False
            ).encode("utf-8")

            st.download_button(
                label="Download trade log",
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
        "Enter a stock symbol and run the historical test "
        "to generate historical performance results."
    )
