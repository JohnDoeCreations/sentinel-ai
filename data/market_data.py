"""Shared market-data access for Sentinel AI."""

from pathlib import Path

import pandas as pd
import requests
import streamlit as st
import truststore
import yfinance as yf

from utils.symbols import normalize_symbol


# Keep yfinance's SQLite cache with the app.  Its Windows default can resolve to
# a protected or unavailable profile directory, which prevents price downloads.
_YFINANCE_CACHE = Path(__file__).resolve().parents[1] / ".cache" / "yfinance"
_YFINANCE_CACHE.mkdir(parents=True, exist_ok=True)
yf.set_tz_cache_location(str(_YFINANCE_CACHE))
truststore.inject_into_ssl()


def _download_yahoo_chart(symbol, period, interval):
    """Use Yahoo's chart API when yfinance's curl transport is unavailable."""
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
    try:
        response = requests.get(
            url,
            params={"range": period, "interval": interval},
            headers={"User-Agent": "Mozilla/5.0 Sentinel-AI"},
            timeout=15,
        )
        response.raise_for_status()
        result = response.json()["chart"]["result"][0]
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
        return pd.DataFrame()

    timestamps = result.get("timestamp") or []
    quotes = (result.get("indicators", {}).get("quote") or [{}])[0]
    if not timestamps or not quotes:
        return pd.DataFrame()

    data = pd.DataFrame(
        {
            "Open": quotes.get("open", []),
            "High": quotes.get("high", []),
            "Low": quotes.get("low", []),
            "Close": quotes.get("close", []),
            "Volume": quotes.get("volume", []),
        },
        index=pd.to_datetime(timestamps, unit="s", utc=True).tz_localize(None),
    )
    data.index.name = "Date"
    return data


class MarketDataError(RuntimeError):
    """Raised when the external market-data provider cannot be reached."""


@st.cache_data(ttl=300, show_spinner=False)
def _download_stock_data(symbol, period, interval):
    """Download normalized data and cache it for five minutes."""
    try:
        data = yf.download(
            symbol,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
            multi_level_index=False,
            timeout=15,
        )
    except Exception as error:
        raise MarketDataError(
            "Yahoo Finance is temporarily unavailable. Try refreshing in a moment."
        ) from error

    if data is None or data.empty:
        data = _download_yahoo_chart(symbol, period, interval)
    if data.empty:
        return pd.DataFrame()

    # Some yfinance versions still return a one-symbol MultiIndex.
    if isinstance(data.columns, pd.MultiIndex):
        if symbol in data.columns.get_level_values(-1):
            data = data.xs(symbol, axis=1, level=-1)
        else:
            data.columns = data.columns.get_level_values(0)

    return data.sort_index().dropna(how="all")


def get_stock_data(symbol, period="3mo", interval="1d"):
    """Return recent stock data, reusing downloads for five minutes."""
    clean_symbol = normalize_symbol(symbol)

    data = _download_stock_data(clean_symbol, period, interval).copy()

    # A few yfinance/Plotly combinations expose duplicate OHLC labels.
    # Keep the first occurrence so selecting data["Close"] returns a Series.
    if data.columns.duplicated().any():
        data = data.loc[:, ~data.columns.duplicated()].copy()

    return data


def clear_market_data_cache():
    """Force the next request to download fresh market data."""
    _download_stock_data.clear()
