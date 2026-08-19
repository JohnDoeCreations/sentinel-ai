import pandas as pd


def calculate_moving_average(close_prices, period=5):
    moving_average = close_prices.rolling(
        window=period
    ).mean()

    return float(moving_average.iloc[-1])


def calculate_ema(close_prices, period=20):
    ema = close_prices.ewm(
        span=period,
        adjust=False,
    ).mean()

    return float(ema.iloc[-1])


def calculate_rsi(close_prices, period=14):
    price_change = close_prices.diff()

    gains = price_change.clip(lower=0)
    losses = -price_change.clip(upper=0)

    average_gain = gains.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    average_loss = losses.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    relative_strength = average_gain / average_loss.replace(0, float("nan"))

    rsi = 100 - (
        100 / (1 + relative_strength)
    )

    current_rsi = rsi.iloc[-1]

    if pd.isna(current_rsi):
        return 50.0

    return float(current_rsi)


def calculate_macd(
    close_prices,
    fast_period=12,
    slow_period=26,
    signal_period=9,
):
    fast_ema = close_prices.ewm(
        span=fast_period,
        adjust=False,
    ).mean()

    slow_ema = close_prices.ewm(
        span=slow_period,
        adjust=False,
    ).mean()

    macd = fast_ema - slow_ema

    signal_line = macd.ewm(
        span=signal_period,
        adjust=False,
    ).mean()

    histogram = macd - signal_line

    return macd, signal_line, histogram


def calculate_atr(data, period=14):
    high_low = data["High"] - data["Low"]

    high_previous_close = (
        data["High"] - data["Close"].shift(1)
    ).abs()

    low_previous_close = (
        data["Low"] - data["Close"].shift(1)
    ).abs()

    true_range = pd.concat(
        [
            high_low,
            high_previous_close,
            low_previous_close,
        ],
        axis=1,
    ).max(axis=1)

    atr = true_range.rolling(
        window=period
    ).mean()

    current_atr = atr.iloc[-1]

    if pd.isna(current_atr):
        return 0.0

    return float(current_atr)