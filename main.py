import yfinance as yf
from strategies.scoring import calculate_score
from strategies.indicators import calculate_moving_average
from strategies.indicators import (
    calculate_rsi,
    calculate_macd,
)


print("=" * 42)
print("         SENTINEL AI v3.0")
print("=" * 42)

stocks = ["AAPL", "TSLA", "NVDA", "MSFT"]


for symbol in stocks:
    try:
        data = yf.download(
            symbol,
            period="3mo",
            progress=False,
            auto_adjust=True,
            multi_level_index=False,
        )

        if data.empty or len(data) < 26:
            print(f"\n{symbol}: Not enough data")
            continue

        close_prices = data["Close"]

        if hasattr(close_prices, "columns"):
            close_prices = close_prices.iloc[:, 0]

        current_price = float(close_prices.iloc[-1])
        previous_price = float(close_prices.iloc[-2])

        percent_change = (
            (current_price - previous_price)
            / previous_price
        ) * 100

        moving_average_5 = calculate_moving_average(
            close_prices,
            period=5,
        )

        rsi = calculate_rsi(
            close_prices,
            period=14,
        )

        macd, signal_line, histogram = calculate_macd(close_prices)

        current_macd = float(macd.iloc[-1])
        current_signal = float(signal_line.iloc[-1])

        score, rating, strengths, weaknesses = calculate_score(
            current_price=current_price,
            moving_average=moving_average_5,
            percent_change=percent_change,
            rsi=rsi,
            current_macd=current_macd,
            current_signal=current_signal,
        )

        if (
            current_price > moving_average_5
            and percent_change > 0
            and rsi < 70
        ):
            signal = "BULLISH WATCH"

        elif (
            current_price < moving_average_5
            and percent_change < 0
            and rsi > 30
        ):
            signal = "BEARISH WATCH"

        elif rsi >= 70:
            signal = "OVERBOUGHT WATCH"

        elif rsi <= 30:
            signal = "OVERSOLD WATCH"

        else:
            signal = "NEUTRAL"

        print(f"\n{symbol}")
        print(f"Current price:    ${current_price:.2f}")
        print(f"Daily change:     {percent_change:.2f}%")
        print(f"5-day average:    ${moving_average_5:.2f}")
        print(f"RSI (14):         {rsi:.2f}")
        print(f"MACD:             {current_macd:.2f}")
        print(f"Signal Line:      {current_signal:.2f}")
        print(f"Signal:           {signal}")
        print(f"Score:            {score}/5")
        print(f"Rating:           {rating}")

        print("\nStrengths:")
        if strengths:
            for item in strengths:
                print(f"  + {item}")
        else:
            print("  None")

        print("\nWeaknesses:")
        if weaknesses:
            for item in weaknesses:
                print(f"  - {item}")
        else:
            print("  None")

    except Exception as error:
        print(f"\n{symbol}: Error — {error}")

print("\nScan complete.")

from backtesting.backtest import backtest_watchlist


backtest_symbols = [
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA",
    "META",
    "AMZN",
    "GOOGL",
]

backtest_watchlist(backtest_symbols)
stocks = ["AAPL", "MSFT", "NVDA", "TSLA", "META", "AMZN"]