"""Arithmetic and alignment checks for the optional specifications."""

import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "optional_robustness.py"
SPEC = importlib.util.spec_from_file_location("optional_robustness", SOURCE)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OptionalRobustnessTests(unittest.TestCase):
    def test_b6_cross_sectional_variance_uses_document_formula(self) -> None:
        estimation = pd.concat([
            pd.DataFrame({"ticker": f"F{i}", "accession_number": str(i),
                          "event_time": np.arange(-244, -5),
                          "ar": np.arange(239) / 10000})
            for i in range(5)
        ], ignore_index=True)
        filings = pd.DataFrame({"ticker": [f"F{i}" for i in range(5)],
                                "accession_number": [str(i) for i in range(5)]})
        for window in MODULE.WINDOWS:
            filings[window] = np.arange(1, 6) / 100
        result = MODULE.b6_tests(estimation, filings)
        car = filings.CAR_m1_p1.to_numpy()
        expected_se = np.sqrt(np.sum((car - car.mean()) ** 2)) / len(car)
        self.assertAlmostEqual(result.iloc[0].cross_sectional_se, expected_se)
        self.assertEqual(len(result), 4)

    def test_c6_uses_complete_market_sessions_and_includes_day_five(self) -> None:
        dates = pd.date_range("2025-01-01", periods=30, freq="B").strftime("%Y-%m-%d")
        prices = pd.concat([
            pd.DataFrame({"ticker": ticker, "date": dates, "return": value})
            for ticker, value in (("^GSPC", 0.0), ("F", .01))
        ], ignore_index=True)
        filings = pd.DataFrame({"ticker": ["F"], "filing_date": [dates[2]],
                                "event_date": [dates[2]], "accession_number": ["1"],
                                "alpha": [0.0], "beta": [1.0]})
        result = MODULE.delayed_returns(filings, prices).iloc[0]
        self.assertAlmostEqual(result.car_p5_p5, .01)
        self.assertAlmostEqual(result.car_p5_p10, .06)
        self.assertAlmostEqual(result.car_p5_p22, .18)

    def test_c8_averages_ten_annual_coefficients(self) -> None:
        rows = []
        for year in range(2016, 2026):
            for i in range(30):
                x = i / 30
                rows.append({"ticker": f"F{i}", "filing_year": year,
                             "tone": x, "car": (year - 2015) * x})
        annual, summary = MODULE.c8_fama_macbeth(
            pd.DataFrame(rows), "car", ["tone"], "test")
        self.assertEqual(annual.filing_year.nunique(), 10)
        self.assertAlmostEqual(summary.set_index("term").loc["tone", "mean_coefficient"], 5.5)


if __name__ == "__main__":
    unittest.main()
