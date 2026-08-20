from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from utils.kalshi_journal import (
    evaluate_forecasts,
    forecast_breakdowns,
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
                    "minutes_remaining": 4.5,
                    "minute_volatility": 0.0012,
                    "move_percent": 0.25,
                    "spread": 0.03,
                    "liquidity": 1200,
                    "volume_24h": 4500,
                    "data_provider": "Massive",
                    "method": "baseline",
                }
                recorded = record_forecast(snapshot)
                self.assertEqual(recorded["minutes_remaining"], 4.5)
                self.assertEqual(recorded["data_provider"], "Massive")
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

    def test_legacy_snapshot_records_missing_experiment_inputs_as_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.json"
            with patch("utils.kalshi_journal.FORECAST_JOURNAL_FILE", path):
                recorded = record_forecast(
                    {"ticker": "KXETH15M-LEGACY", "probability_yes": 0.5}
                )
        self.assertIsNone(recorded["minutes_remaining"])
        self.assertIsNone(recorded["minute_volatility"])
        self.assertEqual(recorded["data_provider"], "")

    def test_breakdowns_group_asset_and_forecast_timing(self):
        rows = [
            {
                "asset": "BTC", "minutes_remaining": 2.0, "result": "yes",
                "probability_yes": 0.8, "decision": "PAPER YES",
                "yes_ask": 0.6, "no_ask": 0.4,
            },
            {
                "asset": "ETH", "minutes_remaining": 7.0, "result": "no",
                "probability_yes": 0.3, "decision": "NO TRADE",
                "yes_ask": 0.4, "no_ask": 0.6,
            },
            {
                "asset": "BTC", "result": None, "probability_yes": 0.6,
                "decision": "NO TRADE", "yes_ask": 0.5, "no_ask": 0.5,
            },
        ]
        breakdowns = forecast_breakdowns(rows)
        assets = {row["Group"]: row for row in breakdowns["asset"]}
        timing = {row["Group"]: row for row in breakdowns["timing"]}
        self.assertEqual(assets["BTC"]["Recorded"], 2)
        self.assertEqual(assets["BTC"]["Accuracy"], 1.0)
        self.assertEqual(timing["1–3 min"]["Settled"], 1)
        self.assertEqual(timing["Other / unknown"]["Settled"], 0)

    def test_evaluation_compares_sentinel_with_market_and_calibrates(self):
        rows = [
            {
                "result": "yes", "probability_yes": 0.8,
                "market_probability": 0.6,
            },
            {
                "result": "no", "probability_yes": 0.2,
                "market_probability": 0.4,
            },
            {
                "result": None, "probability_yes": 0.9,
                "market_probability": 0.9,
            },
        ]
        evaluation = evaluate_forecasts(rows)
        self.assertEqual(evaluation["settled"], 2)
        self.assertAlmostEqual(evaluation["sentinel_brier"], 0.04)
        self.assertAlmostEqual(evaluation["market_brier"], 0.16)
        self.assertAlmostEqual(evaluation["brier_advantage"], 0.12)
        self.assertAlmostEqual(evaluation["average_disagreement"], 0.2)
        self.assertEqual(sum(row["Forecasts"] for row in evaluation["calibration"]), 2)

    def test_empty_evaluation_is_safe(self):
        evaluation = evaluate_forecasts([])
        self.assertEqual(evaluation["settled"], 0)
        self.assertIsNone(evaluation["sentinel_brier"])
        self.assertEqual(evaluation["calibration"], [])


if __name__ == "__main__":
    unittest.main()
