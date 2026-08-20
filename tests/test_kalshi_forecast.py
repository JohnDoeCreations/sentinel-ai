from datetime import datetime, timedelta, timezone
import unittest

import pandas as pd

from utils.kalshi_forecast import estimate_direction_probability, forecast_decision


class KalshiForecastTests(unittest.TestCase):
    def test_rising_price_produces_higher_yes_probability(self):
        now = datetime(2026, 8, 20, 12, 10, tzinfo=timezone.utc)
        times = [now - timedelta(minutes=39 - index) for index in range(40)]
        bars = pd.DataFrame(
            {"Time": times, "Close": [100 + index * 0.05 for index in range(40)]}
        )
        result = estimate_direction_probability(
            bars,
            now + timedelta(minutes=5),
            now=now,
        )
        self.assertGreater(result["probability_yes"], 0.5)

    def test_decision_requires_minimum_edge(self):
        self.assertEqual(forecast_decision(0.54, 0.52, 0.49)["decision"], "NO TRADE")
        self.assertEqual(forecast_decision(0.70, 0.55, 0.46)["decision"], "PAPER YES")


if __name__ == "__main__":
    unittest.main()
