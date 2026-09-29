"""Assemble one transparent company-by-filing-year panel from supplied outputs.

This is a join and audit artifact, not a recalculation of word scores or CAR.
It retains every filing and marks unavailable measures explicitly.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/metadata"
OUT = ROOT / "analysis_outputs/tone_firm_year.csv"


def normalized_accession(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace("-", "", regex=False).str.zfill(18)


def checked_join(base: pd.DataFrame, other: pd.DataFrame, label: str) -> pd.DataFrame:
    keys = ["ticker", "filing_date", "accession_key"]
    if other.duplicated(keys).any():
        raise ValueError(f"Duplicate {label} rows by filing key")
    return base.merge(other, on=keys, how="left", validate="one_to_one")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    filings = pd.read_csv(DATA / "filings_2016_2025.csv", dtype=str)
    filings["accession_key"] = normalized_accession(filings.accession_number)
    filings["filing_year"] = pd.to_datetime(filings.filing_date).dt.year
    filings["report_year"] = pd.to_datetime(filings.report_date).dt.year
    if len(filings) != 1000 or filings.duplicated(["ticker", "filing_year"]).any():
        raise ValueError("Expected exactly one filing per firm and filing year")
    filings["sec_url"] = (
        "https://www.sec.gov/Archives/edgar/data/"
        + filings.cik.str.lstrip("0") + "/"
        + filings.accession_key + "/" + filings.primary_document
    )
    panel = filings[[
        "ticker", "company_name", "cik", "filing_year", "report_year",
        "filing_date", "report_date", "accession_number", "accession_key", "sec_url",
    ]].copy()

    lm = pd.read_csv(DATA / "lm_tone.csv", dtype={"accession_number": str})
    lm["accession_key"] = normalized_accession(lm.accession_number)
    panel = checked_join(panel, lm[[
        "ticker", "filing_date", "accession_key", "item_7_mda_lm_status",
        "item_7_mda_total_words", "item_7_mda_positive_count",
        "item_7_mda_negative_count", "item_7_mda_uncertainty_count",
        "item_7_mda_net_tone",
    ]], "LM")

    method = pd.read_csv(DATA / "tone_method_item7.csv", dtype={"accession_number": str})
    method["accession_key"] = normalized_accession(method.accession_number)
    panel = checked_join(panel, method[[
        "ticker", "filing_date", "accession_key", "lm_net_prop", "lm_net_ratio",
        "lm_net_tfidf", "lm_negated_positive_count", "lm_negated_negative_count",
        "harvard_net_prop", "harvard_net_tfidf",
    ]], "tone_method")

    event = pd.read_csv(ROOT / "analysis_outputs/event_study/event_filing_results.csv",
                        dtype={"accession_number": str})
    event["accession_key"] = normalized_accession(event.accession_number)
    panel = checked_join(panel, event[[
        "ticker", "filing_date", "accession_key", "event_date",
        "CAR_m1_p1", "CAR_0_p3", "CAR_m3_p3", "CAR_m5_p5",
    ]], "event")
    panel["has_item7_tone"] = panel.item_7_mda_lm_status.eq("success")
    panel["has_method_score"] = panel.lm_net_prop.notna()
    panel["has_event_car"] = panel.CAR_m1_p1.notna()
    panel = panel.drop(columns="accession_key").sort_values(["ticker", "filing_year"])
    if panel.ticker.nunique() != 100 or len(panel) != 1000:
        raise ValueError("Panel must retain all 1000 filings from 100 firms")
    OUT.parent.mkdir(exist_ok=True)
    panel.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"Saved {OUT}: {len(panel)} filings, {panel.ticker.nunique()} firms")
    print("Filing years:", panel.filing_year.min(), "to", panel.filing_year.max())
    print("Item 7 tone available:", int(panel.has_item7_tone.sum()))
    print("Method score available:", int(panel.has_method_score.sum()))
    print("Event CAR available:", int(panel.has_event_car.sum()))
    print("Report dates before 2016:", int(panel.report_year.lt(2016).sum()))


if __name__ == "__main__":
    main()
