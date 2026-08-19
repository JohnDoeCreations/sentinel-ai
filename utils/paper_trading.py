"""Persistent simulated portfolio engine for Sentinel AI."""

from datetime import datetime, timezone
import json
import math
from pathlib import Path

from utils.cloud_storage import load_cloud_json, save_cloud_json
from utils.symbols import normalize_legacy_symbol, normalize_symbol


PORTFOLIO_FILE = Path(__file__).resolve().parents[1] / "data" / "paper_portfolio.json"
STARTING_CASH = 10_000.0


def calculate_position_size(
    portfolio_value,
    available_cash,
    price,
    stop_loss_percent,
    risk_percent=1.0,
    maximum_position_percent=20.0,
    existing_position_value=0.0,
):
    """Calculate shares using account risk, cash, and allocation limits."""
    portfolio_value = float(portfolio_value)
    available_cash = float(available_cash)
    price = float(price)
    stop_loss_percent = float(stop_loss_percent)
    risk_percent = float(risk_percent)
    maximum_position_percent = float(maximum_position_percent)

    if portfolio_value <= 0 or available_cash < 0 or price <= 0:
        raise ValueError("Portfolio value, cash, and price must be valid.")
    if stop_loss_percent <= 0 or risk_percent <= 0:
        raise ValueError("Risk and stop-loss percentages must be greater than zero.")

    risk_budget = portfolio_value * (risk_percent / 100)
    risk_per_share = price * (stop_loss_percent / 100)
    shares_by_risk = math.floor(risk_budget / risk_per_share)
    shares_by_cash = math.floor(available_cash / price)

    maximum_position_value = portfolio_value * (
        maximum_position_percent / 100
    )
    remaining_allocation = max(
        0.0,
        maximum_position_value - float(existing_position_value),
    )
    shares_by_allocation = math.floor(remaining_allocation / price)
    suggested_shares = max(
        0,
        min(shares_by_risk, shares_by_cash, shares_by_allocation),
    )

    return {
        "suggested_shares": suggested_shares,
        "risk_budget": round(risk_budget, 2),
        "risk_per_share": round(risk_per_share, 2),
        "stop_loss_price": round(price - risk_per_share, 2),
        "estimated_cost": round(suggested_shares * price, 2),
        "maximum_position_value": round(maximum_position_value, 2),
    }


def new_portfolio():
    """Return a new, empty simulated portfolio."""
    return {
        "starting_cash": STARTING_CASH,
        "cash": STARTING_CASH,
        "positions": {},
        "transactions": [],
        "equity_history": [],
    }


def load_portfolio():
    """Load the saved portfolio or create a clean one when none exists."""
    portfolio = load_cloud_json("paper_portfolio", new_portfolio())
    if portfolio is None:
        if not PORTFOLIO_FILE.exists():
            return new_portfolio()
        try:
            portfolio = json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return new_portfolio()

    required_keys = {"starting_cash", "cash", "positions", "transactions"}
    if not isinstance(portfolio, dict) or not required_keys.issubset(portfolio):
        return new_portfolio()
    if not isinstance(portfolio["positions"], dict):
        return new_portfolio()
    if not isinstance(portfolio["transactions"], list):
        return new_portfolio()

    # Add fields introduced in newer versions without resetting old portfolios.
    portfolio.setdefault("equity_history", [])
    normalized_positions = {}
    for raw_symbol, position in portfolio["positions"].items():
        if not isinstance(position, dict):
            continue
        try:
            symbol = normalize_legacy_symbol(raw_symbol)
            shares = int(position.get("shares", 0))
            average_cost = float(position.get("average_cost", 0.0))
        except (TypeError, ValueError):
            continue
        if shares <= 0 or average_cost < 0:
            continue
        if symbol in normalized_positions:
            existing = normalized_positions[symbol]
            total_shares = int(existing["shares"]) + shares
            total_cost = (
                float(existing["average_cost"]) * int(existing["shares"])
                + average_cost * shares
            )
            existing["shares"] = total_shares
            existing["average_cost"] = (
                round(total_cost / total_shares, 4) if total_shares else 0.0
            )
        else:
            normalized_positions[symbol] = {
                "shares": shares,
                "average_cost": average_cost,
            }
    portfolio["positions"] = normalized_positions

    for transaction in portfolio["transactions"]:
        if isinstance(transaction, dict) and "symbol" in transaction:
            try:
                transaction["symbol"] = normalize_legacy_symbol(
                    transaction["symbol"]
                )
            except ValueError:
                pass
    return portfolio


