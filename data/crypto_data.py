"""Massive one-minute cryptocurrency market data."""

from datetime import datetime, timedelta, timezone
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


MASSIVE_AGGREGATES_URL = "https://api.massive.com/v2/aggs/ticker"


class CryptoDataError(RuntimeError):
    """Raised when minute-level crypto data cannot be loaded."""


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
        message = (
            "Massive rejected the API key or plan access."
            if error.code in {401, 403}
            else f"Massive crypto data returned HTTP {error.code}."
        )
        raise CryptoDataError(message) from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise CryptoDataError("Massive crypto data is temporarily unavailable.") from error

    rows = payload.get("results") or []
    frame = pd.DataFrame(rows)
    if frame.empty or not {"t", "c"}.issubset(frame.columns):
        raise CryptoDataError(f"No recent minute bars were returned for {asset}.")
    frame = frame.rename(columns={"t": "Time", "o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
    frame["Time"] = pd.to_datetime(frame["Time"], unit="ms", utc=True)
    return frame.sort_values("Time").reset_index(drop=True)
