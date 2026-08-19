from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from utils.paper_trading import (
    buy_shares,
    calculate_position_size,
    load_portfolio,
    sell_shares,
)


class PaperTradingTests(unittest.TestCase):
    def test_position_size_respects_risk_cash_and_allocation(self):
        sizing = calculate_position_size(
            portfolio_value=10_000,
            available_cash=10_000,
            price=100,
            stop_loss_percent=5,
            risk_percent=1,
            maximum_position_percent=20,
        )
        self.assertEqual(sizing["suggested_shares"], 20)
        self.assertEqual(sizing["estimated_cost"], 2_000.0)

        nearly_full = calculate_position_size(
            portfolio_value=10_000,
            available_cash=10_000,
            price=100,
            stop_loss_percent=5,
            existing_position_value=1_900,
        )
        self.assertEqual(nearly_full["suggested_shares"], 1)

    def test_buy_and_sell_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "portfolio.json"
            with patch("utils.paper_trading.PORTFOLIO_FILE", path):
                buy_shares("aapl", 10, 100.0)
                portfolio = buy_shares("AAPL", 10, 120.0)
                self.assertEqual(portfolio["cash"], 7_800.0)
                self.assertEqual(portfolio["positions"]["AAPL"]["shares"], 20)
                self.assertEqual(
                    portfolio["positions"]["AAPL"]["average_cost"], 110.0
                )

                portfolio = sell_shares("AAPL", 5, 130.0)
                self.assertEqual(portfolio["positions"]["AAPL"]["shares"], 15)
                self.assertEqual(
                    portfolio["transactions"][-1]["realized_profit"], 100.0
                )

                portfolio = sell_shares("AAPL", 15, 90.0)
                self.assertNotIn("AAPL", portfolio["positions"])
                self.assertEqual(len(portfolio["transactions"]), 4)

    def test_rejects_invalid_orders(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "portfolio.json"
            with patch("utils.paper_trading.PORTFOLIO_FILE", path):
                with self.assertRaisesRegex(ValueError, "greater than zero"):
                    buy_shares("AAPL", 0, 100)
                with self.assertRaisesRegex(ValueError, "Insufficient cash"):
                    buy_shares("AAPL", 101, 100)
                with self.assertRaisesRegex(ValueError, "only 0 are owned"):
                    sell_shares("AAPL", 1, 100)

    def test_malformed_portfolio_falls_back_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "portfolio.json"
            path.write_text(
                '{"starting_cash": 1, "cash": 1, "positions": [], "transactions": {}}',
                encoding="utf-8",
            )
            with patch("utils.paper_trading.PORTFOLIO_FILE", path):
                portfolio = load_portfolio()
        self.assertEqual(portfolio["cash"], 10_000.0)
        self.assertEqual(portfolio["positions"], {})


if __name__ == "__main__":
    unittest.main()
