"""Validate arithmetic, event dates, sample coverage and output consistency."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis_outputs"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_event_calendar(events: pd.DataFrame, ar: pd.DataFrame) -> dict:
    """Check event positions against the benchmark trading calendar."""
    keys = ["ticker", "filing_date", "accession_number"]
    if events.duplicated(keys).any() or ar.duplicated([*keys, "event_time"]).any():
        raise AssertionError("Duplicate filing or event-day key")
    day_counts = ar.groupby(keys).event_time.nunique()
    if not day_counts.eq(11).all():
        raise AssertionError("Each filing needs all eleven event days")
    if set(ar.event_time) != set(range(-5, 6)):
        raise AssertionError("Wrong event-day range")
    day_zero = ar.loc[ar.event_time.eq(0)]
    if len(day_zero) != len(events):
        raise AssertionError("One day-zero row is required per event")
    day_zero = day_zero.merge(
        events[[*keys, "event_date", "event_date_shift"]],
        on=keys, validate="one_to_one", suffixes=("_ar", "_filing"),
    )
    aligned = day_zero.date.eq(day_zero.event_date_ar) & day_zero.date.eq(day_zero.event_date_filing)
    if not aligned.all():
        raise AssertionError(f"Event day zero differs from event date in {int((~aligned).sum())} filings")
    filing_dates = pd.to_datetime(day_zero.filing_date)
    event_dates = pd.to_datetime(day_zero.date)
    if (event_dates < filing_dates).any() or (day_zero.event_date_shift.eq(0) &
                                             event_dates.ne(filing_dates)).any():
        raise AssertionError("Event date precedes filing or same-session flag is inconsistent")
    if not np.isfinite(ar[["firm_return", "market_return", "ar"]].to_numpy(float)).all():
        raise AssertionError("Event window contains missing or infinite returns")
    prices = pd.read_csv(ROOT / "data/market_data/daily_prices.csv",
                         usecols=["ticker", "date"])
    market_days = pd.to_datetime(prices.loc[prices.ticker.eq("^GSPC"), "date"])
    market_days = market_days.drop_duplicates().sort_values().reset_index(drop=True)
    market_position = pd.Series(np.arange(len(market_days)), index=market_days)
    actual_position = pd.to_datetime(ar.date).map(market_position)
    expected_position = pd.to_datetime(ar.event_date).map(market_position) + ar.event_time
    if actual_position.isna().any() or expected_position.isna().any() or not actual_position.eq(expected_position).all():
        raise AssertionError("Event dates do not match market sessions at their relative day")
    return {"filings_checked": len(day_zero), "day_zero_date_mismatches": 0,
            "complete_11_day_windows": int(day_counts.eq(11).sum()),
            "rows_matching_market_calendar": int(actual_position.eq(expected_position).sum())}


def main() -> None:
    source = ROOT / "data/metadata"
    tone = pd.read_csv(source / "tone_method_item7.csv")
    tone_checks = {}
    for prefix in ("lm", "harvard"):
        words = pd.to_numeric(tone[f"{prefix}_total_words"], errors="coerce")
        positive = pd.to_numeric(tone[f"{prefix}_positive_count"], errors="coerce")
        negative = pd.to_numeric(tone[f"{prefix}_negative_count"], errors="coerce")
        expected = (positive - negative) / words
        actual = pd.to_numeric(tone[f"{prefix}_net_prop"], errors="coerce")
        valid = words.gt(0) & expected.notna() & actual.notna()
        tone_checks[prefix] = {
            "checked": int(valid.sum()),
            "mismatches": int((~np.isclose(expected[valid], actual[valid], rtol=1e-9, atol=1e-11)).sum()),
        }

    events = pd.read_csv(OUT / "event_study/event_filing_results.csv", dtype={"accession_number": str})
    ar = pd.read_csv(OUT / "event_study/event_ar_long.csv", dtype={"accession_number": str})
    if not events.event_date_source.eq("sec_acceptance_time").all():
        raise AssertionError("Some event dates did not use SEC acceptance time")
    if events.accepted_at_utc.isna().any():
        raise AssertionError("SEC acceptance timestamps are missing")
    calendar_checks = check_event_calendar(events, ar)
    calendar_checks["sec_timestamps_matched"] = len(events)
    calendar_checks["sessions_shifted_after_filing_date"] = int(events.event_date_shift.sum())
    extended = pd.read_csv(OUT / "event_study/extended_window_tests.csv")
    corrado = pd.read_csv(OUT / "event_study/corrado_daily.csv")
    power = pd.read_csv(OUT / "event_study/theoretical_power.csv")
    if set(extended.window) != {"CAR_m1_p1", "CAR_0_p3", "CAR_m3_p3", "CAR_m5_p5"}:
        raise AssertionError("Extended tests do not cover four CAR windows")
    if set(corrado.event_time) != set(range(-5, 6)):
        raise AssertionError("Corrado rank test does not cover eleven event days")
    if not extended[["brown_warner_p", "autocorr_p"]].stack().between(0, 1).all():
        raise AssertionError("Invalid extended-test p-values")
    if not power.theoretical_power.between(0, 1).all():
        raise AssertionError("Invalid theoretical power values")
    b6 = pd.read_csv(OUT / "event_study/b6_robustness_tests.csv")
    delayed = pd.read_csv(OUT / "event_study/delayed_filing_results.csv")
    c5 = pd.read_csv(OUT / "c5_reduced_results.csv")
    c6 = pd.read_csv(OUT / "c6_delayed_results.csv")
    c7 = pd.read_csv(OUT / "c7_cross_section_results.csv")
    c8 = pd.read_csv(OUT / "c8_fama_macbeth_summary.csv")
    if set(b6.window) != set(extended.window) or len(delayed) != len(events):
        raise AssertionError("B6/C6 event coverage changed")
    if delayed[["car_p5_p5", "car_p5_p10", "car_p5_p22"]].notna().sum().ne(
            [969, 969, 963]).any():
        raise AssertionError("C6 complete-case coverage changed")
    if not c5.n.eq(769).all() or not c7.n.eq(862).all():
        raise AssertionError("C5/C7 sample coverage changed")
    if not c8.n_years.eq(10).all():
        raise AssertionError("C8 needs ten annual coefficients")
    if not b6[["standardized_p", "cross_sectional_p"]].stack().between(0, 1).all():
        raise AssertionError("Invalid B6 p-values")
    if not c6[["p_hc3_two_sided", "p_cluster_two_sided"]].stack().between(0, 1).all():
        raise AssertionError("Invalid C6 p-values")
    original_bw = pd.read_csv(OUT / "event_study/event_study_summary.csv")
    original_bw = original_bw.loc[original_bw.window.eq("CAR_m5_p5")].iloc[0]
    updated_bw = extended.loc[extended.window.eq("CAR_m5_p5")].iloc[0]
    if not np.isclose(original_bw.Brown_Warner_Z, updated_bw.brown_warner_z):
        raise AssertionError("Brown–Warner eleven-day calculation changed")

    controls = pd.read_csv(source / "controls/controls_item7.csv")
    if pd.to_datetime(controls.filing_date, format="%Y-%m-%d", errors="coerce").isna().any():
        raise AssertionError("Control filing dates are not ISO dates")
    with_shares = controls.dropna(subset=["shares_outstanding", "shares_split_adjusted", "split_factor"])
    if not np.isclose(
        with_shares.shares_split_adjusted,
        with_shares.shares_outstanding * with_shares.split_factor,
        rtol=1e-9,
    ).all():
        raise AssertionError("Split-adjusted shares do not match SEC shares and split factor")
    with_cap = controls.dropna(subset=["price_tminus1", "shares_split_adjusted", "market_cap_tminus1"])
    if not np.isclose(
        with_cap.market_cap_tminus1,
        with_cap.price_tminus1 * with_cap.shares_split_adjusted,
        rtol=1e-9,
    ).all():
        raise AssertionError("Market cap uses a different share basis than the historical price")
    car_checks = {}
    for label, lo, hi in (("CAR_m1_p1", -1, 1), ("CAR_0_p3", 0, 3),
                          ("CAR_m3_p3", -3, 3), ("CAR_m5_p5", -5, 5)):
        summed = ar.loc[ar.event_time.between(lo, hi)].groupby("accession_number").ar.sum()
        actual = events.set_index("accession_number")[label]
        aligned = actual.to_frame("actual").join(summed.rename("summed"), how="left")
        mask = np.isclose(aligned.actual, aligned.summed, rtol=1e-9, atol=1e-11)
        car_checks[label] = {"checked": len(aligned), "mismatches": int((~mask).sum())}

    filings = pd.read_csv(source / "filings_2016_2025.csv")
    sections = pd.read_csv(source / "sections_10k_v3.csv")
    missing = filings[["ticker", "filing_date", "accession_number"]].merge(
        sections[["ticker", "filing_date", "item_7_mda_status"]],
        on=["ticker", "filing_date"], how="left", validate="one_to_one",
    )
    missing["has_tone"] = missing.set_index(["ticker", "filing_date"]).index.isin(
        tone.set_index(["ticker", "filing_date"]).index
    )
    missing["has_event"] = missing.set_index(["ticker", "filing_date"]).index.isin(
        events.set_index(["ticker", "filing_date"]).index
    )
    exclusions = pd.read_csv(OUT / "event_study/event_exclusions.csv",
                             dtype={"accession_number": str})
    if len(exclusions) != len(tone) - len(events):
        raise AssertionError("Event exclusions do not explain all omitted tone rows")
    missing = missing.merge(
        exclusions[["ticker", "filing_date", "event_exclusion_reason"]],
        on=["ticker", "filing_date"], how="left", validate="one_to_one",
    )
    missing.loc[~missing.has_tone | ~missing.has_event].to_csv(
        OUT / "missing_filings.csv", index=False, encoding="utf-8-sig"
    )
    c2 = pd.read_csv(OUT / "c2_reduced_results.csv")
    panel = pd.read_csv(OUT / "tone_firm_year.csv")
    comparison = pd.read_csv(OUT / "dictionary_comparison_filings.csv")
    if len(panel) != 1000 or panel.duplicated(["ticker", "filing_year"]).any():
        raise AssertionError("Firm-year panel is not one row per company and filing year")
    if not (panel.groupby("ticker").size() == 10).all():
        raise AssertionError("Firm-year panel does not include 10 filing years per firm")
    if int(panel.has_method_score.sum()) != len(tone) or int(panel.has_event_car.sum()) != len(events):
        raise AssertionError("Firm-year coverage differs from source tables")
    event_cars = events[["ticker", "filing_date", "CAR_m1_p1", "CAR_0_p3",
                         "CAR_m3_p3", "CAR_m5_p5"]]
    panel_cars = panel.merge(event_cars, on=["ticker", "filing_date"], how="inner",
                             validate="one_to_one", suffixes=("_panel", "_event"))
    if len(panel_cars) != len(events):
        raise AssertionError("Firm-year panel is missing recomputed event rows")
    for name in ("CAR_m1_p1", "CAR_0_p3", "CAR_m3_p3", "CAR_m5_p5"):
        if not np.isclose(panel_cars[f"{name}_panel"], panel_cars[f"{name}_event"],
                          rtol=1e-9, atol=1e-11).all():
            raise AssertionError(f"Firm-year panel has stale {name} values")
    if len(comparison) != len(tone):
        raise AssertionError("Dictionary comparison does not cover all tone rows")
    summary = {
        "source_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in [
            ROOT / "data/market_data/daily_prices.csv",
            ROOT / "data/market_data/stock_splits.csv",
            source / "filings_2016_2025.csv",
            source / "filing_acceptance.csv",
            source / "tone_method_item7.csv",
            source / "controls/controls_item7.csv",
        ]},
        "input_filings": len(filings),
        "input_firms": int(filings.ticker.nunique()),
        "tone_rows": len(tone),
        "event_rows": len(events),
        "missing_tone": int((~missing.has_tone).sum()),
        "missing_event": int((~missing.has_event).sum()),
        "c2_complete_cases": int(c2.n.iloc[0]),
        "c2_firms": int(c2.n_firms.iloc[0]),
        "firm_year_rows": len(panel),
        "dictionary_opposite_sign": int(comparison.opposite_sign.sum()),
        "event_calendar": calendar_checks,
        "extended_event_tests": {"brown_warner_windows": len(extended),
                                 "corrado_days": len(corrado),
                                 "power_scenarios": len(power)},
        "optional_robustness": {"b6_windows": len(b6), "c5_filings": int(c5.n.iloc[0]),
                                "c6_windows": int(c6.dependent_variable.nunique()),
                                "c6_long_window_filings": int(delayed.car_p5_p22.notna().sum()),
                                "c7_filings": int(c7.n.iloc[0]),
                                "c8_years": int(c8.n_years.iloc[0])},
        "tone_arithmetic": tone_checks,
        "car_arithmetic": car_checks,
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "verification.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "source_sha256"},
                     ensure_ascii=False, indent=2))
    if any(x["mismatches"] for x in [*tone_checks.values(), *car_checks.values()]):
        raise AssertionError("Tone or CAR arithmetic mismatch")


if __name__ == "__main__":
    main()
