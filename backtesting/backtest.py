import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from data.market_data import get_stock_data
from strategies.indicators import (
    calculate_atr,
    calculate_ema,
    calculate_macd,
    calculate_moving_average,
    calculate_rsi,
)
from strategies.scoring import calculate_score
from utils.symbols import normalize_symbol


RESULTS_FOLDER = Path(__file__).resolve().parent / "results"
TRADE_LOG_COLUMNS = [
    "Symbol",
    "Entry Date",
    "Exit Date",
    "Entry Price",
    "Exit Price",
    "Shares",
    "Profit ($)",
    "Return (%)",
    "Result",
    "Exit Reason",
    "Score",
    "Rating",
    "RSI",
    "MACD",
    "Signal Line",
    "EMA 20",
    "EMA 50",
    "ATR",
]


def backtest(symbol, show_chart=True):
    symbol = normalize_symbol(symbol)
    print(f"\nRunning backtest for {symbol}...")

    data = get_stock_data(
        symbol,
        period="2y",
        interval="1d",
    )

    if data.empty:
        print(f"No historical data found for {symbol}.")
        return None

    data = data.dropna(
        subset=["Open", "High", "Low", "Close"]
    )

    close_prices = data["Close"]

    if isinstance(close_prices, pd.DataFrame):
        close_prices = close_prices.iloc[:, 0]

    warmup_period = 55
    maximum_holding_days = 10

    minimum_score = 3
    risk_per_trade = 0.01

    atr_stop_multiplier = 2.0
    atr_target_multiplier = 3.0

    starting_balance = 10000.0
    balance = starting_balance

    if len(data) <= warmup_period + maximum_holding_days:
        print(f"Not enough historical data for {symbol}.")
        return None

    buy_hold_entry = float(
        close_prices.iloc[warmup_period]
    )

    buy_hold_exit = float(
        close_prices.iloc[-1]
    )

    buy_hold_return = (
        (buy_hold_exit - buy_hold_entry)
        / buy_hold_entry
    ) * 100

    trades = 0
    wins = 0
    losses = 0

    trade_returns = []
    trade_profits = []
    equity_curve = [balance]
    trade_log = []

    peak_balance = balance
    max_drawdown = 0.0

    i = warmup_period

    while i < len(data) - 1:
        history_data = data.iloc[: i + 1]
        history_close = close_prices.iloc[: i + 1]

        current_price = float(
            history_close.iloc[-1]
        )

        previous_price = float(
            history_close.iloc[-2]
        )

        percent_change = (
            (current_price - previous_price)
            / previous_price
        ) * 100

        moving_average = calculate_moving_average(
            history_close,
            period=5,
        )

        rsi = calculate_rsi(
            history_close,
            period=14,
        )

        macd, signal_line, histogram = calculate_macd(
            history_close
        )

        current_macd = float(
            macd.iloc[-1]
        )

        current_signal = float(
            signal_line.iloc[-1]
        )

        ema_20 = calculate_ema(
            history_close,
            period=20,
        )

        ema_50 = calculate_ema(
            history_close,
            period=50,
        )

        atr = calculate_atr(
            history_data,
            period=14,
        )

        score, rating, strengths, weaknesses = calculate_score(
            current_price=current_price,
            moving_average=moving_average,
            percent_change=percent_change,
            rsi=rsi,
            current_macd=current_macd,
            current_signal=current_signal,
        )

        bullish_trend = ema_20 > ema_50

        if (
            score < minimum_score
            or not bullish_trend
            or atr <= 0
        ):
            i += 1
            continue

        entry_index = i
        entry_price = current_price

        stop_loss_price = (
            entry_price
            - atr_stop_multiplier * atr
        )

        take_profit_price = (
            entry_price
            + atr_target_multiplier * atr
        )

        risk_per_share = (
            entry_price - stop_loss_price
        )

        if risk_per_share <= 0:
            i += 1
            continue

        risk_amount = balance * risk_per_trade

        risk_based_shares = math.floor(
            risk_amount / risk_per_share
        )

        affordable_shares = math.floor(
            balance / entry_price
        )

        shares = min(
            risk_based_shares,
            affordable_shares,
        )

        if shares < 1:
            i += 1
            continue

        planned_exit_index = min(
            entry_index + maximum_holding_days,
            len(data) - 1,
        )

        exit_index = planned_exit_index

        exit_price = float(
            close_prices.iloc[exit_index]
        )

        exit_reason = "Time Exit"

        for j in range(
            entry_index + 1,
            planned_exit_index + 1,
        ):
            daily_low = float(
                data["Low"].iloc[j]
            )

            daily_high = float(
                data["High"].iloc[j]
            )

            # Conservative assumption:
            # if both levels are touched on one candle,
            # the stop-loss is counted first.
            if daily_low <= stop_loss_price:
                exit_index = j
                exit_price = stop_loss_price
                exit_reason = "Stop Loss"
                break

            if daily_high >= take_profit_price:
                exit_index = j
                exit_price = take_profit_price
                exit_reason = "Take Profit"
                break

        trade_return = (
            (exit_price - entry_price)
            / entry_price
        ) * 100

        trade_profit = (
            exit_price - entry_price
        ) * shares

        balance += trade_profit

        trades += 1
        trade_returns.append(trade_return)
        trade_profits.append(trade_profit)

        if trade_profit > 0:
            wins += 1
            result = "Win"
        else:
            losses += 1
            result = "Loss"

        peak_balance = max(
            peak_balance,
            balance,
        )

        current_drawdown = (
            (peak_balance - balance)
            / peak_balance
        ) * 100

        max_drawdown = max(
            max_drawdown,
            current_drawdown,
        )

        equity_curve.append(balance)

        entry_date = data.index[
            entry_index
        ].strftime("%Y-%m-%d")

        exit_date = data.index[
            exit_index
        ].strftime("%Y-%m-%d")

        trade_log.append({
            "Symbol": symbol,
            "Entry Date": entry_date,
            "Exit Date": exit_date,
            "Entry Price": round(entry_price, 2),
            "Exit Price": round(exit_price, 2),
            "Shares": shares,
            "Profit ($)": round(trade_profit, 2),
            "Return (%)": round(trade_return, 2),
            "Result": result,
            "Exit Reason": exit_reason,
            "Score": score,
            "Rating": rating,
            "RSI": round(rsi, 2),
            "MACD": round(current_macd, 4),
            "Signal Line": round(current_signal, 4),
            "EMA 20": round(ema_20, 2),
            "EMA 50": round(ema_50, 2),
            "ATR": round(atr, 2),
        })

        print(
            f"{entry_date} -> {exit_date} | "
            f"{shares} shares | "
            f"${entry_price:.2f} -> ${exit_price:.2f} | "
            f"{trade_return:+.2f}% | "
            f"${trade_profit:+.2f} | "
            f"{exit_reason}"
        )

        # Continue after the current trade exits,
        # preventing overlapping positions.
        i = exit_index + 1

    RESULTS_FOLDER.mkdir(parents=True, exist_ok=True)
    trade_log_filename = RESULTS_FOLDER / f"{symbol}_backtest.csv"

    pd.DataFrame(trade_log, columns=TRADE_LOG_COLUMNS).to_csv(
        trade_log_filename,
        index=False,
    )

    print("\n" + "=" * 48)
    print(f"BACKTEST RESULTS: {symbol}")
    print("=" * 48)
    print(f"Trades:              {trades}")

    if trades == 0:
        print("No qualifying trades found.")
        print(
            f"Trade log saved to {trade_log_filename}"
        )
        return {
            "Symbol": symbol,
            "Trades": 0,
            "Win Rate": 0.0,
            "Strategy Return": 0.0,
            "Buy & Hold": buy_hold_return,
            "Ending Balance": balance,
            "Max Drawdown": 0.0,
            "Profit Factor": 0.0,
        }

    winning_returns = [
        value
        for value in trade_returns
        if value > 0
    ]

    losing_returns = [
        value
        for value in trade_returns
        if value <= 0
    ]

    winning_profits = [
        value
        for value in trade_profits
        if value > 0
    ]

    losing_profits = [
        value
        for value in trade_profits
        if value <= 0
    ]

    win_rate = (
        wins / trades
    ) * 100

    average_return = (
        sum(trade_returns)
        / len(trade_returns)
    )

    average_win = (
        sum(winning_returns)
        / len(winning_returns)
        if winning_returns
        else 0.0
    )

    average_loss = (
        sum(losing_returns)
        / len(losing_returns)
        if losing_returns
        else 0.0
    )

    largest_win = (
        max(winning_returns)
        if winning_returns
        else 0.0
    )

    largest_loss = (
        min(losing_returns)
        if losing_returns
        else 0.0
    )

    gross_profit = sum(
        winning_profits
    )

    gross_loss = abs(
        sum(losing_profits)
    )

    if gross_loss > 0:
        profit_factor = (
            gross_profit / gross_loss
        )
    elif gross_profit > 0:
        profit_factor = float("inf")
    else:
        profit_factor = 0.0

    strategy_return = (
        (balance - starting_balance)
        / starting_balance
    ) * 100

    net_profit = (
        balance - starting_balance
    )

    win_probability = wins / trades
    loss_probability = losses / trades

    expectancy = (
        win_probability * average_win
        + loss_probability * average_loss
    )

    returns_series = pd.Series(
        trade_returns,
        dtype="float64",
    )

    return_standard_deviation = (
        returns_series.std(ddof=1)
    )

    if (
        len(returns_series) > 1
        and return_standard_deviation > 0
    ):
        sharpe_ratio = (
            returns_series.mean()
            / return_standard_deviation
        ) * math.sqrt(len(returns_series))
    else:
        sharpe_ratio = 0.0

    print(f"Wins:                {wins}")
    print(f"Losses:              {losses}")
    print(f"Win Rate:            {win_rate:.1f}%")
    print(f"Average Return:      {average_return:.2f}%")
    print(f"Average Win:         {average_win:.2f}%")
    print(f"Average Loss:        {average_loss:.2f}%")
    print(f"Largest Win:         {largest_win:.2f}%")
    print(f"Largest Loss:        {largest_loss:.2f}%")
    print(f"Profit Factor:       {profit_factor:.2f}")
    print(f"Expectancy:          {expectancy:.2f}%")
    print(f"Sharpe Ratio:        {sharpe_ratio:.2f}")
    print(f"Starting Balance:    ${starting_balance:,.2f}")
    print(f"Ending Balance:      ${balance:,.2f}")
    print(f"Net Profit:          ${net_profit:,.2f}")
    print(f"Max Drawdown:        {max_drawdown:.2f}%")
    print(f"Strategy Return:     {strategy_return:.2f}%")
    print(f"Buy & Hold Return:   {buy_hold_return:.2f}%")

    if strategy_return > buy_hold_return:
        print("Result:               Strategy beat Buy & Hold")
    else:
        print("Result:               Buy & Hold performed better")

    print(
        f"\nTrade log saved to {trade_log_filename}"
    )

    chart_filename = RESULTS_FOLDER / f"{symbol}_equity_curve.png"

    plt.figure(figsize=(10, 5))
    plt.plot(equity_curve)
    plt.title(
        f"Sentinel AI Equity Curve - {symbol}"
    )
    plt.xlabel("Completed Trades")
    plt.ylabel("Account Balance ($)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(
        chart_filename,
        dpi=150,
    )

    if show_chart:
        plt.show()

    plt.close()

    print(
        f"Equity chart saved to {chart_filename}"
    )

    return {
        "Symbol": symbol,
        "Trades": trades,
        "Wins": wins,
        "Losses": losses,
        "Win Rate": round(win_rate, 2),
        "Average Return": round(average_return, 2),
        "Profit Factor": round(profit_factor, 2),
        "Expectancy": round(expectancy, 2),
        "Sharpe Ratio": round(sharpe_ratio, 2),
        "Starting Balance": round(starting_balance, 2),
        "Ending Balance": round(balance, 2),
        "Net Profit": round(net_profit, 2),
        "Max Drawdown": round(max_drawdown, 2),
        "Strategy Return": round(strategy_return, 2),
        "Buy & Hold": round(buy_hold_return, 2),
    }


