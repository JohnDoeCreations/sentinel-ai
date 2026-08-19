def calculate_score(
    current_price,
    moving_average,
    percent_change,
    rsi,
    current_macd,
    current_signal,
):
    score = 0
    strengths = []
    weaknesses = []

    if current_price > moving_average:
        score += 1
        strengths.append("Price is above the moving average")
    else:
        weaknesses.append("Price is below the moving average")

    if percent_change > 0:
        score += 1
        strengths.append("Daily momentum is positive")
    else:
        weaknesses.append("Daily momentum is negative")

    if 40 <= rsi <= 65:
        score += 1
        strengths.append("RSI is in a healthy range")
    else:
        weaknesses.append("RSI is outside the ideal range")

    if rsi < 30:
        score += 1
        strengths.append("Stock may be oversold")

    # MACD check
    if current_macd is not None and current_signal is not None:
        if current_macd > current_signal:
            score += 1
            strengths.append("MACD is bullish")
        else:
            weaknesses.append("MACD is bearish")

    if score == 4:
        rating = "STRONG SETUP"
    elif score == 3:
        rating = "GOOD SETUP"
    elif score == 2:
        rating = "MIXED SETUP"
    elif score == 1:
        rating = "WEAK SETUP"
    else:
        rating = "NO SETUP"

    return score, rating, strengths, weaknesses
 