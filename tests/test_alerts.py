import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from utils.alerts import (
    add_alert,
    delete_alert,
    evaluate_alert,
    load_alert_state,
    record_alert_check,
    set_alert_enabled,
)
from utils.alert_monitor import check_enabled_alerts


ANALYSIS = {
    "Price": 125.0,
    "Score": 4,
    "Signal": "BULLISH WATCH",
    "RSI": 72.0,
}


class AlertTests(unittest.TestCase):
    def test_alert_lifecycle_and_trigger_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "alerts.json"
            with patch("utils.alerts.ALERTS_FILE", path):
                alert = add_alert(" aapl ", "price_above", 120.0)
                triggered, current, message = evaluate_alert(alert, ANALYSIS)
                self.assertTrue(triggered)

                record_alert_check(alert["id"], triggered, current, message)
                record_alert_check(alert["id"], triggered, current, message)
                state = load_alert_state()
                self.assertEqual(len(state["history"]), 1)
                self.assertTrue(state["alerts"][0]["is_triggered"])

                set_alert_enabled(alert["id"], False)
                state = load_alert_state()
                self.assertFalse(state["alerts"][0]["enabled"])
                self.assertFalse(state["alerts"][0]["is_triggered"])

                delete_alert(alert["id"])
                state = load_alert_state()
                self.assertEqual(state["alerts"], [])
                self.assertEqual(len(state["history"]), 1)

    def test_rule_evaluation_boundaries(self):
        cases = [
            ({"type": "price_below", "target": 125.0}, None, True),
            ({"type": "score_at_least", "target": 4}, None, True),
            ({"type": "signal_equals", "target": "BULLISH WATCH"}, None, True),
            ({"type": "rsi_above", "target": 72.0}, None, True),
            ({"type": "rsi_below", "target": 30.0}, None, False),
            ({"type": "position_gain_at_least", "target": 5.0}, 5.0, True),
            ({"type": "position_loss_at_most", "target": 5.0}, -5.0, True),
        ]
        for rule, position_return, expected in cases:
            alert = {"symbol": "AAPL", **rule}
            with self.subTest(rule=rule):
                result, _current, _message = evaluate_alert(
                    alert, ANALYSIS, position_return
                )
                self.assertEqual(result, expected)

    def test_malformed_collections_are_repaired(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "alerts.json"
            path.write_text(
                json.dumps({"alerts": "invalid", "history": {}}),
                encoding="utf-8",
            )
            with patch("utils.alerts.ALERTS_FILE", path):
                self.assertEqual(
                    load_alert_state(),
                    {"alerts": [], "history": []},
                )

    def test_batch_check_reuses_analysis_and_avoids_duplicate_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "alerts.json"
            with patch("utils.alerts.ALERTS_FILE", path):
                add_alert("AAPL", "price_above", 120.0)
                add_alert("AAPL", "rsi_above", 70.0)
                calls = []

                def analyzer(symbol):
                    calls.append(symbol)
                    return ANALYSIS

                first = check_enabled_alerts(
                    analyzer,
                    checked_at="2026-08-18T12:00:00+00:00",
                )
                second = check_enabled_alerts(
                    analyzer,
                    checked_at="2026-08-18T12:05:00+00:00",
                )
                state = load_alert_state()

        self.assertEqual(first["checked"], 2)
        self.assertEqual(first["symbols_analyzed"], 1)
        self.assertEqual(len(first["newly_triggered"]), 2)
        self.assertEqual(len(second["newly_triggered"]), 0)
        self.assertEqual(len(state["history"]), 2)
        self.assertEqual(calls, ["AAPL", "AAPL"])

    def test_batch_check_records_errors_without_stopping_other_alerts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "alerts.json"
            with patch("utils.alerts.ALERTS_FILE", path):
                add_alert("AAPL", "price_above", 120.0)
                add_alert("MSFT", "price_above", 120.0)

                def analyzer(symbol):
                    if symbol == "AAPL":
                        raise RuntimeError("provider unavailable")
                    return ANALYSIS

                result = check_enabled_alerts(analyzer)
                state = load_alert_state()

        self.assertEqual(result["checked"], 1)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(state["alerts"][0]["last_error"], "provider unavailable")


if __name__ == "__main__":
    unittest.main()
