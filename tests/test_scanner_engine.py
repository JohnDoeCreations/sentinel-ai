import unittest
from unittest.mock import patch

import pandas as pd

from utils.scanner_engine import analyze_stock


def close_data(length=40):
    """Return predictable closing-price data for scanner tests."""
    return pd.DataFrame(
        {"Close": pd.Series(range(100, 100 + length), dtype=float)}
    )


class AnalyzeStockTests(unittest.TestCase):
    @patch("utils.scanner_engine.get_stock_data")
    def test_returns_none_for_empty_data(self, get_stock_data):
        get_stock_data.return_value = pd.DataFrame()

        self.assertIsNone(analyze_stock("AAPL"))

    @patch("utils.scanner_engine.get_stock_data")
    def test_returns_none_when_history_is_too_short(self, get_stock_data):
        get_stock_data.return_value = close_data(25)

        self.assertIsNone(analyze_stock("AAPL"))

    @patch("utils.scanner_engine.calculate_score")
    @patch("utils.scanner_engine.calculate_macd")
    @patch("utils.scanner_engine.calculate_rsi", return_value=50.0)
    @patch("utils.scanner_engine.calculate_moving_average", return_value=120.0)
    @patch("utils.scanner_engine.get_stock_data")
    def test_normalizes_symbol_and_returns_expected_fields(
        self,
        get_stock_data,
        _moving_average,
        _rsi,
        calculate_macd,
        calculate_score,
    ):
        get_stock_data.return_value = close_data()
        macd = pd.Series([0.0] * 39 + [2.0])
        signal = pd.Series([0.0] * 39 + [1.0])
        calculate_macd.return_value = macd, signal, macd - signal
        calculate_score.return_value = (
            4,
            "STRONG SETUP",
            ["Bullish"],
            [],
        )

        result = analyze_stock(" aapl ")

        self.assertEqual(result["Symbol"], "AAPL")
        self.assertEqual(result["Price"], 139.0)
        self.assertEqual(result["Signal"], "BULLISH WATCH")
        self.assertEqual(result["Score"], 4)
        self.assertIn("Strengths", result)
        get_stock_data.assert_called_once_with(
            "AAPL", period="3mo", interval="1d"
        )

    def test_rejects_zero_previous_close(self):
        data = close_data()
        data.loc[len(data) - 2, "Close"] = 0.0

        with patch("utils.scanner_engine.get_stock_data", return_value=data):
            with self.assertRaisesRegex(ValueError, "invalid previous closing price"):
                analyze_stock("ZERO")

    def test_overbought_signal_takes_priority(self):
        with (
            patch("utils.scanner_engine.get_stock_data", return_value=close_data()),
            patch("utils.scanner_engine.calculate_moving_average", return_value=120.0),
            patch("utils.scanner_engine.calculate_rsi", return_value=75.0),
            patch(
                "utils.scanner_engine.calculate_macd",
                return_value=(pd.Series([2.0]), pd.Series([1.0]), pd.Series([1.0])),
            ),
            patch(
                "utils.scanner_engine.calculate_score",
                return_value=(4, "STRONG SETUP", [], []),
            ),
        ):
            self.assertEqual(analyze_stock("AAPL")["Signal"], "OVERBOUGHT WATCH")

    def test_oversold_signal_takes_priority(self):
        with (
            patch("utils.scanner_engine.get_stock_data", return_value=close_data()),
            patch("utils.scanner_engine.calculate_moving_average", return_value=120.0),
            patch("utils.scanner_engine.calculate_rsi", return_value=25.0),
            patch(
                "utils.scanner_engine.calculate_macd",
                return_value=(pd.Series([0.0]), pd.Series([1.0]), pd.Series([-1.0])),
            ),
            patch(
                "utils.scanner_engine.calculate_score",
                return_value=(1, "WEAK SETUP", [], []),
            ),
        ):
            self.assertEqual(analyze_stock("AAPL")["Signal"], "OVERSOLD WATCH")


if __name__ == "__main__":
    unittest.main()
