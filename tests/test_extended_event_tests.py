"""Independent arithmetic checks for extended event-study diagnostics."""

import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "extended_event_tests.py"
SPEC = importlib.util.spec_from_file_location("extended_tests", SOURCE)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExtendedEventTests(unittest.TestCase):
    def test_brown_warner_all_windows_and_power_at_zero(self) -> None:
        days = np.arange(-244, -5)
        noise = np.random.default_rng(42).normal(0, .01, len(days))
        ar = np.zeros(len(days))
        for index in range(1, len(days)):
            ar[index] = .4 * ar[index - 1] + noise[index]
        estimation = pd.DataFrame({"event_time": days, "ar": ar})
        event = pd.DataFrame({"event_time": np.arange(-5, 6), "ar": .002})
        result = MODULE.brown_warner_windows(estimation, event)
        self.assertEqual(result.window.tolist(), list(MODULE.WINDOWS))
        self.assertGreater(result.iloc[0].rho_1, 0)
        for row in result.itertuples():
            self.assertAlmostEqual(row.caar, row.n_event_days * .002)
            self.assertAlmostEqual(row.brown_warner_z,
                                   row.caar / (row.estimation_aar_sd * np.sqrt(row.n_event_days)))
            self.assertGreater(row.autocorr_se,
                               row.estimation_aar_sd * np.sqrt(row.n_event_days))
        power = MODULE.theoretical_power(result, effects=(0.,))
        self.assertTrue(np.allclose(power.theoretical_power, .05))

    def test_corrado_rank_center_and_day_zero(self) -> None:
        days = np.arange(-244, -5)
        estimation = pd.concat([
            pd.DataFrame({"ticker": ticker, "accession_number": accession,
                          "event_time": days, "ar": np.sin(days + shift)})
            for ticker, accession, shift in (("A", "1", 0.), ("B", "2", .7))
        ])
        event = pd.concat([
            pd.DataFrame({"ticker": ticker, "accession_number": accession,
                          "event_time": np.arange(-5, 6), "ar": 10.})
            for ticker, accession in (("A", "1"), ("B", "2"))
        ])
        result = MODULE.corrado_daily(estimation, event)
        self.assertEqual(len(result), 11)
        self.assertTrue((result.corrado_z > 0).all())


if __name__ == "__main__":
    unittest.main()
