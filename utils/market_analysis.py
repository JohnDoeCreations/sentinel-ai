"""Deeper, explainable market analysis built from price and volume data."""

import pandas as pd

from data.market_data import get_stock_data
from strategies.indicators import calculate_atr, calculate_macd, calculate_rsi
from utils.symbols import normalize_symbol


def _series(data, column):
    """Return one numeric column as a clean Series."""
    values = data[column]
    if isinstance(values, pd.DataFrame):
        values = values.iloc[:, 0]
    return pd.to_numeric(values, errors="coerce")


def build_market_analysis(symbol):
    """Return an explainable technical-analysis report for one symbol."""
    clean_symbol = normalize_symbol(symbol)
    data = get_stock_data(clean_symbol, period="1y", interval="1d")

    required_columns = {"High", "Low", "Close"}
    if data.empty or not required_columns.issubset(data.columns):
        return None

    close = _series(data, "Close").dropna()
    if len(close) < 50:
        return None

    high = _series(data, "High").reindex(close.index)
    low = _series(data, "Low").reindex(close.index)
    analysis_data = pd.DataFrame({"High": high, "Low": low, "Close": close}).dropna()
    if len(analysis_data) < 50:
        return None

    close = analysis_data["Close"]
    current_price = float(close.iloc[-1])
    previous_price = float(close.iloc[-2])
    if previous_price <= 0 or current_price <= 0:
        raise ValueError(f"{clean_symbol} has invalid closing-price data.")

    sma_20 = float(close.rolling(20).mean().iloc[-1])
    sma_50 = float(close.rolling(50).mean().iloc[-1])
    rsi = calculate_rsi(close, period=14)
    macd, signal_line, histogram = calculate_macd(close)
    atr = calculate_atr(analysis_data, period=14)
    atr_percent = atr / current_price * 100
    daily_change = (current_price / previous_price - 1) * 100
    five_day_return = (
        (current_price / float(close.iloc[-6]) - 1) * 100
        if len(close) >= 6
        else 0.0
    )

    recent = analysis_data.tail(20)
    support = float(recent["Low"].min())
    resistance = float(recent["High"].max())
    distance_to_support = (current_price / support - 1) * 100 if support > 0 else 0.0
    distance_to_resistance = (resistance / current_price - 1) * 100

    bullish_factors = []
    risk_factors = []

    if current_price > sma_20:
        bullish_factors.append("Price is above its 20-day average")
    else:
        risk_factors.append("Price is below its 20-day average")

    if sma_20 > sma_50:
        bullish_factors.append("The 20-day trend is above the 50-day trend")
    else:
        risk_factors.append("The 20-day trend is below the 50-day trend")

    if float(macd.iloc[-1]) > float(signal_line.iloc[-1]):
        bullish_factors.append("MACD momentum is positive")
    else:
        risk_factors.append("MACD momentum is negative")

    if 40 <= rsi <= 65:
        bullish_factors.append("RSI is in a constructive range")
    elif rsi >= 70:
        risk_factors.append("RSI is overbought and may be extended")
    elif rsi <= 30:
        risk_factors.append("RSI is oversold, but downside momentum remains a risk")
    else:
        risk_factors.append("RSI is outside the preferred momentum range")

    if atr_percent >= 4:
        volatility = "High"
        risk_factors.append("Daily price ranges are unusually wide")
    elif atr_percent >= 2:
        volatility = "Moderate"
    else:
        volatility = "Low"

    trend_points = sum(
        [
            current_price > sma_20,
            sma_20 > sma_50,
            float(macd.iloc[-1]) > float(signal_line.iloc[-1]),
            40 <= rsi <= 65,
        ]
    )
    if trend_points >= 3:
        bias = "Bullish"
    elif trend_points <= 1:
        bias = "Bearish"
    else:
        bias = "Neutral"

    if current_price > sma_20 and sma_20 > sma_50:
        trend = "Uptrend"
    elif current_price < sma_20 and sma_20 < sma_50:
        trend = "Downtrend"
    else:
        trend = "Range / transition"

    volume_context = "Volume data is unavailable."
    volume_ratio = None
    if "Volume" in data.columns:
        volume = _series(data, "Volume").reindex(close.index).dropna()
        if len(volume) >= 20 and float(volume.tail(20).mean()) > 0:
            volume_ratio = float(volume.iloc[-1] / volume.tail(20).mean())
            if volume_ratio >= 1.25:
                volume_context = "Trading volume is above its 20-day average."
            elif volume_ratio <= 0.75:
                volume_context = "Trading volume is below its 20-day average."
            else:
                volume_context = "Trading volume is near its 20-day average."

    summary = (
        f"{clean_symbol} has a {bias.lower()} technical bias and is in a "
        f"{trend.lower()}. Price is {abs(current_price / sma_20 - 1) * 100:.1f}% "
        f"{'above' if current_price >= sma_20 else 'below'} the 20-day average, "
        f"while RSI is {rsi:.1f}. Volatility is {volatility.lower()} at "
        f"{atr_percent:.1f}% of price."
    )

    return {
        "Symbol": clean_symbol,
        "Price": round(current_price, 2),
        "Daily Change (%)": round(daily_change, 2),
        "5-Day Return (%)": round(five_day_return, 2),
        "20-Day Average": round(sma_20, 2),
        "50-Day Average": round(sma_50, 2),
        "RSI": round(rsi, 2),
        "MACD Histogram": round(float(histogram.iloc[-1]), 4),
        "ATR": round(atr, 2),
        "ATR (%)": round(atr_percent, 2),
        "Support": round(support, 2),
        "Resistance": round(resistance, 2),
        "Distance to Support (%)": round(distance_to_support, 2),
        "Distance to Resistance (%)": round(distance_to_resistance, 2),
        "Bias": bias,
        "Trend": trend,
        "Volatility": volatility,
        "Volume Ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
        "Volume Context": volume_context,
        "Bullish Factors": bullish_factors,
        "Risk Factors": risk_factors,
        "Summary": summary,
        "Bull Case": (
            f"A sustained move above ${resistance:,.2f} would confirm a breakout "
            "from the recent 20-session range."
        ),
        "Base Case": (
            f"Price may consolidate between support near ${support:,.2f} and "
            f"resistance near ${resistance:,.2f}."
        ),
        "Bear Case": (
            f"A close below ${support:,.2f} would weaken the current structure "
            "and increase downside risk."
        ),
        "Chart Data": analysis_data.tail(126).copy(),
    }
