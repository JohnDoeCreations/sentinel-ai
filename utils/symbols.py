"""Shared ticker-symbol validation and legacy cleanup."""

import re


SYMBOL_PATTERN = re.compile(r"^[A-Z0-9^][A-Z0-9.^=\-]{0,19}$")


def normalize_symbol(symbol):
    """Return a normalized ticker or raise ValueError when it is malformed."""
    if not isinstance(symbol, str):
        raise ValueError("A stock symbol must be text.")

    clean_symbol = symbol.strip().upper()
    if not clean_symbol:
        raise ValueError("A stock symbol is required.")
    if not SYMBOL_PATTERN.fullmatch(clean_symbol):
        raise ValueError(
            "Use one symbol at a time with letters, numbers, '.', '-', '^', or '='."
        )
    return clean_symbol


def normalize_legacy_symbol(symbol):
    """Normalize older saved symbols that may have surrounding commas."""
    if not isinstance(symbol, str):
        raise ValueError("A stock symbol must be text.")
    return normalize_symbol(symbol.strip().strip(","))


def parse_symbol_list(value):
    """Parse a comma-separated string into unique validated symbols."""
    symbols = []
    for item in value.split(","):
        if not item.strip():
            continue
        symbol = normalize_symbol(item)
        if symbol not in symbols:
            symbols.append(symbol)
    return symbols
