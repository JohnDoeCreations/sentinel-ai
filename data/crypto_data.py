"""Massive one-minute cryptocurrency market data."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import requests
import truststore
import yfinance as yf


truststore.inject_into_ssl()
_YFINANCE_CRYPTO_CACHE = Path(__file__).resolve().parents[1] / ".cache" / "yfinance"
_YFINANCE_CRYPTO_CACHE.mkdir(parents=True, exist_ok=True)
yf.set_tz_cache_location(str(_YFINANCE_CRYPTO_CACHE))


MASSIVE_AGGREGATES_URL = "https://api.massive.com/v2/aggs/ticker"


class CryptoDataError(RuntimeError):
    """Raised when minute-level crypto data cannot be loaded."""


def _get_yahoo_crypto_minute_bars(asset):
    """Return recent minute bars from Yahoo when Massive plan access is absent."""
    try:
        frame = yf.download(
            f"{asset}-USD",
            period="1d",
            interval="1m",
            progress=False,
            auto_adjust=True,
            multi_level_index=False,
        )
    except Exception:
        frame = pd.DataFrame()
    if frame.empty:
        try:
            response = requests.get(
                f"https://query2.finance.yahoo.com/v8/finance/chart/{asset}-USD",
                params={"range": "1d", "interval": "1m"},
                headers={"User-Agent": "Mozilla/5.0 Sentinel-AI"},
                timeout=15,
            )
            response.raise_for_status()
            result = response.json()["chart"]["result"][0]
            quote = result["indicators"]["quote"][0]
            frame = pd.DataFrame(
                {
                    "Time": pd.to_datetime(result["timestamp"], unit="s", utc=True),
                    "Open": quote.get("open", []),
                    "High": quote.get("high", []),
                    "Low": quote.get("low", []),
                    "Close": quote.get("close", []),
                    "Volume": quote.get("volume", []),
                }
            )
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
            frame = pd.DataFrame()
    if frame.empty or "Close" not in frame.columns:
        raise CryptoDataError(f"No recent fallback minute bars were returned for {asset}.")
    if "Time" not in frame.columns:
        frame = frame.reset_index()
        time_column = "Datetime" if "Datetime" in frame.columns else frame.columns[0]
        frame = frame.rename(columns={time_column: "Time"})
    frame["Time"] = pd.to_datetime(frame["Time"], utc=True)
    frame.attrs["provider"] = "Yahoo Finance fallback"
    return frame.sort_values("Time").reset_index(drop=True)


def get_crypto_minute_bars(asset, _api_key, lookback_minutes=180):
    """Return recent one-minute USD aggregate bars from Massive."""
    asset = str(asset).strip().upper()
    api_key = str(_api_key or "").strip()
    if not asset or not api_key:
        raise CryptoDataError("A crypto asset and Massive API key are required.")
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=int(lookback_minutes))
    ticker = f"X:{asset}USD"
    query = urlencode(
        {"adjusted": "true", "sort": "asc", "limit": 5000, "apiKey": api_key}
    )
    url = (
        f"{MASSIVE_AGGREGATES_URL}/{ticker}/range/1/minute/"
        f"{int(start.timestamp() * 1000)}/{int(end.timestamp() * 1000)}?{query}"
    )
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Sentinel-AI/1.0"})
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code in {401, 403, 429}:
            return _get_yahoo_crypto_minute_bars(asset)
        raise CryptoDataError(f"Massive crypto data returned HTTP {error.code}.") from error
    except (URLError, TimeoutError, json.JSONDecodeError):
        return _get_yahoo_crypto_minute_bars(asset)

    rows = payload.get("results") or []
    frame = pd.DataFrame(rows)
    if frame.empty or not {"t", "c"}.issubset(frame.columns):
        raise CryptoDataError(f"No recent minute bars were returned for {asset}.")
    frame = frame.rename(columns={"t": "Time", "o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
    frame["Time"] = pd.to_datetime(frame["Time"], unit="ms", utc=True)
    frame.attrs["provider"] = "Massive"
    return frame.sort_values("Time").reset_index(drop=True)
