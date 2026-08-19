import unittest

from utils.portfolio_analytics import (
    concentration_summary,
    enrich_position_rows,
    equity_drawdown,
)


class PortfolioAnalyticsTests(unittest.TestCase):
    def test_enriches_positions_with_cost_and_allocation(self):
        rows = enrich_position_rows(
            [
                {
                    "Symbol": "AAPL",
                    "Shares": 10,
                    "Average Cost": 100,
                    "Market Value": 1_250,
                    "Unrealized P/L": 250,
                }
            ],
            portfolio_value=5_000,
        )
        self.assertEqual(rows[0]["Cost Basis"], 1_000)
        self.assertEqual(rows[0]["Allocation (%)"], 25.0)
        self.assertEqual(rows[0]["Return (%)"], 25.0)

    def test_concentration_summary_flags_large_positions(self):
        summary = concentration_summary(
            [
                {"Symbol": "AAPL", "Allocation (%)": 30.0},
                {"Symbol": "MSFT", "Allocation (%)": 20.0},
            ]
        )
        self.assertEqual(summary["largest_symbol"], "AAPL")
        self.assertEqual(summary["concentrated_symbols"], ["AAPL"])

    def test_equity_drawdown_uses_prior_peak(self):
        history, maximum_drawdown = equity_drawdown(
            [
                {"portfolio_value": 10_000},
                {"portfolio_value": 12_000},
                {"portfolio_value": 9_000},
                {"portfolio_value": 11_000},
            ]
        )
        self.assertEqual(maximum_drawdown, 25.0)
        self.assertAlmostEqual(history.iloc[-1]["drawdown_percent"], -8.3333, places=3)

    def test_empty_history_is_safe(self):
        history, maximum_drawdown = equity_drawdown([])
        self.assertTrue(history.empty)
        self.assertEqual(maximum_drawdown, 0.0)


if __name__ == "__main__":
    unittest.main()
