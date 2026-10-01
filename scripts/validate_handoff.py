"""Validate the UI data contract and write a checksum manifest.

Run after the calculation scripts. This reads existing results; it does not
re-estimate tone, CAR, or regressions.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "handoff"
FILES = {
    "firm_year": "analysis_outputs/tone_firm_year.csv",
    "dictionary_summary": "analysis_outputs/dictionary_comparison_summary.csv",
    "dictionary_filings": "analysis_outputs/dictionary_comparison_filings.csv",
    "event_filing": "analysis_outputs/event_study/event_filing_results.csv",
    "event_exclusions": "analysis_outputs/event_study/event_exclusions.csv",
    "event_daily": "analysis_outputs/event_study/event_daily_summary.csv",
    "event_windows": "analysis_outputs/event_study/event_study_summary.csv",
    "event_extended": "analysis_outputs/event_study/extended_window_tests.csv",
    "corrado_daily": "analysis_outputs/event_study/corrado_daily.csv",
    "theoretical_power": "analysis_outputs/event_study/theoretical_power.csv",
    "b6_robustness": "analysis_outputs/event_study/b6_robustness_tests.csv",
    "c5_reduced": "analysis_outputs/c5_reduced_results.csv",
    "c5_sample": "analysis_outputs/c5_reduced_sample.csv",
    "c6_delayed": "analysis_outputs/c6_delayed_results.csv",
    "delayed_filings": "analysis_outputs/event_study/delayed_filing_results.csv",
    "c7_cross_section": "analysis_outputs/c7_cross_section_results.csv",
    "c7_sample": "analysis_outputs/c7_cross_section_sample.csv",
    "c8_annual": "analysis_outputs/c8_annual_coefficients.csv",
    "c8_summary": "analysis_outputs/c8_fama_macbeth_summary.csv",
    "regression": "analysis_outputs/regression/regression_results.csv",
    "c2_regression": "analysis_outputs/c2_reduced_results.csv",
    "c2_matched4": "analysis_outputs/c2_matched4_results.csv",
    "c2_full6": "analysis_outputs/c2_full6_results.csv",
    "c2_full6_sample": "analysis_outputs/c2_full6_sample.csv",
    "c3_full6": "analysis_outputs/c3_posneg_full6_results.csv",
    "c5_full6": "analysis_outputs/c5_full6_results.csv",
    "c5_full6_sample": "analysis_outputs/c5_full6_sample.csv",
    "missing_filings": "analysis_outputs/missing_filings.csv",
    "word_power_scores": "analysis_outputs/word_power/scores.csv",
    "word_power_regression": "analysis_outputs/word_power/regression_results.csv",
    "word_power_six_control_sample": "analysis_outputs/word_power/six_control_sample.csv",
    "word_power_ridge_sensitivity": "analysis_outputs/word_power/ridge_sensitivity.csv",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    tables = {}
    for name, relative in FILES.items():
        path = ROOT / relative
        require(path.is_file(), f"Missing {relative}")
        tables[name] = pd.read_csv(path, dtype={"accession_number": str, "cik": str})

    panel = tables["firm_year"]
    keys = ["ticker", "filing_date"]
    require(len(panel) == 1000, "Expected 1000 filing rows")
    require(not panel.duplicated(keys).any(), "Duplicate company-date in firm-year panel")
    require(not panel.duplicated(["ticker", "filing_year"]).any(), "Duplicate company-filing-year")
    require(panel.ticker.nunique() == 100, "Expected 100 companies")
    require((panel.groupby("ticker").size() == 10).all(), "Expected 10 filings per company")
    require(set(panel.filing_year) == set(range(2016, 2026)), "Filing-year range changed")
    require(panel.filing_year.eq(pd.to_datetime(panel.filing_date).dt.year).all(), "Filing year/date mismatch")
    require(panel.report_year.eq(pd.to_datetime(panel.report_date).dt.year).all(), "Report year/date mismatch")
    require(panel.sec_url.str.startswith("https://www.sec.gov/Archives/edgar/data/").all(), "Bad SEC URL")
    require(panel.has_method_score.eq(panel.lm_net_prop.notna()).all(), "Tone flag inconsistent")
    require(panel.has_event_car.eq(panel.CAR_m1_p1.notna()).all(), "CAR flag inconsistent")
    require(int(panel.has_method_score.sum()) == 971, "Expected 971 tone rows")
    require(int(panel.has_event_car.sum()) == 969, "Expected 969 event rows")

    comparison = tables["dictionary_filings"]
    require(len(comparison) == 971 and not comparison.duplicated(keys).any(), "Dictionary keys changed")
    require(comparison.opposite_sign.eq(comparison.lm_net_prop.mul(comparison.harvard_net_prop).lt(0)).all(),
            "Dictionary sign flag inconsistent")
    require(int(comparison.opposite_sign.sum()) == int(tables["dictionary_summary"].n_opposite_sign.iloc[0]),
            "Dictionary summary disagrees with filing rows")

    events = tables["event_filing"]
    require(len(events) == 969 and not events.duplicated(keys).any(), "Event keys changed")
    excluded = tables["event_exclusions"]
    require(len(excluded) == 2 and not excluded.duplicated(keys).any(), "Event exclusions changed")
    require(excluded.event_exclusion_reason.notna().all(), "Event exclusions need reasons")
    require(not excluded.set_index(keys).index.isin(events.set_index(keys).index).any(),
            "Excluded event also appears in valid event results")
    require(len(tables["event_windows"]) == 4, "Expected four CAR windows")
    require(tables["event_windows"].N.eq(969).all(), "Event window N differs")
    require(len(tables["event_daily"]) == 11, "Expected event days -5 through +5")
    require(set(tables["event_daily"].event_time) == set(range(-5, 6)), "Event-day axis changed")
    require(set(tables["event_extended"].window) == set(tables["event_windows"].window),
            "Brown–Warner/B7 windows do not match CAR windows")
    require(set(tables["corrado_daily"].event_time) == set(range(-5, 6)),
            "Corrado daily coverage changed")
    require(len(tables["theoretical_power"]) == 12,
            "Expected three theoretical effect scenarios per CAR window")
    require(set(tables["b6_robustness"].window) == set(tables["event_windows"].window),
            "B6 windows do not match CAR windows")
    require(len(tables["delayed_filings"]) == len(events), "C6 filing coverage changed")
    require(tables["c8_annual"].filing_year.nunique() == 10, "C8 needs ten years")
    require(tables["c8_summary"].n_years.eq(10).all(), "C8 year count mismatch")
    require(len(tables["c7_sample"]) == int(tables["c2_regression"].n.iloc[0]),
            "C7 control sample changed")

    for name in ("regression", "c2_regression", "c2_matched4", "c2_full6",
                 "c3_full6", "c5_reduced", "c5_full6", "c6_delayed", "c7_cross_section"):
        table = tables[name]
        require(table.p_hc3_two_sided.dropna().between(0, 1).all(), f"Invalid HC3 p-values in {name}")
        require(table.p_cluster_two_sided.dropna().between(0, 1).all(), f"Invalid cluster p-values in {name}")
    require(len(tables["regression"]) == 76, "Expected 76 C1/C3/C4 rows")
    require(len(tables["c2_regression"]) == 24, "Expected 24 reduced C2 rows")
    require(tables["c2_regression"].n.eq(862).all(), "Reduced C2 sample changed")
    require(len(tables["c2_full6_sample"]) == 481 and
            tables["c2_full6_sample"].ticker.nunique() == 71,
            "Six-control sample coverage changed")
    require(len(tables["c5_full6_sample"]) == 431,
            "Full C5 sample coverage changed")
    for name in ("c2_matched4", "c2_full6", "c3_full6"):
        require(tables[name].n.eq(481).all(), f"{name} sample mismatch")

    wp = tables["word_power_scores"]
    require(len(wp) == 971 and not wp.duplicated(keys).any(), "Word Power score coverage changed")
    require(wp[["lm_positive_wp", "lm_negative_wp"]].notna().all().all(),
            "Missing Word Power scores")
    wp_reg = tables["word_power_regression"]
    require(wp_reg.p_hc3_two_sided.dropna().between(0, 1).all(), "Invalid Word Power HC3 p")
    require(wp_reg.p_cluster_two_sided.dropna().between(0, 1).all(), "Invalid Word Power cluster p")
    for model, term, n in (
        ("C1_H1_WP_positive", "lm_positive_wp", 969),
        ("C1_H2_WP_negative", "lm_negative_wp", 969),
        ("C2_H1_WP_positive_six_controls", "lm_positive_wp", 481),
        ("C2_H2_WP_negative_six_controls", "lm_negative_wp", 481),
    ):
        rows = wp_reg.loc[wp_reg.model.eq(model) &
                          wp_reg.dependent_variable.eq("car_0_p3") & wp_reg.term.eq(term)]
        require(len(rows) == 1 and int(rows.iloc[0].n) == n, f"Word Power {model} result changed")
    require(len(tables["word_power_six_control_sample"]) == 481,
            "Word Power six-control sample changed")

    files = {}
    for name, relative in FILES.items():
        path = ROOT / relative
        files[name] = {
            "path": relative.replace("\\", "/"),
            "rows": int(len(tables[name])),
            "sha256": digest(path),
            "columns": list(tables[name].columns),
        }
    manifest = {
        "contract_version": 1,
        "date_axis": "filing_year = calendar year of filing_date; report_year is separate",
        "return_units": "CAR, CAAR, AAR are decimal returns: 0.01 = 1%",
        "tone_units": "LM and Harvard proportional tone are ratios, not percentages",
        "missing_rule": "NaN/blank means unavailable; never coerce to zero",
        "full_sample_models": "Regression CSVs describe their saved samples; UI filters do not refit them",
        "files": files,
    }
    OUT.mkdir(exist_ok=True)
    target = OUT / "manifest.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Handoff PASS: 1000 filings, 971 tone, 969 CAR, 862 C2; {len(files)} tables")
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
