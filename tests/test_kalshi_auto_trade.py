from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from utils.kalshi_auto_trade import (
    load_auto_trade_settings,
    save_auto_trade_settings,
    size_paper_order,
)


class KalshiAutoTradeTests(unittest.TestCase):
    def test_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auto.json"
            with patch("utils.kalshi_auto_trade.AUTO_TRADE_SETTINGS_FILE", path):
                saved = save_auto_trade_settings(
                    {
                        "enabled": True,
                        "minimum_edge": 0.08,
                        "contracts_per_trade": 12,
                        "maximum_trade_cost": 20,
                        "maximum_total_exposure": 80,
                    }
                )
                self.assertTrue(saved["enabled"])
                self.assertEqual(load_auto_trade_settings(), saved)

    def test_order_size_respects_every_limit(self):
        portfolio = {
            "cash": 50,
            "positions": {
                "OLD:YES": {"contracts": 10, "average_cost": 0.5}
            },
        }
        settings = {
            "enabled": True,
            "minimum_edge": 0.05,
            "contracts_per_trade": 100,
            "maximum_trade_cost": 10,
            "maximum_total_exposure": 12,
        }
        self.assertEqual(size_paper_order(portfolio, 0.5, settings), 14)

    def test_invalid_exposure_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least"):
            save_auto_trade_settings(
                {
                    "maximum_trade_cost": 100,
                    "maximum_total_exposure": 50,
                }
            )


if __name__ == "__main__":
    unittest.main()
