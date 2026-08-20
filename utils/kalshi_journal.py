"""Persistent forward-only journal for experimental Kalshi forecasts."""

from datetime import datetime, timezone
import json
from pathlib import Path


FORECAST_JOURNAL_FILE = (
    Path(__file__).resolve().parents[1] / "data" / "kalshi_forecasts.json"
)


def load_forecast_journal():
    """Load valid journal rows, falling back safely for missing data."""
    if not FORECAST_JOURNAL_FILE.exists():
        return []
    try:
        rows = json.loads(FORECAST_JOURNAL_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [row for row in rows if isinstance(row, dict) and row.get("ticker")] if isinstance(rows, list) else []


def _save_forecast_journal(rows):
    FORECAST_JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = FORECAST_JOURNAL_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    temporary.replace(FORECAST_JOURNAL_FILE)
    return rows


def record_forecast(snapshot):
    """Record one immutable snapshot per contract and reject duplicates."""
    ticker = str(snapshot.get("ticker", "")).strip().upper()
    probability = float(snapshot.get("probability_yes"))
    if not ticker or not 0 <= probability <= 1:
        raise ValueError("A valid ticker and YES probability are required.")
    rows = load_forecast_journal()
    if any(str(row.get("ticker", "")).upper() == ticker for row in rows):
        raise ValueError("A forecast for this contract is already recorded.")
    row = {
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ticker": ticker,
        "asset": str(snapshot.get("asset", "")).upper(),
        "title": str(snapshot.get("title", "")),
        "close_time": snapshot.get("close_time"),
        "probability_yes": probability,
        "market_probability": float(snapshot.get("market_probability", 0)),
        "yes_ask": float(snapshot.get("yes_ask", 0)),
        "no_ask": float(snapshot.get("no_ask", 0)),
        "decision": str(snapshot.get("decision", "NO TRADE")),
        "estimated_edge": float(snapshot.get("estimated_edge", 0)),
        "start_price": float(snapshot.get("start_price", 0)),
        "current_price": float(snapshot.get("current_price", 0)),
        "result": None,
        "settled_at": None,
    }
    rows.append(row)
    _save_forecast_journal(rows)
    return row


def update_forecast_results(results):
    """Apply official YES/NO results without altering forecast inputs."""
    normalized = {str(key).upper(): str(value).lower() for key, value in results.items()}
    rows = load_forecast_journal()
    updated = 0
    for row in rows:
        result = normalized.get(str(row["ticker"]).upper())
        if row.get("result") is None and result in {"yes", "no"}:
            row["result"] = result
            row["settled_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            updated += 1
    if updated:
        _save_forecast_journal(rows)
    return updated


def summarize_forecasts(rows=None):
    """Calculate forward accuracy, calibration, and simulated decision P/L."""
    rows = rows if rows is not None else load_forecast_journal()
    settled = [row for row in rows if row.get("result") in {"yes", "no"}]
    if not settled:
        return {"total": len(rows), "settled": 0, "accuracy": None, "brier_score": None, "paper_profit": 0.0, "paper_trades": 0}
    correct = 0
    brier_total = 0.0
    paper_profit = 0.0
    paper_trades = 0
    for row in settled:
        outcome = 1.0 if row["result"] == "yes" else 0.0
        probability = float(row["probability_yes"])
        correct += int((probability >= 0.5) == bool(outcome))
        brier_total += (probability - outcome) ** 2
        decision = row.get("decision")
        if decision == "PAPER YES":
            paper_profit += (1.0 - float(row["yes_ask"])) if outcome else -float(row["yes_ask"])
            paper_trades += 1
        elif decision == "PAPER NO":
            paper_profit += (1.0 - float(row["no_ask"])) if not outcome else -float(row["no_ask"])
            paper_trades += 1
    return {
        "total": len(rows),
        "settled": len(settled),
        "accuracy": correct / len(settled),
        "brier_score": brier_total / len(settled),
        "paper_profit": paper_profit,
        "paper_trades": paper_trades,
    }
