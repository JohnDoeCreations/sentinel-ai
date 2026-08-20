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


def _number(value, default=0.0):
    """Convert optional market inputs without breaking older journal rows."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def record_forecast(snapshot):
    """Record one immutable snapshot per contract and reject duplicates."""
    ticker = str(snapshot.get("ticker", "")).strip().upper()
    probability = _number(snapshot.get("probability_yes"), default=-1.0)
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
        "market_probability": _number(snapshot.get("market_probability")),
        "yes_ask": _number(snapshot.get("yes_ask")),
        "no_ask": _number(snapshot.get("no_ask")),
        "decision": str(snapshot.get("decision", "NO TRADE")),
        "estimated_edge": _number(snapshot.get("estimated_edge")),
        "start_price": _number(snapshot.get("start_price")),
        "current_price": _number(snapshot.get("current_price")),
        "minutes_remaining": _number(snapshot.get("minutes_remaining"), None),
        "minute_volatility": _number(snapshot.get("minute_volatility"), None),
        "move_percent": _number(snapshot.get("move_percent"), None),
        "spread": _number(snapshot.get("spread"), None),
        "liquidity": _number(snapshot.get("liquidity"), None),
        "volume_24h": _number(snapshot.get("volume_24h"), None),
        "data_provider": str(snapshot.get("data_provider", "") or ""),
        "method": str(snapshot.get("method", "") or ""),
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


def _breakdown_row(label, rows):
    summary = summarize_forecasts(rows)
    return {
        "Group": label,
        "Recorded": summary["total"],
        "Settled": summary["settled"],
        "Accuracy": summary["accuracy"],
        "Brier score": summary["brier_score"],
        "Paper profit": summary["paper_profit"],
        "Paper trades": summary["paper_trades"],
    }


def forecast_breakdowns(rows=None):
    """Summarize results by asset and time remaining at prediction."""
    rows = rows if rows is not None else load_forecast_journal()
    assets = sorted({str(row.get("asset", "")).upper() for row in rows if row.get("asset")})
    by_asset = [
        _breakdown_row(asset, [row for row in rows if str(row.get("asset", "")).upper() == asset])
        for asset in assets
    ]

    timing_groups = {
        "1–3 min": [],
        "3–6 min": [],
        "6–10 min": [],
        "Other / unknown": [],
    }
    for row in rows:
        minutes = _number(row.get("minutes_remaining"), None)
        if minutes is not None and 1 <= minutes < 3:
            timing_groups["1–3 min"].append(row)
        elif minutes is not None and 3 <= minutes < 6:
            timing_groups["3–6 min"].append(row)
        elif minutes is not None and 6 <= minutes <= 10:
            timing_groups["6–10 min"].append(row)
        else:
            timing_groups["Other / unknown"].append(row)
    by_timing = [
        _breakdown_row(label, group)
        for label, group in timing_groups.items()
        if group
    ]
    return {"asset": by_asset, "timing": by_timing}


def evaluate_forecasts(rows=None, bin_width=0.2):
    """Compare settled Sentinel probabilities with the recorded Kalshi market."""
    rows = rows if rows is not None else load_forecast_journal()
    settled = [row for row in rows if row.get("result") in {"yes", "no"}]
    if not settled:
        return {
            "settled": 0,
            "sentinel_brier": None,
            "market_brier": None,
            "brier_advantage": None,
            "average_disagreement": None,
            "calibration": [],
        }

    sentinel_errors = []
    market_errors = []
    disagreements = []
    bins = {}
    for row in settled:
        outcome = 1.0 if row["result"] == "yes" else 0.0
        sentinel_probability = min(max(_number(row.get("probability_yes")), 0.0), 1.0)
        market_probability = min(max(_number(row.get("market_probability")), 0.0), 1.0)
        sentinel_errors.append((sentinel_probability - outcome) ** 2)
        market_errors.append((market_probability - outcome) ** 2)
        disagreements.append(abs(sentinel_probability - market_probability))
        lower = min(int(sentinel_probability / bin_width) * bin_width, 1.0 - bin_width)
        label = f"{lower:.1f}–{lower + bin_width:.1f}"
        bins.setdefault(label, {"probabilities": [], "outcomes": []})
        bins[label]["probabilities"].append(sentinel_probability)
        bins[label]["outcomes"].append(outcome)

    calibration = []
    for label, values in bins.items():
        calibration.append(
            {
                "Probability range": label,
                "Average forecast": sum(values["probabilities"]) / len(values["probabilities"]),
                "Observed YES rate": sum(values["outcomes"]) / len(values["outcomes"]),
                "Forecasts": len(values["outcomes"]),
            }
        )
    calibration.sort(key=lambda row: row["Average forecast"])
    sentinel_brier = sum(sentinel_errors) / len(settled)
    market_brier = sum(market_errors) / len(settled)
    return {
        "settled": len(settled),
        "sentinel_brier": sentinel_brier,
        "market_brier": market_brier,
        "brier_advantage": market_brier - sentinel_brier,
        "average_disagreement": sum(disagreements) / len(disagreements),
        "calibration": calibration,
    }
