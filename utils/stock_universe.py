"""Persistent large stock-universe management for Sentinel AI."""

import csv
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path

import requests

from utils.cloud_storage import load_cloud_json, save_cloud_json
from utils.symbols import normalize_symbol


UNIVERSE_FILE = Path(__file__).resolve().parents[1] / "data" / "stock_universe.json"
SP500_SOURCE = (
    "https://raw.githubusercontent.com/datasets/"
    "s-and-p-500-companies/main/data/constituents.csv"
)
NASDAQ100_SOURCE = (
    "https://raw.githubusercontent.com/Gary-Strauss/"
    "NASDAQ100_Constituents/master/data/nasdaq100_constituents.csv"
)


def new_universe():
    return {"name": "Custom universe", "symbols": [], "updated_at": None}


def _normalize_many(values):
    symbols = []
    invalid = []
    for value in values:
        raw = str(value).strip()
        if not raw:
            continue
        # Yahoo uses dashes for share classes such as BRK.B and BF.B.
        candidate = raw.replace(".", "-")
        try:
            symbol = normalize_symbol(candidate)
        except ValueError:
            invalid.append(raw)
            continue
        if symbol not in symbols:
            symbols.append(symbol)
    return symbols, invalid


def parse_universe_text(value):
    """Parse comma, whitespace, or newline-separated ticker symbols."""
    values = value.replace(",", " ").split()
    return _normalize_many(values)


def parse_universe_csv(content):
    """Read symbols from a CSV containing Symbol or Ticker, or its first column."""
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(content))
    if not reader.fieldnames:
        return [], []
    field_lookup = {name.strip().lower(): name for name in reader.fieldnames}
    symbol_field = field_lookup.get("symbol") or field_lookup.get("ticker")
    symbol_field = symbol_field or reader.fieldnames[0]
    return _normalize_many(row.get(symbol_field, "") for row in reader)


def fetch_sp500_symbols(timeout=20):
    """Fetch the maintained open S&P 500 constituent preset."""
    response = requests.get(SP500_SOURCE, timeout=timeout)
    response.raise_for_status()
    symbols, invalid = parse_universe_csv(response.text)
    if len(symbols) < 450:
        raise ValueError("The S&P 500 source returned an incomplete list.")
    return symbols, invalid


def fetch_nasdaq100_symbols(timeout=20):
    """Fetch the maintained open NASDAQ-100 constituent preset."""
    response = requests.get(NASDAQ100_SOURCE, timeout=timeout)
    response.raise_for_status()
    symbols, invalid = parse_universe_csv(response.text)
    if len(symbols) < 90:
        raise ValueError("The NASDAQ-100 source returned an incomplete list.")
    return symbols, invalid


def load_universe():
    """Load the saved universe with safe local fallback."""
    state = load_cloud_json("stock_universe", new_universe())
    if state is None:
        if not UNIVERSE_FILE.exists():
            return new_universe()
        try:
            state = json.loads(UNIVERSE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return new_universe()
    if not isinstance(state, dict) or not isinstance(state.get("symbols"), list):
        return new_universe()
    symbols, _invalid = _normalize_many(state["symbols"])
    return {
        "name": str(state.get("name") or "Custom universe"),
        "symbols": symbols,
        "updated_at": state.get("updated_at"),
    }


def save_universe(symbols, name="Custom universe"):
    """Normalize and persist one stock universe."""
    clean_symbols, invalid = _normalize_many(symbols)
    if not clean_symbols:
        raise ValueError("Add at least one valid stock symbol.")
    state = {
        "name": str(name).strip() or "Custom universe",
        "symbols": clean_symbols,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    UNIVERSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = UNIVERSE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temporary.replace(UNIVERSE_FILE)
    save_cloud_json("stock_universe", state)
    return state, invalid
