"""Check stock-split alignment of price, SEC shares, and turnover inputs."""

import importlib.util
from pathlib import Path
import unittest

import pandas as pd


SOURCE = Path(__file__).resolve().parents[1] / "src" / "build_controls.py"
SPEC = importlib.util.spec_from_file_location("build_controls_test", SOURCE)
assert SPEC is not None and SPEC.loader is not None
CONTROLS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLS)


class StockSplitTests(unittest.TestCase):
    def test_only_splits_after_sec_share_date_change_basis(self) -> None:
        splits = pd.DataFrame({
            "ticker": ["AAPL", "AAPL", "OTHER"],
            "date": pd.to_datetime(["2014-06-09", "2020-08-31", "2020-08-31"]),
            "ratio": [7.0, 4.0, 2.0],
        })
        last_price_date = pd.Timestamp("2026-01-14")
        self.assertEqual(CONTROLS.split_factor(splits, "AAPL", "2019-10-18", last_price_date), 4.0)
        self.assertEqual(CONTROLS.split_factor(splits, "AAPL", "2020-10-16", last_price_date), 1.0)


if __name__ == "__main__":
    unittest.main()
