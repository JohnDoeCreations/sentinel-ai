from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from utils.bulk_scanner import load_bulk_scan_state, scan_next_batch


class BulkScannerTests(unittest.TestCase):
    def test_batches_wrap_and_merge_results(self):
        def analyzer(symbol):
            if symbol == "MSFT":
                raise RuntimeError("temporary failure")
            return {"Symbol": symbol, "Score": 3, "Daily Change (%)": 1.0}

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.json"
            with patch("utils.bulk_scanner.RESULTS_FILE", path):
                first = scan_next_batch(
                    analyzer, batch_size=2, symbols=["AAPL", "MSFT", "NVDA"]
                )
                second = scan_next_batch(
                    analyzer, batch_size=2, symbols=["AAPL", "MSFT", "NVDA"]
                )
                state = load_bulk_scan_state()

        self.assertEqual(first["batch"], ["AAPL", "MSFT"])
        self.assertEqual(second["batch"], ["NVDA", "AAPL"])
        self.assertEqual(set(state["results"]), {"AAPL", "NVDA"})
        self.assertEqual(state["errors"]["MSFT"], "temporary failure")
        self.assertEqual(state["cursor"], 1)

    def test_removes_results_outside_current_universe(self):
        def analyzer(symbol):
            return {"Symbol": symbol, "Score": 2, "Daily Change (%)": 0.0}

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.json"
            with patch("utils.bulk_scanner.RESULTS_FILE", path):
                scan_next_batch(analyzer, batch_size=2, symbols=["AAPL", "MSFT"])
                scan_next_batch(analyzer, batch_size=1, symbols=["NVDA"])
                state = load_bulk_scan_state()

        self.assertEqual(set(state["results"]), {"NVDA"})


if __name__ == "__main__":
    unittest.main()
