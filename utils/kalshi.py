"""Public Kalshi market data and a local paper-contract portfolio."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path

import requests
import truststore


truststore.inject_into_ssl()

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
PAPER_PORTFOLIO_FILE = (
    Path(__file__).resolve().parents[1] / "data" / "kalshi_paper_portfolio.json"
)
PAPER_STARTING_CASH = 1_000.0
CRYPTO_15M_SERIES = {
    "BTC": "KXBTC15M",
    "ETH": "KXETH15M",
    "SOL": "KXSOL15M",
    "XRP": "KXXRP15M",
    "DOGE": "KXDOGE15M",
    "BNB": "KXBNB15M",
    "HYPE": "KXHYPE15M",
}


class KalshiDataError(RuntimeError):
    """Raised when Kalshi public market data cannot be loaded."""


def _decimal(value, default=0.0):
    """Convert Kalshi fixed-point strings to floats safely."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _fetch_series(asset, series_ticker, timeout):
    response = requests.get(
        f"{BASE_URL}/markets",
        params={
            "series_ticker": series_ticker,
            "status": "open",
            "limit": 100,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return asset, response.json().get("markets", [])


def fetch_crypto_15m_markets(assets=None, timeout=8):
    """Return normalized active 15-minute crypto contracts from Kalshi."""
    requested_assets = [
        str(asset).strip().upper()
        for asset in (assets or CRYPTO_15M_SERIES)
        if str(asset).strip().upper() in CRYPTO_15M_SERIES
    ]
    if not requested_assets:
        return []

    raw_markets = []
    failures = []
    workers = min(6, len(requested_assets))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _fetch_series,
                asset,
                CRYPTO_15M_SERIES[asset],
                timeout,
            ): asset
            for asset in requested_assets
        }
        for future in as_completed(futures):
            try:
                asset, markets = future.result()
            except (requests.RequestException, ValueError, TypeError) as error:
                failures.append(f"{futures[future]}: {error}")
                continue
            raw_markets.extend((asset, market) for market in markets)

    if not raw_markets and failures:
        raise KalshiDataError(
            "Kalshi market data is temporarily unavailable. Please try again."
        )

    normalized = []
    for asset, market in raw_markets:
        yes_bid = _decimal(market.get("yes_bid_dollars"))
        yes_ask = _decimal(market.get("yes_ask_dollars"))
        no_bid = _decimal(market.get("no_bid_dollars"))
        no_ask = _decimal(market.get("no_ask_dollars"))
        midpoint = (
            (yes_bid + yes_ask) / 2
            if yes_bid > 0 and yes_ask > 0
            else _decimal(market.get("last_price_dollars"))
        )
        normalized.append(
            {
                "asset": asset,
                "ticker": str(market.get("ticker", "")),
                "title": str(market.get("title", "")),
                "yes_bid": yes_bid,
                "yes_ask": yes_ask,
                "no_bid": no_bid,
                "no_ask": no_ask,
                "last_price": _decimal(market.get("last_price_dollars")),
                "market_probability": midpoint,
                "spread": max(0.0, yes_ask - yes_bid),
                "volume": _decimal(market.get("volume_fp")),
                "volume_24h": _decimal(market.get("volume_24h_fp")),
                "liquidity": _decimal(market.get("liquidity_dollars")),
                "close_time": market.get("close_time"),
                "status": str(market.get("status", "")),
                "rules_primary": str(market.get("rules_primary", "")),
            }
        )
    return sorted(normalized, key=lambda item: item["close_time"] or "")


def fetch_market_result(ticker, timeout=8):
    """Return the current status and binary result for one public market."""
    try:
        response = requests.get(
            f"{BASE_URL}/markets/{str(ticker).strip().upper()}",
            timeout=timeout,
        )
        response.raise_for_status()
        market = response.json()["market"]
    except (requests.RequestException, KeyError, TypeError, ValueError) as error:
        raise KalshiDataError("Kalshi could not update this market result.") from error
    result = str(market.get("result", "")).strip().lower()
    return {
        "ticker": str(market.get("ticker", ticker)),
        "status": str(market.get("status", "")),
        "result": result if result in {"yes", "no"} else None,
    }


def new_kalshi_paper_portfolio():
    """Return a clean simulated prediction-market portfolio."""
    return {
        "starting_cash": PAPER_STARTING_CASH,
        "cash": PAPER_STARTING_CASH,
        "positions": {},
        "transactions": [],
    }


