from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from utils.kalshi import (
    buy_paper_contract,
    close_paper_contract,
    fetch_crypto_15m_markets,
    format_market_time,
    load_kalshi_paper_portfolio,
    paper_profit_summary,
    set_paper_cash_balance,
    settle_paper_contract,
)


class KalshiTests(unittest.TestCase):
    def test_formats_utc_market_close_in_mountain_time(self):
        formatted = format_market_time(
            "2026-08-21T00:15:00Z", "America/Denver"
        )
        self.assertEqual(formatted, "Aug 20, 2026 · 6:15 PM MDT")

    @patch("utils.kalshi.requests.get")
    def test_normalizes_public_market_prices(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "markets": [
                {
                    "ticker": "KXBTC15M-TEST",
                    "title": "Bitcoin up in 15 minutes?",
                    "yes_bid_dollars": "0.4700",
                    "yes_ask_dollars": "0.5100",
                    "no_bid_dollars": "0.4900",
                    "no_ask_dollars": "0.5300",
                    "last_price_dollars": "0.5000",
                    "volume_fp": "120.00",
                    "volume_24h_fp": "80.00",
                    "liquidity_dollars": "450.00",
                    "close_time": "2026-08-20T23:00:00Z",
                    "status": "active",
                }
            ]
        }
        get.return_value = response

        markets = fetch_crypto_15m_markets(["BTC"])

        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0]["asset"], "BTC")
        self.assertAlmostEqual(markets[0]["market_probability"], 0.49)
        self.assertAlmostEqual(markets[0]["spread"], 0.04)

    def test_paper_contract_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kalshi.json"
            with patch("utils.kalshi.PAPER_PORTFOLIO_FILE", path):
                portfolio = buy_paper_contract(
                    "KXBTC15M-TEST",
                    "Bitcoin up?",
                    "BTC",
                    "YES",
                    10,
                    0.40,
                )
                self.assertEqual(portfolio["cash"], 996.0)
                key = "KXBTC15M-TEST:YES"
                self.assertEqual(portfolio["positions"][key]["contracts"], 10)

                portfolio = close_paper_contract(key, 4, 0.60)
                self.assertEqual(portfolio["positions"][key]["contracts"], 6)
                self.assertEqual(
                    portfolio["transactions"][-1]["realized_profit"], 0.8
                )

                portfolio = close_paper_contract(key, 6, 0.20)
                self.assertNotIn(key, portfolio["positions"])

    def test_rejects_invalid_paper_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kalshi.json"
            with patch("utils.kalshi.PAPER_PORTFOLIO_FILE", path):
                with self.assertRaisesRegex(ValueError, r"between \$0 and \$1"):
                    buy_paper_contract("TEST", "Test", "BTC", "YES", 1, 1.0)
                self.assertEqual(load_kalshi_paper_portfolio()["cash"], 1_000.0)

    def test_sets_simulated_cash_and_records_adjustment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kalshi.json"
            with patch("utils.kalshi.PAPER_PORTFOLIO_FILE", path):
                portfolio = set_paper_cash_balance(5_000)
                self.assertEqual(portfolio["cash"], 5_000)
                self.assertEqual(portfolio["cash_adjustments"], 4_000)
                self.assertEqual(portfolio["transactions"][-1]["action"], "CASH ADJUSTMENT")
                self.assertEqual(portfolio["transactions"][-1]["total"], 4_000)

                unchanged = set_paper_cash_balance(5_000)
                self.assertEqual(len(unchanged["transactions"]), 1)

    def test_rejects_invalid_simulated_cash(self):
        with self.assertRaisesRegex(ValueError, "between"):
            set_paper_cash_balance(-1)

    def test_settles_winning_and_losing_paper_contracts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kalshi.json"
            with patch("utils.kalshi.PAPER_PORTFOLIO_FILE", path):
                buy_paper_contract("MARKET", "Test", "BTC", "YES", 2, 0.4)
                buy_paper_contract("MARKET", "Test", "BTC", "NO", 3, 0.7)
                self.assertEqual(settle_paper_contract("MARKET", "yes"), 2)
                portfolio = load_kalshi_paper_portfolio()
                self.assertFalse(portfolio["positions"])
                settlements = [
                    row for row in portfolio["transactions"]
                    if row["action"] == "SETTLE"
                ]
                self.assertEqual(len(settlements), 2)
                self.assertEqual(settlements[0]["price"], 1.0)
                self.assertEqual(settlements[1]["price"], 0.0)

    def test_profit_summary_excludes_cash_adjustments(self):
        portfolio = {
            "transactions": [
                {"action": "CASH ADJUSTMENT", "total": 5_000},
                {
                    "action": "CLOSE", "timestamp": "2026-08-21T00:00:00Z",
                    "ticker": "WIN", "side": "YES", "realized_profit": 4.0,
                },
                {
                    "action": "SETTLE", "timestamp": "2026-08-21T00:15:00Z",
                    "ticker": "LOSS", "side": "NO", "realized_profit": -1.5,
                },
            ]
        }
        summary = paper_profit_summary(portfolio, unrealized_profit=0.75)
        self.assertEqual(summary["realized_profit"], 2.5)
        self.assertEqual(summary["total_profit"], 3.25)
        self.assertEqual(summary["closed_trades"], 2)
        self.assertEqual(summary["win_rate"], 0.5)
        self.assertEqual(summary["history"][-1]["Cumulative realized P/L"], 2.5)


if __name__ == "__main__":
    unittest.main()
