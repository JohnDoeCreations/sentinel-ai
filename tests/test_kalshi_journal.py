from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from utils.kalshi_journal import (
    load_forecast_journal,
    record_forecast,
    summarize_forecasts,
    update_forecast_results,
)


class KalshiJournalTests(unittest.TestCase):
    def test_record_duplicate_settle_and_summarize(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.json"
            with patch("utils.kalshi_journal.FORECAST_JOURNAL_FILE", path):
                snapshot = {
                    "ticker": "KXBTC15M-TEST",
                    "asset": "BTC",
                    "probability_yes": 0.70,
                    "market_probability": 0.55,
                    "yes_ask": 0.56,
                    "no_ask": 0.46,
                    "decision": "PAPER YES",
                    "estimated_edge": 0.14,
                }
                record_forecast(snapshot)
                with self.assertRaisesRegex(ValueError, "already recorded"):
                    record_forecast(snapshot)
                self.assertEqual(update_forecast_results({"KXBTC15M-TEST": "yes"}), 1)
                summary = summarize_forecasts(load_forecast_journal())
                self.assertEqual(summary["settled"], 1)
                self.assertEqual(summary["accuracy"], 1.0)
                self.assertAlmostEqual(summary["brier_score"], 0.09)
                self.assertAlmostEqual(summary["paper_profit"], 0.44)

    def test_empty_summary_is_safe(self):
        summary = summarize_forecasts([])
        self.assertIsNone(summary["accuracy"])
        self.assertEqual(summary["settled"], 0)


if __name__ == "__main__":
    unittest.main()