def load_kalshi_paper_portfolio():
    """Load the local paper portfolio, falling back safely if malformed."""
    if not PAPER_PORTFOLIO_FILE.exists():
        return new_kalshi_paper_portfolio()
    try:
        portfolio = json.loads(PAPER_PORTFOLIO_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return new_kalshi_paper_portfolio()
    required = {"starting_cash", "cash", "positions", "transactions"}
    if not isinstance(portfolio, dict) or not required.issubset(portfolio):
        return new_kalshi_paper_portfolio()
    if not isinstance(portfolio["positions"], dict):
        return new_kalshi_paper_portfolio()
    if not isinstance(portfolio["transactions"], list):
        return new_kalshi_paper_portfolio()
    return portfolio


def _save_kalshi_paper_portfolio(portfolio):
    PAPER_PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = PAPER_PORTFOLIO_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(portfolio, indent=2), encoding="utf-8")
    temporary.replace(PAPER_PORTFOLIO_FILE)
    return portfolio


def buy_paper_contract(ticker, title, asset, side, contracts, price, close_time=None):
    """Buy YES or NO contracts in the simulated Kalshi portfolio."""
    clean_ticker = str(ticker).strip().upper()
    clean_side = str(side).strip().upper()
    contracts = int(contracts)
    price = float(price)
    if not clean_ticker:
        raise ValueError("A market ticker is required.")
    if clean_side not in {"YES", "NO"}:
        raise ValueError("Contract side must be YES or NO.")
    if contracts <= 0:
        raise ValueError("Contract quantity must be greater than zero.")
    if not 0 < price < 1:
        raise ValueError("Contract price must be between $0 and $1.")

    portfolio = load_kalshi_paper_portfolio()
    total_cost = round(contracts * price, 4)
    if total_cost > float(portfolio["cash"]):
        raise ValueError("Insufficient simulated cash for this order.")

    position_key = f"{clean_ticker}:{clean_side}"
    position = portfolio["positions"].get(
        position_key,
        {
            "ticker": clean_ticker,
            "title": str(title),
            "asset": str(asset).upper(),
            "side": clean_side,
            "contracts": 0,
            "average_cost": 0.0,
            "close_time": close_time,
        },
    )
    old_contracts = int(position["contracts"])
    new_contracts = old_contracts + contracts
    average_cost = (
        old_contracts * float(position["average_cost"]) + contracts * price
    ) / new_contracts
    position["contracts"] = new_contracts
    position["average_cost"] = round(average_cost, 4)
    portfolio["positions"][position_key] = position
    portfolio["cash"] = round(float(portfolio["cash"]) - total_cost, 4)
    portfolio["transactions"].append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "action": "BUY",
            "ticker": clean_ticker,
            "side": clean_side,
            "contracts": contracts,
            "price": round(price, 4),
            "total": total_cost,
        }
    )
    return _save_kalshi_paper_portfolio(portfolio)


def close_paper_contract(position_key, contracts, price):
    """Close simulated contracts at the supplied current bid."""
    contracts = int(contracts)
    price = float(price)
    portfolio = load_kalshi_paper_portfolio()
    position = portfolio["positions"].get(position_key)
    owned = int(position["contracts"]) if position else 0
    if contracts <= 0:
        raise ValueError("Contract quantity must be greater than zero.")
    if position is None or contracts > owned:
        raise ValueError(f"Cannot close {contracts} contracts; only {owned} are owned.")
    if not 0 <= price <= 1:
        raise ValueError("Contract price must be between $0 and $1.")

    proceeds = round(contracts * price, 4)
    realized_profit = round(
        (price - float(position["average_cost"])) * contracts,
        4,
    )
    remaining = owned - contracts
    if remaining:
        position["contracts"] = remaining
    else:
        del portfolio["positions"][position_key]
    portfolio["cash"] = round(float(portfolio["cash"]) + proceeds, 4)
    portfolio["transactions"].append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "action": "CLOSE",
            "ticker": position["ticker"],
            "side": position["side"],
            "contracts": contracts,
            "price": round(price, 4),
            "total": proceeds,
            "realized_profit": realized_profit,
        }
    )
    return _save_kalshi_paper_portfolio(portfolio)
