"""Massive market-news access and normalized sentiment data."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import streamlit as st

from utils.symbols import normalize_symbol


MASSIVE_NEWS_URL = "https://api.massive.com/v2/reference/news"
SENTIMENT_SCORES = {"positive": 1, "neutral": 0, "negative": -1}


class NewsDataError(RuntimeError):
    """Raised when Massive news cannot be loaded safely."""


def _safe_url(value):
    """Return an HTTP(S) URL or an empty string."""
    candidate = str(value or "").strip()
    parsed = urlparse(candidate)
    return candidate if parsed.scheme in {"http", "https"} else ""


def _article_sentiment(article, symbol):
    """Extract the requested ticker's sentiment and reasoning."""
    insights = article.get("insights") or []
    matching = [
        insight
        for insight in insights
        if str(insight.get("ticker", "")).upper() == symbol
    ]
    selected = matching[0] if matching else {}
    sentiment = str(selected.get("sentiment", "neutral")).lower()
    if sentiment not in SENTIMENT_SCORES:
        sentiment = "neutral"
    reasoning = str(selected.get("sentiment_reasoning", "")).strip()
    return sentiment, reasoning


def normalize_news_response(payload, symbol):
    """Normalize Massive's response into stable, display-safe fields."""
    clean_symbol = normalize_symbol(symbol)
    if not isinstance(payload, dict):
        raise NewsDataError("Massive returned an unexpected response.")
    if payload.get("status") not in {None, "OK"}:
        raise NewsDataError("Massive could not complete the news request.")

    articles = []
    for raw_article in payload.get("results") or []:
        if not isinstance(raw_article, dict):
            continue
        title = str(raw_article.get("title", "")).strip()
        article_url = _safe_url(raw_article.get("article_url"))
        if not title or not article_url:
            continue

        sentiment, reasoning = _article_sentiment(raw_article, clean_symbol)
        publisher = raw_article.get("publisher") or {}
        articles.append(
            {
                "id": str(raw_article.get("id", "")),
                "title": title,
                "description": str(raw_article.get("description", "")).strip(),
                "article_url": article_url,
                "image_url": _safe_url(raw_article.get("image_url")),
                "author": str(raw_article.get("author", "")).strip(),
                "published_utc": str(raw_article.get("published_utc", "")).strip(),
                "publisher": str(publisher.get("name", "Unknown source")).strip(),
                "publisher_url": _safe_url(publisher.get("homepage_url")),
                "tickers": [
                    str(ticker).upper()
                    for ticker in raw_article.get("tickers") or []
                ],
                "sentiment": sentiment,
                "sentiment_score": SENTIMENT_SCORES[sentiment],
                "sentiment_reasoning": reasoning,
                "keywords": [
                    str(keyword)
                    for keyword in raw_article.get("keywords") or []
                ],
            }
        )
    return articles


@st.cache_data(ttl="1h", max_entries=50, show_spinner=False)
def get_stock_news(symbol, limit=20, _api_key=None):
    """Return recent ticker news from Massive, cached for one hour."""
    clean_symbol = normalize_symbol(symbol)
    limit = int(limit)
    if not 1 <= limit <= 100:
        raise ValueError("News limit must be between 1 and 100.")
    api_key = str(_api_key or "").strip()
    if not api_key:
        raise NewsDataError("A Massive API key is required.")

    query = urlencode(
        {
            "ticker": clean_symbol,
            "limit": limit,
            "sort": "published_utc",
            "order": "desc",
            "apiKey": api_key,
        }
    )
    request = Request(
        f"{MASSIVE_NEWS_URL}?{query}",
        headers={"Accept": "application/json", "User-Agent": "Sentinel-AI/1.0"},
    )

    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code in {401, 403}:
            message = "Massive rejected the API key. Check your key and plan access."
        elif error.code == 429:
            message = "Massive's request limit was reached. Try again shortly."
        else:
            message = f"Massive news returned HTTP {error.code}."
        raise NewsDataError(message) from error
    except (URLError, TimeoutError) as error:
        raise NewsDataError(
            "Massive news is temporarily unavailable. Check your connection and retry."
        ) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise NewsDataError("Massive returned unreadable news data.") from error

    return normalize_news_response(payload, clean_symbol)


def summarize_sentiment(articles):
    """Aggregate article sentiment into a transparent summary."""
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    for article in articles:
        sentiment = article.get("sentiment", "neutral")
        counts[sentiment if sentiment in counts else "neutral"] += 1

    total = sum(counts.values())
    score = (
        (counts["positive"] - counts["negative"]) / total
        if total
        else 0.0
    )
    if score >= 0.2:
        label = "Positive"
    elif score <= -0.2:
        label = "Negative"
    else:
        label = "Neutral"

    risks = []
    if counts["negative"] >= max(2, counts["positive"]):
        risks.append("Negative headlines are prominent in the current sample.")
    if total < 5:
        risks.append("The sample is small, so the sentiment signal is less reliable.")

    return {
        "label": label,
        "score": round(score, 2),
        "total": total,
        "positive": counts["positive"],
        "neutral": counts["neutral"],
        "negative": counts["negative"],
        "risks": risks,
    }


def clear_news_cache():
    """Force the next news request to load fresh data."""
    get_stock_news.clear()
