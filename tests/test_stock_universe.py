from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock

from utils.stock_universe import (
    fetch_nasdaq100_symbols,
    load_universe,
    parse_universe_csv,
    parse_universe_text,
    save_universe,
)


class StockUniverseTests(unittest.TestCase):
    def test_fetches_complete_nasdaq100_preset(self):
        response = Mock()
        response.text = "Ticker,Company\n" + "\n".join(
            f"NQ{index},Company {index}" for index in range(100)
        )
        with patch("utils.stock_universe.requests.get", return_value=response):
            symbols, invalid = fetch_nasdaq100_symbols()

        response.raise_for_status.assert_called_once()
        self.assertEqual(len(symbols), 100)
        self.assertEqual(invalid, [])

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
