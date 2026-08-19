import unittest
from unittest.mock import patch

import pandas as pd

from utils.market_analysis import build_market_analysis


def market_history(length=80, start=100.0, step=1.0):
    close = pd.Series(
        [start + index * step for index in range(length)], dtype=float
    )
    return pd.DataFrame(
        {
            "High": close + 2.0,
            "Low": close - 2.0,
            "Close": close,
            "Volume": pd.Series([1_000_000.0] * length),
        }
    )


class MarketAnalysisTests(unittest.TestCase):
    @patch("utils.market_analysis.get_stock_data")
    def test_returns_none_for_empty_or_short_history(self, get_stock_data):
        get_stock_data.return_value = pd.DataFrame()
        self.assertIsNone(build_market_analysis("AAPL"))

        get_stock_data.return_value = market_history(length=49)
        self.assertIsNone(build_market_analysis("AAPL"))

    @patch("utils.market_analysis.get_stock_data")
    def test_builds_bullish_report_with_levels_and_scenarios(self, get_stock_data):
        get_stock_data.return_value = market_history()

        result = build_market_analysis(" aapl ")

        self.assertEqual(result["Symbol"], "AAPL")
        self.assertEqual(result["Bias"], "Bullish")
        self.assertEqual(result["Trend"], "Uptrend")
        self.assertEqual(result["Support"], 158.0)
        self.assertEqual(result["Resistance"], 181.0)
        self.assertIn("breakout", result["Bull Case"])
        self.assertIn("AAPL", result["Summary"])
        self.assertEqual(len(result["Chart Data"]), 80)
        get_stock_data.assert_called_once_with(
            "AAPL", period="1y", interval="1d"
        )

    @patch("utils.market_analysis.get_stock_data")
    def test_builds_bearish_report(self, get_stock_data):
        get_stock_data.return_value = market_history(start=200.0, step=-1.0)

        result = build_market_analysis("MSFT")

        self.assertEqual(result["Bias"], "Bearish")
        self.assertEqual(result["Trend"], "Downtrend")
        self.assertTrue(result["Risk Factors"])

    @patch("utils.market_analysis.get_stock_data")
    def test_rejects_nonpositive_closing_price(self, get_stock_data):
        data = market_history()
        data.loc[len(data) - 1, "Close"] = 0.0
        get_stock_data.return_value = data

        with self.assertRaisesRegex(ValueError, "invalid closing-price data"):
            build_market_analysis("ZERO")


if __name__ == "__main__":
    unittest.main()
