import unittest

from utils.trade_planner import calculate_trade_plan


class TradePlannerTests(unittest.TestCase):
    def test_calculates_risk_constrained_plan(self):
        plan = calculate_trade_plan(
            account_value=10_000,
            available_cash=10_000,
            entry_price=100,
            stop_price=95,
            target_price=110,
            risk_percent=1,
            maximum_position_percent=20,
        )

        self.assertEqual(plan["suggested_shares"], 20)
        self.assertEqual(plan["position_value"], 2_000.0)
        self.assertEqual(plan["planned_loss"], 100.0)
        self.assertEqual(plan["planned_profit"], 200.0)
        self.assertEqual(plan["reward_to_risk"], 2.0)
        self.assertEqual(plan["limiting_factor"], "Risk budget")
        self.assertFalse(plan["warnings"])

    def test_respects_existing_allocation_and_cash(self):
        allocation_limited = calculate_trade_plan(
            account_value=10_000,
            available_cash=10_000,
            entry_price=100,
            stop_price=99,
            target_price=102,
            existing_position_value=1_900,
        )
        self.assertEqual(allocation_limited["suggested_shares"], 1)
        self.assertEqual(allocation_limited["limiting_factor"], "Allocation cap")

        cash_limited = calculate_trade_plan(
            account_value=10_000,
            available_cash=250,
            entry_price=100,
            stop_price=95,
            target_price=110,
        )
        self.assertEqual(cash_limited["suggested_shares"], 2)
        self.assertEqual(cash_limited["limiting_factor"], "Available cash")

    def test_flags_aggressive_risk_and_weak_reward(self):
        plan = calculate_trade_plan(
            account_value=10_000,
            available_cash=10_000,
            entry_price=100,
            stop_price=99.5,
            target_price=100.5,
            risk_percent=3,
        )
        self.assertGreaterEqual(len(plan["warnings"]), 3)

    def test_rejects_invalid_long_trade_prices(self):
        with self.assertRaisesRegex(ValueError, "stop must be below"):
            calculate_trade_plan(10_000, 10_000, 100, 100, 110)
        with self.assertRaisesRegex(ValueError, "target must be above"):
            calculate_trade_plan(10_000, 10_000, 100, 95, 99)


if __name__ == "__main__":
    unittest.main()
