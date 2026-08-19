"""Risk-first trade planning calculations for Sentinel AI."""

import math


def calculate_trade_plan(
    account_value,
    available_cash,
    entry_price,
    stop_price,
    target_price,
    risk_percent=1.0,
    maximum_position_percent=20.0,
    existing_position_value=0.0,
):
    """Calculate a long-position plan constrained by risk, cash, and allocation."""
    account_value = float(account_value)
    available_cash = float(available_cash)
    entry_price = float(entry_price)
    stop_price = float(stop_price)
    target_price = float(target_price)
    risk_percent = float(risk_percent)
    maximum_position_percent = float(maximum_position_percent)
    existing_position_value = float(existing_position_value)

    if account_value <= 0 or available_cash < 0:
        raise ValueError("Account value must be positive and cash cannot be negative.")
    if entry_price <= 0 or stop_price <= 0 or target_price <= 0:
        raise ValueError("Entry, stop, and target prices must be positive.")
    if stop_price >= entry_price:
        raise ValueError("For a long trade, the stop must be below the entry price.")
    if target_price <= entry_price:
        raise ValueError("For a long trade, the target must be above the entry price.")
    if risk_percent <= 0 or maximum_position_percent <= 0:
        raise ValueError("Risk and maximum allocation must be greater than zero.")
    if existing_position_value < 0:
        raise ValueError("Existing position value cannot be negative.")

    risk_budget = account_value * risk_percent / 100
    risk_per_share = entry_price - stop_price
    reward_per_share = target_price - entry_price
    reward_to_risk = reward_per_share / risk_per_share

    maximum_position_value = account_value * maximum_position_percent / 100
    remaining_allocation = max(0.0, maximum_position_value - existing_position_value)
    shares_by_risk = math.floor(risk_budget / risk_per_share)
    shares_by_cash = math.floor(available_cash / entry_price)
    shares_by_allocation = math.floor(remaining_allocation / entry_price)
    suggested_shares = max(
        0,
        min(shares_by_risk, shares_by_cash, shares_by_allocation),
    )

    position_value = suggested_shares * entry_price
    planned_loss = suggested_shares * risk_per_share
    planned_profit = suggested_shares * reward_per_share
    stop_distance_percent = risk_per_share / entry_price * 100
    allocation_percent = position_value / account_value * 100

    limiting_values = {
        "Risk budget": shares_by_risk,
        "Available cash": shares_by_cash,
        "Allocation cap": shares_by_allocation,
    }
    limiting_factor = min(limiting_values, key=limiting_values.get)

    warnings = []
    if suggested_shares < 1:
        warnings.append("No shares fit the current risk, cash, and allocation limits.")
    if risk_percent > 2:
        warnings.append("Account risk above 2% can accelerate drawdowns.")
    if stop_distance_percent < 1:
        warnings.append("The stop is less than 1% from entry and may be sensitive to normal price noise.")
    elif stop_distance_percent > 10:
        warnings.append("The stop is more than 10% from entry, creating a wide risk range.")
    if reward_to_risk < 2:
        warnings.append("The selected target offers less than 2 units of reward for each unit of risk.")
    if available_cash > account_value:
        warnings.append("Available cash is greater than account value; verify the account inputs.")

    return {
        "suggested_shares": suggested_shares,
        "risk_budget": round(risk_budget, 2),
        "risk_per_share": round(risk_per_share, 2),
        "reward_per_share": round(reward_per_share, 2),
        "reward_to_risk": round(reward_to_risk, 2),
        "position_value": round(position_value, 2),
        "planned_loss": round(planned_loss, 2),
        "planned_profit": round(planned_profit, 2),
        "allocation_percent": round(allocation_percent, 2),
        "stop_distance_percent": round(stop_distance_percent, 2),
        "one_r_target": round(entry_price + risk_per_share, 2),
        "two_r_target": round(entry_price + 2 * risk_per_share, 2),
        "three_r_target": round(entry_price + 3 * risk_per_share, 2),
        "limiting_factor": limiting_factor,
        "maximum_position_value": round(maximum_position_value, 2),
        "warnings": warnings,
    }
