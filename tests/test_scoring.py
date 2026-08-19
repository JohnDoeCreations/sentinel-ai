import unittest

from strategies.scoring import calculate_score


class CalculateScoreTests(unittest.TestCase):
    def test_strong_setup_has_maximum_score_of_four(self):
        score, rating, strengths, weaknesses = calculate_score(
            current_price=110.0,
            moving_average=100.0,
            percent_change=1.5,
            rsi=50.0,
            current_macd=2.0,
            current_signal=1.0,
        )

        self.assertEqual(score, 4)
        self.assertEqual(rating, "STRONG SETUP")
        self.assertEqual(len(strengths), 4)
        self.assertEqual(weaknesses, [])

    def test_oversold_point_replaces_healthy_rsi_point(self):
        score, rating, strengths, _weaknesses = calculate_score(
            current_price=110.0,
            moving_average=100.0,
            percent_change=1.5,
            rsi=25.0,
            current_macd=2.0,
            current_signal=1.0,
        )

        self.assertEqual(score, 4)
        self.assertEqual(rating, "STRONG SETUP")
        self.assertIn("Stock may be oversold", strengths)
        self.assertNotIn("RSI is in a healthy range", strengths)

    def test_no_setup_for_bearish_inputs(self):
        score, rating, strengths, weaknesses = calculate_score(
            current_price=90.0,
            moving_average=100.0,
            percent_change=-1.5,
            rsi=75.0,
            current_macd=-2.0,
            current_signal=-1.0,
        )

        self.assertEqual(score, 0)
        self.assertEqual(rating, "NO SETUP")
        self.assertEqual(strengths, [])
        self.assertEqual(len(weaknesses), 4)


if __name__ == "__main__":
    unittest.main()
