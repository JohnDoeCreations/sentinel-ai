import unittest

from utils.symbols import (
    normalize_legacy_symbol,
    normalize_symbol,
    parse_symbol_list,
)


class SymbolValidationTests(unittest.TestCase):
    def test_normalizes_common_yahoo_symbols(self):
        self.assertEqual(normalize_symbol(" brk-b "), "BRK-B")
        self.assertEqual(normalize_symbol("^gspc"), "^GSPC")
        self.assertEqual(normalize_symbol("eurusd=x"), "EURUSD=X")

    def test_rejects_compound_or_punctuated_symbols(self):
        for value in ("AAPL, NVDA", "AAPL,", "AAPL NVDA", ""):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_symbol(value)

    def test_parses_unique_comma_separated_symbols(self):
        self.assertEqual(
            parse_symbol_list("aapl, NVDA, aapl"),
            ["AAPL", "NVDA"],
        )

    def test_repairs_legacy_trailing_comma(self):
        self.assertEqual(normalize_legacy_symbol("AAPL,"), "AAPL")


if __name__ == "__main__":
    unittest.main()