def backtest_watchlist(symbols):
    summaries = []

    print("\n" + "=" * 48)
    print("SENTINEL AI MULTI-STOCK BACKTEST")
    print("=" * 48)

    for symbol in symbols:
        try:
            result = backtest(
                symbol,
                show_chart=False,
            )

            if result is not None:
                summaries.append(result)

        except Exception as error:
            print(
                f"\n{symbol}: Backtest failed - {error}"
            )

    if not summaries:
        print("No backtest results were generated.")
        return pd.DataFrame()

    summary_dataframe = pd.DataFrame(
        summaries
    )

    summary_dataframe = summary_dataframe.sort_values(
        by="Strategy Return",
        ascending=False,
    )

    RESULTS_FOLDER.mkdir(parents=True, exist_ok=True)
    summary_filename = RESULTS_FOLDER / "watchlist_summary.csv"

    summary_dataframe.to_csv(
        summary_filename,
        index=False,
    )

    print("\n" + "=" * 48)
    print("WATCHLIST SUMMARY")
    print("=" * 48)

    print(
        summary_dataframe[
            [
                "Symbol",
                "Trades",
                "Win Rate",
                "Profit Factor",
                "Strategy Return",
                "Buy & Hold",
                "Max Drawdown",
            ]
        ].to_string(index=False)
    )

    print(
        f"\nSummary saved to {summary_filename}"
    )
    return summary_dataframe
