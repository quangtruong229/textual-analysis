"""Check source alignment and quality gating for supplied six-control inputs."""

import importlib.util
from pathlib import Path
import sys
import unittest

import pandas as pd


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("full_controls", SCRIPTS / "calculate_full_controls.py")
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FullControlsTests(unittest.TestCase):
    def fixtures(self):
        panel = pd.DataFrame({"ticker": ["A", "B"],
                              "filing_date": ["2025-02-01", "2025-03-01"],
                              "accession_number": ["0001", "0002"],
                              "report_date": ["2024-12-31", "2024-12-31"]})
        earnings = pd.DataFrame({"ticker": ["A", "B"],
                                 "tenk_filing_date": ["2025-02-01", "2025-03-01"],
                                 "tenk_accession": ["0001", "0002"],
                                 "status": ["success", "success"],
                                 "eadret": [.03, -.01],
                                 "stock_return": [.05, .01],
                                 "market_return": [.02, .02],
                                 "tenk_acceptance_datetime_utc": ["2025-02-01T18:00:00Z",
                                                                   "2025-03-01T18:00:00Z"],
                                 "acceptance_datetime_utc": ["2025-01-20T18:00:00Z",
                                                             "2025-02-20T18:00:00Z"]})
        accruals = pd.DataFrame({"ticker": ["A", "B"],
                                 "filing_date": ["2025-02-01", "2025-03-01"],
                                 "report_date": ["2024-12-31", "2024-12-31"],
                                 "status": ["PASS", "WARN"],
                                 "accruals": [.2, .3],
                                 "accruals_numerator": [20, 30],
                                 "average_total_assets": [100, 100]})
        return panel, earnings, accruals

    def test_warn_accrual_is_excluded_even_if_numeric(self):
        validated, qa = MODULE.load_controls(*self.fixtures())
        self.assertEqual(qa["eadret_success"], 2)
        self.assertEqual(qa["accruals_pass"], 1)
        self.assertAlmostEqual(validated.loc[0, "accruals_accepted"], .2)
        self.assertTrue(pd.isna(validated.loc[1, "accruals_accepted"]))

    def test_earnings_after_10k_is_rejected(self):
        panel, earnings, accruals = self.fixtures()
        earnings.loc[0, "acceptance_datetime_utc"] = "2025-02-02T18:00:00Z"
        with self.assertRaisesRegex(ValueError, "not before"):
            MODULE.load_controls(panel, earnings, accruals)

    def test_wrong_accession_is_rejected(self):
        panel, earnings, accruals = self.fixtures()
        earnings.loc[0, "tenk_accession"] = "9999"
        with self.assertRaisesRegex(ValueError, "accession differs"):
            MODULE.load_controls(panel, earnings, accruals)


if __name__ == "__main__":
    unittest.main()
