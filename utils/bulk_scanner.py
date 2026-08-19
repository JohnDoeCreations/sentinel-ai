"""Persistent batched scanning for large stock universes."""

from datetime import datetime, timezone
import json
from pathlib import Path

from utils.cloud_storage import load_cloud_json, save_cloud_json
from utils.stock_universe import load_universe


RESULTS_FILE = Path(__file__).resolve().parents[1] / "data" / "bulk_scan_results.json"


def new_bulk_scan_state():
    return {
        "results": {},
        "errors": {},
        "cursor": 0,
        "last_run_at": None,
        "last_batch_size": 0,
    }


def load_bulk_scan_state():
    state = load_cloud_json("bulk_scan_results", new_bulk_scan_state())
    if state is None:
        if not RESULTS_FILE.exists():
            return new_bulk_scan_state()
        try:
            state = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return new_bulk_scan_state()
    if not isinstance(state, dict):
        return new_bulk_scan_state()
    state.setdefault("results", {})
    state.setdefault("errors", {})
    state.setdefault("cursor", 0)
    state.setdefault("last_run_at", None)
    state.setdefault("last_batch_size", 0)
    if not isinstance(state["results"], dict):
        state["results"] = {}
    if not isinstance(state["errors"], dict):
        state["errors"] = {}
    return state


def save_bulk_scan_state(state):
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = RESULTS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temporary.replace(RESULTS_FILE)
    save_cloud_json("bulk_scan_results", state)
    return state


def scan_next_batch(analyze_symbol, batch_size=25, symbols=None):
    """Scan the next universe slice, persist results, and advance the cursor."""
    universe_symbols = list(symbols or load_universe()["symbols"])
    if not universe_symbols:
        raise ValueError("The stock universe is empty.")
    batch_size = max(1, min(int(batch_size), len(universe_symbols)))
    state = load_bulk_scan_state()
    allowed_symbols = set(universe_symbols)
    state["results"] = {
        symbol: result
        for symbol, result in state["results"].items()
        if symbol in allowed_symbols
    }
    state["errors"] = {
        symbol: message
        for symbol, message in state["errors"].items()
        if symbol in allowed_symbols
    }
    cursor = int(state.get("cursor", 0)) % len(universe_symbols)
    batch = [
        universe_symbols[(cursor + offset) % len(universe_symbols)]
        for offset in range(batch_size)
    ]
    completed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for symbol in batch:
        try:
            result = analyze_symbol(symbol)
            if result is None:
                raise ValueError("Not enough market data.")
            result = dict(result)
            result["Scanned At"] = completed_at
            state["results"][symbol] = result
            state["errors"].pop(symbol, None)
        except Exception as error:
            state["errors"][symbol] = str(error)

    state["cursor"] = (cursor + batch_size) % len(universe_symbols)
    state["last_run_at"] = completed_at
    state["last_batch_size"] = len(batch)
    save_bulk_scan_state(state)
    return {"batch": batch, "state": state}
