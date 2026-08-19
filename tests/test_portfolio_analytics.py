import unittest

from utils.portfolio_analytics import (
    concentration_summary,
    enrich_position_rows,
    equity_drawdown,
    protection_risk_rows,
    protection_risk_summary,
)


class PortfolioAnalyticsTests(unittest.TestCase):
    def test_protection_risk_summary_tracks_coverage_and_planned_loss(self):
        positions = {
            "AAPL": {"shares": 10, "average_cost": 100.0},
            "MSFT": {"shares": 5, "average_cost": 200.0},
        }
        alerts = [
            {
                "symbol": "AAPL",
                "type": "position_loss_at_most",
                "target": 5.0,
                "source": "paper_trade",
                "enabled": True,
            },
            {
                "symbol": "AAPL",
                "type": "position_gain_at_least",
                "target": 10.0,
                "source": "paper_trade",
                "enabled": True,
            },
        ]
        rows = protection_risk_rows(positions, alerts)
        summary = protection_risk_summary(rows)

        self.assertEqual(summary["coverage_percent"], 50.0)
        self.assertEqual(summary["planned_risk"], 50.0)
        self.assertEqual(summary["unprotected_value"], 1_000.0)
        self.assertEqual(rows[0]["Status"], "Protected")
        self.assertEqual(rows[1]["Status"], "Needs protection")

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
