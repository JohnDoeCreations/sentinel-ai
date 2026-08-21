"""Persistent controls and sizing for automatic Kalshi paper execution."""

import json
from pathlib import Path


AUTO_TRADE_SETTINGS_FILE = (
    Path(__file__).resolve().parents[1] / "data" / "kalshi_auto_trade.json"
)
DEFAULT_AUTO_TRADE_SETTINGS = {
    "enabled": False,
    "minimum_edge": 0.05,
    "contracts_per_trade": 10,
    "maximum_trade_cost": 25.0,
    "maximum_total_exposure": 100.0,
}


def load_auto_trade_settings():
    """Load validated paper-only automation settings."""
    settings = dict(DEFAULT_AUTO_TRADE_SETTINGS)
    if AUTO_TRADE_SETTINGS_FILE.exists():
        try:
            stored = json.loads(AUTO_TRADE_SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stored = {}
        if isinstance(stored, dict):
            settings.update(stored)
    return validate_auto_trade_settings(settings)


def validate_auto_trade_settings(settings):
    """Normalize limits and reject unsafe or nonsensical paper settings."""
    try:
        normalized = {
            "enabled": bool(settings.get("enabled", False)),
            "minimum_edge": float(settings.get("minimum_edge", 0.05)),
            "contracts_per_trade": int(settings.get("contracts_per_trade", 10)),
            "maximum_trade_cost": float(settings.get("maximum_trade_cost", 25)),
            "maximum_total_exposure": float(settings.get("maximum_total_exposure", 100)),
        }
    except (TypeError, ValueError) as error:
        raise ValueError("Automatic paper-trading limits must be valid numbers.") from error
    if not 0 <= normalized["minimum_edge"] <= 0.5:
        raise ValueError("Minimum edge must be between 0% and 50%.")
    if not 1 <= normalized["contracts_per_trade"] <= 10_000:
        raise ValueError("Contracts per trade must be between 1 and 10,000.")
    if not 0 < normalized["maximum_trade_cost"] <= 1_000_000:
        raise ValueError("Maximum trade cost must be greater than $0.")
    if not normalized["maximum_trade_cost"] <= normalized["maximum_total_exposure"] <= 10_000_000:
        raise ValueError("Total exposure must be at least the maximum trade cost.")
    return normalized


def save_auto_trade_settings(settings):
    """Persist automatic paper settings atomically."""
    normalized = validate_auto_trade_settings(settings)
    AUTO_TRADE_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = AUTO_TRADE_SETTINGS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    temporary.replace(AUTO_TRADE_SETTINGS_FILE)
    return normalized


def size_paper_order(portfolio, ask_price, settings):
    """Return a contract quantity within cash, trade, and exposure limits."""
    ask_price = float(ask_price)
    if not 0 < ask_price < 1:
        return 0
    settings = validate_auto_trade_settings(settings)
    exposure = sum(
        int(position.get("contracts", 0)) * float(position.get("average_cost", 0))
        for position in portfolio.get("positions", {}).values()
    )
    remaining_exposure = max(0.0, settings["maximum_total_exposure"] - exposure)
    limits = [
        settings["contracts_per_trade"],
        int(settings["maximum_trade_cost"] / ask_price),
        int(remaining_exposure / ask_price),
        int(float(portfolio.get("cash", 0)) / ask_price),
    ]
    return max(0, min(limits))
