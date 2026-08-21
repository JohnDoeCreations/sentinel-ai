"""Automatic paper-forecast collection for active Kalshi crypto contracts."""

from datetime import datetime, timezone

from data.crypto_data import CryptoDataError, get_crypto_minute_bars
from utils.kalshi import (
    KalshiDataError,
    buy_paper_contract,
    fetch_crypto_15m_markets,
    fetch_market_result,
    load_kalshi_paper_portfolio,
    settle_paper_contract,
)
from utils.kalshi_auto_trade import load_auto_trade_settings, size_paper_order
from utils.kalshi_forecast import estimate_direction_probability, forecast_decision
from utils.kalshi_journal import (
    load_forecast_journal,
    record_forecast,
    update_forecast_results,
)


DEFAULT_ASSETS = ("BTC", "ETH", "SOL")


def collect_forecast_cycle(api_key, assets=DEFAULT_ASSETS, now=None, auto_settings=None):
    """Record eligible forecasts and settle finished entries in one safe cycle."""
    now = now or datetime.now(timezone.utc)
    report = {
        "markets": 0, "recorded": 0, "paper_trades": 0,
        "paper_positions_settled": 0, "settled": 0, "skipped": 0, "errors": [],
    }
    auto_settings = auto_settings or load_auto_trade_settings()
    existing = {str(row["ticker"]).upper() for row in load_forecast_journal()}
    try:
        markets = fetch_crypto_15m_markets(assets)
    except KalshiDataError as error:
        report["errors"].append(str(error))
        markets = []
    report["markets"] = len(markets)
    bars_by_asset = {}
    for market in markets:
        ticker = market["ticker"].upper()
        close_at = datetime.fromisoformat(str(market["close_time"]).replace("Z", "+00:00"))
        minutes_remaining = (close_at - now).total_seconds() / 60
        if ticker in existing or not 1 <= minutes_remaining <= 10:
            report["skipped"] += 1
            continue
        asset = market["asset"]
        try:
            if asset not in bars_by_asset:
                bars_by_asset[asset] = get_crypto_minute_bars(asset, api_key)
            forecast = estimate_direction_probability(
                bars_by_asset[asset], market["close_time"], now=now
            )
            decision = forecast_decision(
                forecast["probability_yes"], market["yes_ask"], market["no_ask"]
            )
            record_forecast(
                {
                    **market,
                    **forecast,
                    "decision": decision["decision"],
                    "estimated_edge": decision["edge"],
                }
            )
            existing.add(ticker)
            report["recorded"] += 1
            if auto_settings["enabled"] and decision["decision"] in {"PAPER YES", "PAPER NO"}:
                side = decision["decision"].removeprefix("PAPER ")
                ask_price = market["yes_ask"] if side == "YES" else market["no_ask"]
                portfolio = load_kalshi_paper_portfolio()
                already_open = any(
                    str(position.get("ticker", "")).upper() == ticker
                    for position in portfolio.get("positions", {}).values()
                )
                quantity = size_paper_order(portfolio, ask_price, auto_settings)
                if (
                    not already_open
                    and decision["edge"] >= auto_settings["minimum_edge"]
                    and quantity > 0
                ):
                    buy_paper_contract(
                        ticker, market["title"], market["asset"], side,
                        quantity, ask_price, market["close_time"],
                    )
                    report["paper_trades"] += 1
        except (CryptoDataError, ValueError) as error:
            report["errors"].append(f"{ticker}: {error}")

    results = {}
    for row in load_forecast_journal():
        if row.get("result") is not None:
            continue
        try:
            market_result = fetch_market_result(row["ticker"])
        except KalshiDataError as error:
            report["errors"].append(f'{row["ticker"]}: {error}')
            continue
        if market_result["result"]:
            results[row["ticker"]] = market_result["result"]
            report["paper_positions_settled"] += settle_paper_contract(
                row["ticker"], market_result["result"]
            )
    report["settled"] = update_forecast_results(results)
    return report
