"""Batch monitoring service for persistent Sentinel AI alerts."""

from datetime import datetime, timezone

from utils.alerts import evaluate_alert, load_alert_state, save_alert_state


def check_enabled_alerts(analyze_symbol, positions=None, checked_at=None):
    """Check every enabled alert in one batch and persist once."""
    state = load_alert_state()
    positions = positions or {}
    checked_at = checked_at or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )
    analysis_cache = {}
    checked_count = 0
    newly_triggered = []
    errors = []

    for alert in state["alerts"]:
        if not alert.get("enabled", True):
            continue

        symbol = alert["symbol"]
        try:
            if symbol not in analysis_cache:
                analysis_cache[symbol] = analyze_symbol(symbol)
            analysis = analysis_cache[symbol]
            if analysis is None:
                raise ValueError("Not enough market data.")

            position_return = None
            position = positions.get(symbol)
            if position:
                average_cost = float(position.get("average_cost", 0.0))
                if average_cost <= 0:
                    raise ValueError("The paper position has an invalid average cost.")
                position_return = (
                    float(analysis["Price"]) / average_cost - 1
                ) * 100

            triggered, current_value, message = evaluate_alert(
                alert,
                analysis,
                position_return,
            )
            was_triggered = bool(alert.get("is_triggered", False))
            alert["is_triggered"] = bool(triggered)
            alert["last_checked_at"] = checked_at
            alert["last_value"] = current_value
            alert.pop("last_error", None)
            checked_count += 1

            if triggered and not was_triggered:
                history_item = {
                    "timestamp": checked_at,
                    "symbol": symbol,
                    "type": alert["type"],
                    "message": message,
                }
                state["history"].append(history_item)
                newly_triggered.append(history_item)
        except Exception as error:
            error_message = str(error)
            alert["last_checked_at"] = checked_at
            alert["last_error"] = error_message
            errors.append({"symbol": symbol, "message": error_message})

    state["monitor"] = {
        "last_checked_at": checked_at,
        "checked": checked_count,
        "new_triggers": len(newly_triggered),
        "errors": len(errors),
    }
    save_alert_state(state)
    return {
        "checked_at": checked_at,
        "checked": checked_count,
        "newly_triggered": newly_triggered,
        "errors": errors,
        "symbols_analyzed": len(analysis_cache),
    }
