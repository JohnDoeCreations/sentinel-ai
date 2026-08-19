"""Reusable stock-analysis engine for Sentinel AI scanner interfaces."""

import pandas as pd

from data.market_data import get_stock_data
from strategies.indicators import (
    calculate_macd,
    calculate_moving_average,
    calculate_rsi,
)
from strategies.scoring import calculate_score
from utils.symbols import normalize_symbol


def analyze_stock(symbol):
    """Analyze one symbol and return the values displayed by the scanner."""
    clean_symbol = normalize_symbol(symbol)
    data = get_stock_data(clean_symbol, period="3mo", interval="1d")

    if data.empty:
        return None

    close_prices = data["Close"].dropna()
    if isinstance(close_prices, pd.DataFrame):
        close_prices = close_prices.iloc[:, 0]

    if len(close_prices) < 26:
        return None

    current_price = float(close_prices.iloc[-1])
    previous_price = float(close_prices.iloc[-2])
    if previous_price == 0:
        raise ValueError(f"{clean_symbol} has an invalid previous closing price.")

    percent_change = ((current_price - previous_price) / previous_price) * 100
    moving_average = calculate_moving_average(close_prices, period=5)
    rsi = calculate_rsi(close_prices, period=14)
    macd, signal_line, _ = calculate_macd(close_prices)
    current_macd = float(macd.iloc[-1])
    current_signal = float(signal_line.iloc[-1])

    score, rating, strengths, weaknesses = calculate_score(
        current_price=current_price,
        moving_average=moving_average,
        percent_change=percent_change,
        rsi=rsi,
        current_macd=current_macd,
        current_signal=current_signal,
    )

    if rsi >= 70:
        signal = "OVERBOUGHT WATCH"
    elif rsi <= 30:
        signal = "OVERSOLD WATCH"
    elif score >= 4:
        signal = "BULLISH WATCH"
    elif score <= 1:
        signal = "BEARISH WATCH"
    else:
        signal = "NEUTRAL"

    return {
        "Symbol": clean_symbol,
        "Price": round(current_price, 2),
        "Daily Change (%)": round(percent_change, 2),
        "5-Day Average": round(moving_average, 2),
        "RSI": round(rsi, 2),
        "MACD": round(current_macd, 2),
        "Signal Line": round(current_signal, 2),
        "Score": score,
        "Rating": rating,
        "Signal": signal,
        "Strengths": strengths,
        "Weaknesses": weaknesses,
    }
