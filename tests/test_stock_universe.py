from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from utils.stock_universe import (
    load_universe,
    parse_universe_csv,
    parse_universe_text,
    save_universe,
)


class StockUniverseTests(unittest.TestCase):
    def test_parses_bulk_text_and_yahoo_share_classes(self):
        symbols, invalid = parse_universe_text("AAPL, MSFT\nBRK.B AAPL bad/name")
        self.assertEqual(symbols, ["AAPL", "MSFT", "BRK-B"])
        self.assertEqual(invalid, ["bad/name"])

    def test_parses_symbol_or_first_csv_column(self):
        symbols, invalid = parse_universe_csv(
            "Symbol,Company\nAAPL,Apple\nMSFT,Microsoft\n"
        )
        self.assertEqual(symbols, ["AAPL", "MSFT"])
        self.assertEqual(invalid, [])

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "universe.json"
            with patch("utils.stock_universe.UNIVERSE_FILE", path):
                save_universe(["AAPL", "MSFT"], "Leaders")
                state = load_universe()
        self.assertEqual(state["name"], "Leaders")
        self.assertEqual(state["symbols"], ["AAPL", "MSFT"])
