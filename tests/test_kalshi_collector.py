from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

import pandas as pd

from utils.kalshi_collector import collect_forecast_cycle


class KalshiCollectorTests(unittest.TestCase):
    @patch("utils.kalshi_collector.update_forecast_results", return_value=1)
    @patch("utils.kalshi_collector.fetch_market_result", return_value={"result": "yes"})
    @patch("utils.kalshi_collector.record_forecast")
    @patch("utils.kalshi_collector.get_crypto_minute_bars")
    @patch("utils.kalshi_collector.fetch_crypto_15m_markets")
    @patch("utils.kalshi_collector.load_forecast_journal")
    def test_cycle_records_eligible_and_settles_pending(
        self, load_journal, fetch_markets, get_bars, record, _result, update
    ):
        now = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
        load_journal.side_effect = [
            [{"ticker": "OLD", "result": None}],
            [{"ticker": "OLD", "result": None}],
        ]
        fetch_markets.return_value = [{
            "ticker": "NEW", "asset": "BTC", "title": "BTC up?",
            "close_time": (now + timedelta(minutes=5)).isoformat(),
            "yes_ask": 0.51, "no_ask": 0.50, "market_probability": 0.505,
        }]
        get_bars.return_value = pd.DataFrame({
            "Time": [now - timedelta(minutes=39-i) for i in range(40)],
            "Close": [100 + i * 0.02 for i in range(40)],
        })
        report = collect_forecast_cycle("key", now=now)
        self.assertEqual(report["recorded"], 1)
        self.assertEqual(report["settled"], 1)
        record.assert_called_once()
        update.assert_called_once_with({"OLD": "yes"})

    @patch("utils.kalshi_collector.fetch_crypto_15m_markets", return_value=[])
    @patch("utils.kalshi_collector.load_forecast_journal", return_value=[])
    def test_empty_cycle_is_safe(self, _journal, _markets):
        report = collect_forecast_cycle("key")
        self.assertEqual(report["recorded"], 0)
        self.assertEqual(report["errors"], [])


if __name__ == "__main__":
    unittest.main()