def save_portfolio(portfolio):
    """Save portfolio state atomically and return it."""
    PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = PORTFOLIO_FILE.with_suffix(".tmp")
    temporary_file.write_text(
        json.dumps(portfolio, indent=2),
        encoding="utf-8",
    )
    temporary_file.replace(PORTFOLIO_FILE)
    save_cloud_json("paper_portfolio", portfolio)
    return portfolio


def record_equity_snapshot(portfolio_value, cash, market_value):
    """Create or update today's persistent portfolio-value snapshot."""
    portfolio = load_portfolio()
    snapshot = {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "portfolio_value": round(float(portfolio_value), 2),
        "cash": round(float(cash), 2),
        "market_value": round(float(market_value), 2),
    }

    history = portfolio.setdefault("equity_history", [])
    if history and history[-1].get("date") == snapshot["date"]:
        history[-1] = snapshot
    else:
        history.append(snapshot)

    save_portfolio(portfolio)
    return snapshot


def buy_shares(symbol, shares, price):
    """Execute a simulated buy at the supplied market price."""
    clean_symbol = normalize_symbol(symbol)
    shares = int(shares)
    price = float(price)

    if shares <= 0:
        raise ValueError("Share quantity must be greater than zero.")
    if price <= 0:
        raise ValueError("A valid market price is required.")

    portfolio = load_portfolio()
    total_cost = round(shares * price, 2)
    if total_cost > portfolio["cash"]:
        raise ValueError(
            f"Insufficient cash. This order costs ${total_cost:,.2f}, "
            f"but only ${portfolio['cash']:,.2f} is available."
        )

    position = portfolio["positions"].get(
        clean_symbol,
        {"shares": 0, "average_cost": 0.0},
    )
    old_shares = int(position["shares"])
    new_shares = old_shares + shares
    weighted_cost = (
        old_shares * float(position["average_cost"]) + shares * price
    ) / new_shares

    portfolio["positions"][clean_symbol] = {
        "shares": new_shares,
        "average_cost": round(weighted_cost, 4),
    }
    portfolio["cash"] = round(portfolio["cash"] - total_cost, 2)
    portfolio["transactions"].append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "side": "BUY",
            "symbol": clean_symbol,
            "shares": shares,
            "price": round(price, 2),
            "total": total_cost,
            "realized_profit": 0.0,
        }
    )
    return save_portfolio(portfolio)


def sell_shares(symbol, shares, price):
    """Execute a simulated sale and record realized profit or loss."""
    clean_symbol = normalize_symbol(symbol)
    shares = int(shares)
    price = float(price)
    portfolio = load_portfolio()
    position = portfolio["positions"].get(clean_symbol)

    if shares <= 0:
        raise ValueError("Share quantity must be greater than zero.")
    if price <= 0:
        raise ValueError("A valid market price is required.")
    if position is None or int(position["shares"]) < shares:
        owned = int(position["shares"]) if position else 0
        raise ValueError(f"Cannot sell {shares} shares; only {owned} are owned.")

    proceeds = round(shares * price, 2)
    average_cost = float(position["average_cost"])
    realized_profit = round((price - average_cost) * shares, 2)
    remaining_shares = int(position["shares"]) - shares

    if remaining_shares == 0:
        del portfolio["positions"][clean_symbol]
    else:
        position["shares"] = remaining_shares

    portfolio["cash"] = round(portfolio["cash"] + proceeds, 2)
    portfolio["transactions"].append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "side": "SELL",
            "symbol": clean_symbol,
            "shares": shares,
            "price": round(price, 2),
            "total": proceeds,
            "realized_profit": realized_profit,
        }
    )
    return save_portfolio(portfolio)
