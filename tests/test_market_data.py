import unittest
from unittest.mock import patch

import pandas as pd

from data.market_data import MarketDataError, _download_stock_data, get_stock_data


class MarketDataTests(unittest.TestCase):
    def setUp(self):
        _download_stock_data.clear()

    @patch("data.market_data.yf.download")
    def test_provider_failure_has_user_friendly_error(self, download):
        download.side_effect = TimeoutError("request timed out")

        with self.assertRaisesRegex(MarketDataError, "temporarily unavailable"):
            get_stock_data("AAPL")

    @patch("data.market_data._download_yahoo_chart", return_value=pd.DataFrame())
    @patch("data.market_data.yf.download", return_value=pd.DataFrame())
    def test_empty_provider_response_remains_empty(self, _download, fallback):
        self.assertTrue(get_stock_data("UNKNOWN").empty)
        fallback.assert_called_once_with("UNKNOWN", "3mo", "1d")

    def test_blank_symbol_is_rejected_before_download(self):
        with self.assertRaisesRegex(ValueError, "symbol is required"):
            get_stock_data("  ")


if __name__ == "__main__":
    unittest.main()
