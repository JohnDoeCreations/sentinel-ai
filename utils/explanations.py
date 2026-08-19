"""Plain-English explanations for Sentinel AI analysis results."""


def explain_analysis(result):
    """Convert a scanner result into a concise, plain-English explanation."""
    symbol = result["Symbol"]
    rating = result["Rating"].lower()
    signal = result["Signal"].lower().replace(" watch", "")
    strengths = result.get("Strengths", [])
    weaknesses = result.get("Weaknesses", [])

    summary = (
        f"{symbol} is currently rated as a {rating} with a {signal} signal."
    )

    if strengths:
        positive_details = "; ".join(item.lower() for item in strengths)
        summary += f" Positive factors: {positive_details}."

    if weaknesses:
        risk_details = "; ".join(item.lower() for item in weaknesses)
        summary += f" Factors to watch: {risk_details}."

    rsi = result["RSI"]
    if rsi >= 70:
        summary += " RSI suggests price may be overextended after recent gains."
    elif rsi <= 30:
        summary += " RSI suggests heavy selling and a potentially oversold condition."
    else:
        summary += f" RSI is {rsi:.2f}, outside the usual overbought and oversold extremes."

    return summary
