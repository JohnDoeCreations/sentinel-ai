"""Persistent local watchlist storage for Sentinel AI."""

import json
from pathlib import Path

from utils.cloud_storage import load_cloud_json, save_cloud_json
from utils.symbols import normalize_symbol, parse_symbol_list


WATCHLIST_FILE = Path(__file__).resolve().parents[1] / "data" / "watchlist.json"


def load_watchlist():
    """Return saved symbols, ignoring invalid or duplicate entries."""
    saved_data = load_cloud_json("watchlist", [])
    if saved_data is None:
        if not WATCHLIST_FILE.exists():
            return []
        try:
            saved_data = json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

    if not isinstance(saved_data, list):
        return []

    symbols = []
    for item in saved_data:
        if isinstance(item, str):
            try:
                saved_symbols = parse_symbol_list(item)
            except ValueError:
                continue
            for symbol in saved_symbols:
                if symbol not in symbols:
                    symbols.append(symbol)

    return symbols


def save_watchlist(symbols):
    """Normalize and save symbols to the local JSON file."""
    clean_symbols = []
    for item in symbols:
        symbol = normalize_symbol(item)
        if symbol not in clean_symbols:
            clean_symbols.append(symbol)

    WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = WATCHLIST_FILE.with_suffix(".tmp")
    temporary_file.write_text(
        json.dumps(clean_symbols, indent=2),
        encoding="utf-8",
    )
    temporary_file.replace(WATCHLIST_FILE)
    save_cloud_json("watchlist", clean_symbols)
    return clean_symbols


def add_symbol(symbol):
    """Add one symbol and return True only when the list changed."""
    clean_symbol = normalize_symbol(symbol)

    symbols = load_watchlist()
    if clean_symbol in symbols:
        return False

    symbols.append(clean_symbol)
    save_watchlist(symbols)
    return True


def remove_symbols(symbols_to_remove):
    """Remove selected symbols and return the updated watchlist."""
    removed = {normalize_symbol(symbol) for symbol in symbols_to_remove}
    remaining = [symbol for symbol in load_watchlist() if symbol not in removed]
    return save_watchlist(remaining)
