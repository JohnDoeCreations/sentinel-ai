import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from utils.paper_trading import load_portfolio
from utils.watchlist import load_watchlist


class PersistenceCleanupTests(unittest.TestCase):
    def test_watchlist_splits_legacy_compound_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "watchlist.json"
            path.write_text(
                json.dumps(["AAPL, NVDA", "AAPL", "bad symbol!"]),
                encoding="utf-8",
            )
            with patch("utils.watchlist.WATCHLIST_FILE", path):
                self.assertEqual(load_watchlist(), ["AAPL", "NVDA"])

    def test_portfolio_repairs_and_merges_legacy_positions(self):
        saved = {
            "starting_cash": 10_000.0,
            "cash": 8_000.0,
            "positions": {
                "AAPL": {"shares": 2, "average_cost": 100.0},
                "AAPL,": {"shares": 3, "average_cost": 110.0},
            },
            "transactions": [{"symbol": "AAPL,"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "portfolio.json"
            path.write_text(json.dumps(saved), encoding="utf-8")
            with patch("utils.paper_trading.PORTFOLIO_FILE", path):
                portfolio = load_portfolio()

        self.assertEqual(portfolio["positions"]["AAPL"]["shares"], 5)
        self.assertEqual(portfolio["positions"]["AAPL"]["average_cost"], 106.0)
        self.assertEqual(portfolio["transactions"][0]["symbol"], "AAPL")


if __name__ == "__main__":
    unittest.main()
