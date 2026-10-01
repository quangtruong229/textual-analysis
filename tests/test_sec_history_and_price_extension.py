"""Regression checks for SEC archive pagination and late C6 price sessions."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SEC = load_module("select_companies", ROOT / "src/select_companies.py")
PRICES = load_module("download_market_data", ROOT / "src/download_market_data.py")


class SecHistoryAndPriceExtensionTests(unittest.TestCase):
    def test_sec_history_includes_archived_filings_and_deduplicates(self):
        recent = {"filingDate": ["2025-10-30"], "reportDate": ["2025-09-30"],
                  "form": ["10-K"], "accessionNumber": ["recent"],
                  "primaryDocument": ["recent.htm"]}
        archived = {"filingDate": ["2017-10-30", "2025-10-30"],
                    "reportDate": ["2017-09-30", "2025-09-30"],
                    "form": ["10-K", "10-K"],
                    "accessionNumber": ["old", "recent"],
                    "primaryDocument": ["old.htm", "recent.htm"]}
        main = {"filings": {"recent": recent, "files": [
            {"name": "CIK0000000001-submissions-001.json",
             "filingFrom": "2016-01-01", "filingTo": "2025-12-31"},
            {"name": "CIK0000000001-submissions-002.json",
             "filingFrom": "2000-01-01", "filingTo": "2010-12-31"}]}}
        with patch.object(SEC, "get_json", side_effect=[main, archived]) as get_json:
            records = SEC.get_10k_filings("0000000001")
        self.assertEqual({r["accession_number"] for r in records}, {"old", "recent"})
        self.assertEqual(get_json.call_count, 2)

    def test_extension_preserves_old_prices_and_aligns_new_adjusted_close(self):
        old = pd.DataFrame({"ticker": ["F", "F"], "date": ["2026-01-14", "2026-01-15"],
                            "adj_close": [100.0, 102.0], "return": [0.01, 0.02]})
        new = pd.DataFrame({"ticker": ["F", "F", "F"],
                            "date": ["2026-01-14", "2026-01-15", "2026-01-16"],
                            "adj_close": [50.0, 51.0, 52.0]})
        result = PRICES.extend_prices(old, new)
        self.assertEqual(len(result), 3)
        self.assertEqual(result.iloc[1]["return"], 0.02)
        self.assertAlmostEqual(result.iloc[2]["adj_close"], 104.0)
        self.assertAlmostEqual(result.iloc[2]["return"], 104 / 102 - 1)


if __name__ == "__main__":
    unittest.main()
