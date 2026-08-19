"""Persistent alert rules and trigger history for Sentinel AI."""

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from utils.cloud_storage import load_cloud_json, save_cloud_json
from utils.symbols import normalize_legacy_symbol, normalize_symbol


ALERTS_FILE = Path(__file__).resolve().parents[1] / "data" / "alerts.json"


def new_alert_state():
    return {"alerts": [], "history": []}


def load_alert_state():
    """Load saved alerts and history, falling back safely when invalid."""
    state = load_cloud_json("alerts", new_alert_state())
    if state is None:
        if not ALERTS_FILE.exists():
            return new_alert_state()
        try:
            state = json.loads(ALERTS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return new_alert_state()

    if not isinstance(state, dict):
        return new_alert_state()

    state.setdefault("alerts", [])
    state.setdefault("history", [])
    if not isinstance(state["alerts"], list):
        state["alerts"] = []
    if not isinstance(state["history"], list):
        state["history"] = []
    for alert in state["alerts"]:
        if isinstance(alert, dict) and "symbol" in alert:
            try:
                alert["symbol"] = normalize_legacy_symbol(alert["symbol"])
            except ValueError:
                alert["enabled"] = False
    return state


def save_alert_state(state):
    """Save alert state atomically."""
    ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = ALERTS_FILE.with_suffix(".tmp")
    temporary_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temporary_file.replace(ALERTS_FILE)
    save_cloud_json("alerts", state)
    return state


def add_alert(symbol, alert_type, target):
    """Create and persist one enabled alert rule."""
    state = load_alert_state()
    alert = {
        "id": uuid4().hex,
        "symbol": normalize_symbol(symbol),
        "type": alert_type,
        "target": target,
        "enabled": True,
        "is_triggered": False,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "last_checked_at": None,
        "last_value": None,
    }
    state["alerts"].append(alert)
    save_alert_state(state)
    return alert


def ensure_paper_trade_protection(
    symbol,
    stop_loss_percent,
    take_profit_percent,
):
    """Create or refresh linked stop-loss and take-profit alerts."""
    clean_symbol = normalize_symbol(symbol)
    targets = {
        "position_loss_at_most": float(stop_loss_percent),
        "position_gain_at_least": float(take_profit_percent),
    }
    if any(target <= 0 for target in targets.values()):
        raise ValueError("Protection percentages must be greater than zero.")

    state = load_alert_state()
    protected = []
    for alert_type, target in targets.items():
        existing = next(
            (
                alert
                for alert in state["alerts"]
                if alert.get("symbol") == clean_symbol
                and alert.get("type") == alert_type
                and alert.get("source") == "paper_trade"
            ),
            None,
        )
        if existing:
            existing.update(
                {
                    "target": target,
                    "enabled": True,
                    "is_triggered": False,
                    "last_checked_at": None,
                    "last_value": None,
                }
            )
            existing.pop("last_error", None)
            protected.append(existing)
            continue

        alert = {
            "id": uuid4().hex,
            "symbol": clean_symbol,
            "type": alert_type,
            "target": target,
            "enabled": True,
            "is_triggered": False,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "last_checked_at": None,
            "last_value": None,
            "source": "paper_trade",
        }
        state["alerts"].append(alert)
        protected.append(alert)

    save_alert_state(state)
    return protected


def paper_trade_protection_status(symbol, alerts=None):
    """Summarize enabled linked protection for one paper position."""
    clean_symbol = normalize_symbol(symbol)
    alerts = alerts if alerts is not None else load_alert_state()["alerts"]
    linked = [
        alert
        for alert in alerts
        if alert.get("symbol") == clean_symbol
        and alert.get("source") == "paper_trade"
        and alert.get("enabled", True)
    ]
    types = {alert.get("type") for alert in linked}
    stop = "position_loss_at_most" in types
    target = "position_gain_at_least" in types
    return {
        "stop_loss": stop,
        "take_profit": target,
        "protected": stop and target,
        "label": "Protected" if stop and target else "Needs protection",
    }


def disable_paper_trade_protection(symbol):
    """Disable linked protection after the associated position is closed."""
    clean_symbol = normalize_symbol(symbol)
    state = load_alert_state()
    for alert in state["alerts"]:
        if (
            alert.get("symbol") == clean_symbol
            and alert.get("source") == "paper_trade"
        ):
            alert["enabled"] = False
            alert["is_triggered"] = False
    return save_alert_state(state)


def set_alert_enabled(alert_id, enabled):
    """Enable or disable an alert."""
    state = load_alert_state()
    for alert in state["alerts"]:
        if alert["id"] == alert_id:
            alert["enabled"] = bool(enabled)
            if not enabled:
                alert["is_triggered"] = False
            break
    return save_alert_state(state)


def delete_alert(alert_id):
    """Delete one alert while preserving its trigger history."""
    state = load_alert_state()
    state["alerts"] = [
        alert for alert in state["alerts"] if alert["id"] != alert_id
    ]
    return save_alert_state(state)


def evaluate_alert(alert, analysis, position_return=None):
    """Evaluate one rule and return condition, current value, and message."""
    alert_type = alert["type"]
    target = alert["target"]
    symbol = alert["symbol"]

    if alert_type == "price_above":
        current = float(analysis["Price"])
        triggered = current >= float(target)
        message = f"{symbol} price ${current:.2f} reached ${float(target):.2f}."
    elif alert_type == "price_below":
        current = float(analysis["Price"])
        triggered = current <= float(target)
        message = f"{symbol} price ${current:.2f} fell to ${float(target):.2f} or lower."
    elif alert_type == "score_at_least":
        current = int(analysis["Score"])
        triggered = current >= int(target)
        message = f"{symbol} scanner score reached {current}/4."
    elif alert_type == "signal_equals":
        current = analysis["Signal"]
        triggered = current == target
        message = f"{symbol} signal changed to {current}."
    elif alert_type == "rsi_above":
        current = float(analysis["RSI"])
        triggered = current >= float(target)
        message = f"{symbol} RSI reached {current:.2f}."
    elif alert_type == "rsi_below":
        current = float(analysis["RSI"])
        triggered = current <= float(target)
        message = f"{symbol} RSI fell to {current:.2f}."
    elif alert_type == "position_gain_at_least":
        if position_return is None:
            raise ValueError(f"No open paper position exists for {symbol}.")
        current = float(position_return)
        triggered = current >= float(target)
        message = f"{symbol} paper position return reached {current:+.2f}%."
    elif alert_type == "position_loss_at_most":
        if position_return is None:
            raise ValueError(f"No open paper position exists for {symbol}.")
        current = float(position_return)
        triggered = current <= -abs(float(target))
        message = f"{symbol} paper position return fell to {current:+.2f}%."
    else:
        raise ValueError(f"Unsupported alert type: {alert_type}")

    return triggered, current, message


def record_alert_check(alert_id, triggered, current_value, message):
    """Save check status and record only new false-to-true triggers."""
    state = load_alert_state()
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for alert in state["alerts"]:
        if alert["id"] != alert_id:
            continue

        was_triggered = bool(alert.get("is_triggered", False))
        alert["is_triggered"] = bool(triggered)
        alert["last_checked_at"] = checked_at
        alert["last_value"] = current_value

        if triggered and not was_triggered:
            state["history"].append(
                {
                    "timestamp": checked_at,
                    "symbol": alert["symbol"],
                    "type": alert["type"],
                    "message": message,
                }
            )
        break

    return save_alert_state(state)


def check_enabled_alerts(analyze_symbol, positions=None, checked_at=None):
    """Check every enabled alert in one batch and persist once.

    ``analyze_symbol`` is injected so this persistence module stays independent
    from the market-data provider and remains straightforward to test.
    """
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
