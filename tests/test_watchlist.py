import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from utils.watchlist import add_symbol, load_watchlist, remove_symbols


class WatchlistTests(unittest.TestCase):
    def test_add_duplicate_and_remove_symbols(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "watchlist.json"
            with patch("utils.watchlist.WATCHLIST_FILE", path):
                self.assertTrue(add_symbol(" aapl "))
                self.assertFalse(add_symbol("AAPL"))
                self.assertTrue(add_symbol("NVDA"))
                self.assertEqual(load_watchlist(), ["AAPL", "NVDA"])
                self.assertEqual(remove_symbols(["AAPL"]), ["NVDA"])
                self.assertEqual(json.loads(path.read_text()), ["NVDA"])

    def test_invalid_json_returns_empty_watchlist(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "watchlist.json"
            path.write_text("not json", encoding="utf-8")
            with patch("utils.watchlist.WATCHLIST_FILE", path):
                self.assertEqual(load_watchlist(), [])


if __name__ == "__main__":
    unittest.main()
