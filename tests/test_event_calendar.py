"""Calendar regression tests for the supplied-price event study.

Run from the repository root with:
    python -m unittest discover -s tests -p "test_event_calendar.py" -v

The fixture has a known trading calendar and no external-data dependency.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


SOURCE = Path(__file__).resolve().parents[1] / "src" / "event_study_final.py"
SPEC = importlib.util.spec_from_file_location("event_study_calendar_test", SOURCE)
assert SPEC is not None and SPEC.loader is not None
EVENT_STUDY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVENT_STUDY)


def synthetic_prices() -> tuple[pd.DatetimeIndex, pd.DataFrame]:
    """Return 400 business sessions, with an undefined first daily return."""
    dates = pd.bdate_range("2020-01-06", periods=400)
    day = np.arange(len(dates), dtype=float)
    market_return = 0.0002 + 0.008 * np.sin(day / 7.0)
    stock_return = 0.0004 + 1.3 * market_return + 0.002 * np.cos(day / 11.0)
    frames = []
    for ticker, returns in (("TEST", stock_return), ("^GSPC", market_return)):
        returns = returns.copy()
        returns[0] = np.nan
        frames.append(pd.DataFrame({
            "ticker": ticker,
            "date": dates,
            "return": returns,
            "adj_close": 100.0 * np.cumprod(1.0 + np.nan_to_num(returns)),
        }))
    return dates, pd.concat(frames, ignore_index=True)


def filing_on(date: pd.Timestamp) -> dict:
    return {
        "ticker": "TEST",
        "filing_date": date,
        "accession_number": "0000000000-20-000001",
    }


class EventCalendarTests(unittest.TestCase):
    def assert_successful_calendar(self, filing_date: pd.Timestamp, index: int) -> None:
        dates, prices = synthetic_prices()
        result, event, estimation, status = EVENT_STUDY.process_filing(
            filing_on(filing_date), prices
        )
        self.assertEqual(status, "success")
        self.assertIsNotNone(result)
        self.assertIsNotNone(event)
        self.assertIsNotNone(estimation)
        self.assertEqual(result["event_date"], dates[index])
        self.assertEqual(result["n_estimation"], 239)
        self.assertEqual(len(estimation), 239)
        self.assertEqual(len(event), 11)
        self.assertEqual(event["event_time"].tolist(), list(range(-5, 6)))
        self.assertEqual(estimation["event_time"].tolist(), list(range(-244, -5)))

        # Compare every session with the original market calendar, not with a
        # filtered/renumbered version of the event-study output.
        self.assertEqual(event["date"].tolist(), dates[index - 5:index + 6].tolist())
        self.assertEqual(
            estimation["date"].tolist(), dates[index - 244:index - 5].tolist()
        )
        day_zero = event.loc[event["event_time"].eq(0), "date"].item()
        self.assertEqual(day_zero, result["event_date"])

    def test_initial_missing_return_does_not_shift_trading_day_event(self) -> None:
        dates, _ = synthetic_prices()
        self.assert_successful_calendar(dates[300], index=300)

    def test_weekend_filing_uses_next_market_session_without_extra_shift(self) -> None:
        dates, _ = synthetic_prices()
        self.assertEqual(dates[304].dayofweek, 4)  # Friday.
        saturday = dates[304] + pd.Timedelta(days=1)
        self.assert_successful_calendar(saturday, index=305)

    def test_missing_event_return_is_rejected_without_compressing_calendar(self) -> None:
        for ticker in ("TEST", "^GSPC"):
            for relative_day in (0, 3):
                with self.subTest(ticker=ticker, relative_day=relative_day):
                    dates, prices = synthetic_prices()
                    mask = prices["ticker"].eq(ticker) & prices["date"].eq(
                        dates[300 + relative_day]
                    )
                    prices.loc[mask, "return"] = np.nan
                    result, event, estimation, status = EVENT_STUDY.process_filing(
                        filing_on(dates[300]), prices
                    )
                    self.assertEqual(status, "missing_returns_in_event_calendar")
                    self.assertIsNone(result)
                    self.assertIsNone(event)
                    self.assertIsNone(estimation)


if __name__ == "__main__":
    unittest.main()
