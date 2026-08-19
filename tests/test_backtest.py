from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from backtesting.backtest import TRADE_LOG_COLUMNS, backtest, backtest_watchlist


def price_data(length=80, rising=False):
    index = pd.date_range("2025-01-01", periods=length, freq="B")
    close = pd.Series(
        [100.0 + index * 0.5 if rising else 100.0 for index in range(length)],
        index=index,
    )
    return pd.DataFrame(
        {
            "Open": close,
            "High": close + (4.0 if rising else 1.0),
            "Low": close - 1.0,
            "Close": close,
        },
        index=index,
    )


class BacktestTests(unittest.TestCase):
    def test_empty_and_short_history_return_none(self):
        with patch("backtesting.backtest.get_stock_data", return_value=pd.DataFrame()):
            self.assertIsNone(backtest("AAPL", show_chart=False))

        with patch(
            "backtesting.backtest.get_stock_data", return_value=price_data(60)
        ):
            self.assertIsNone(backtest("AAPL", show_chart=False))

    def test_zero_trade_backtest_writes_headered_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory)
            with (
                patch("backtesting.backtest.RESULTS_FOLDER", results),
                patch(
                    "backtesting.backtest.get_stock_data",
                    return_value=price_data(),
                ),
            ):
                result = backtest("aapl", show_chart=False)

            trade_log = pd.read_csv(results / "AAPL_backtest.csv")

        self.assertEqual(result["Trades"], 0)
        self.assertEqual(list(trade_log.columns), TRADE_LOG_COLUMNS)
        self.assertTrue(trade_log.empty)

    def test_forced_bullish_setup_records_trade_and_chart(self):
        macd = pd.Series([2.0] * 80)
        signal = pd.Series([1.0] * 80)
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory)
            with (
                patch("backtesting.backtest.RESULTS_FOLDER", results),
                patch(
                    "backtesting.backtest.get_stock_data",
                    return_value=price_data(rising=True),
                ),
                patch("backtesting.backtest.calculate_score", return_value=(4, "STRONG SETUP", [], [])),
                patch("backtesting.backtest.calculate_ema", side_effect=lambda _prices, period: 110.0 if period == 20 else 100.0),
                patch("backtesting.backtest.calculate_atr", return_value=1.0),
                patch("backtesting.backtest.calculate_rsi", return_value=50.0),
                patch("backtesting.backtest.calculate_moving_average", return_value=100.0),
                patch("backtesting.backtest.calculate_macd", return_value=(macd, signal, macd - signal)),
            ):
                result = backtest("AAPL", show_chart=False)
                trade_log = pd.read_csv(results / "AAPL_backtest.csv")
                chart_exists = (results / "AAPL_equity_curve.png").exists()

        self.assertGreater(result["Trades"], 0)
        self.assertFalse(trade_log.empty)
        self.assertIn("Take Profit", set(trade_log["Exit Reason"]))
        self.assertTrue(chart_exists)

    def test_watchlist_summary_is_sorted_and_returned(self):
        def summary(symbol, strategy_return):
            return {
                "Symbol": symbol,
                "Trades": 3,
                "Win Rate": 66.67,
                "Profit Factor": 1.5,
                "Strategy Return": strategy_return,
                "Buy & Hold": 4.0,
                "Max Drawdown": 2.0,
            }

        results_by_symbol = {
            "AAPL": summary("AAPL", 2.0),
            "NVDA": summary("NVDA", 8.0),
        }
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory)
            with (
                patch("backtesting.backtest.RESULTS_FOLDER", results),
                patch(
                    "backtesting.backtest.backtest",
                    side_effect=lambda symbol, show_chart=False: results_by_symbol[symbol],
                ),
            ):
                summary = backtest_watchlist(["AAPL", "NVDA"])

        self.assertEqual(summary["Symbol"].tolist(), ["NVDA", "AAPL"])


if __name__ == "__main__":
    unittest.main()
