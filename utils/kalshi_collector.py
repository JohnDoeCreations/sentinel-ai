"""Automatic paper-forecast collection for active Kalshi crypto contracts."""

from datetime import datetime, timezone

from data.crypto_data import CryptoDataError, get_crypto_minute_bars
from utils.kalshi import (
    KalshiDataError,
    fetch_crypto_15m_markets,
    fetch_market_result,
)
from utils.kalshi_forecast import estimate_direction_probability, forecast_decision
from utils.kalshi_journal import (
    load_forecast_journal,
    record_forecast,
    update_forecast_results,
)


DEFAULT_ASSETS = ("BTC", "ETH", "SOL")


def collect_forecast_cycle(api_key, assets=DEFAULT_ASSETS, now=None):
    """Record eligible forecasts and settle finished entries in one safe cycle."""
    now = now or datetime.now(timezone.utc)
    report = {"markets": 0, "recorded": 0, "settled": 0, "skipped": 0, "errors": []}
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
    report["settled"] = update_forecast_results(results)
    return report
