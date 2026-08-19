import json
import unittest
from unittest.mock import patch

from data.news_data import (
    NewsDataError,
    get_stock_news,
    normalize_news_response,
    summarize_sentiment,
)


PAYLOAD = {
    "status": "OK",
    "results": [
        {
            "id": "one",
            "title": "Apple launches a new product",
            "description": "A product announcement.",
            "article_url": "https://example.com/apple",
            "published_utc": "2026-08-18T12:00:00Z",
            "publisher": {"name": "Example News"},
            "tickers": ["AAPL"],
            "insights": [
                {
                    "ticker": "AAPL",
                    "sentiment": "positive",
                    "sentiment_reasoning": "The launch may support growth.",
                }
            ],
        },
        {
            "id": "two",
            "title": "Supply questions remain",
            "article_url": "https://example.com/supply",
            "published_utc": "2026-08-18T11:00:00Z",
            "publisher": {"name": "Example News"},
            "tickers": ["AAPL"],
            "insights": [
                {"ticker": "AAPL", "sentiment": "negative"}
            ],
        },
    ],
}


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(PAYLOAD).encode("utf-8")


class NewsDataTests(unittest.TestCase):
    def setUp(self):
        get_stock_news.clear()

    def test_normalizes_articles_and_ticker_sentiment(self):
        articles = normalize_news_response(PAYLOAD, " aapl ")

        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0]["sentiment"], "positive")
        self.assertEqual(articles[1]["sentiment"], "negative")
        self.assertEqual(articles[0]["publisher"], "Example News")

    def test_discards_articles_without_safe_link(self):
        payload = {
            "status": "OK",
            "results": [{"title": "Unsafe", "article_url": "javascript:alert(1)"}],
        }
        self.assertEqual(normalize_news_response(payload, "AAPL"), [])

    def test_summarizes_sentiment_transparently(self):
        articles = normalize_news_response(PAYLOAD, "AAPL")
        summary = summarize_sentiment(articles)

        self.assertEqual(summary["label"], "Neutral")
        self.assertEqual(summary["score"], 0.0)
        self.assertEqual(summary["positive"], 1)
        self.assertEqual(summary["negative"], 1)
        self.assertTrue(summary["risks"])

    @patch("data.news_data.urlopen", return_value=FakeResponse())
    def test_fetches_massive_news_with_normalized_symbol(self, urlopen):
        articles = get_stock_news(" aapl ", limit=10, _api_key="test-key")

        self.assertEqual(len(articles), 2)
        request = urlopen.call_args.args[0]
        self.assertIn("ticker=AAPL", request.full_url)
        self.assertIn("apiKey=test-key", request.full_url)

    def test_requires_api_key(self):
        with self.assertRaisesRegex(NewsDataError, "API key"):
            get_stock_news("AAPL", _api_key="")


if __name__ == "__main__":
    unittest.main()
