"""Check the provided calculations against independently regenerated outputs."""

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


def compare_table(old: Path, new: Path) -> dict:
    a, b = pd.read_csv(old), pd.read_csv(new)
    if a.shape != b.shape or list(a.columns) != list(b.columns):
        return {"same": False, "original_shape": a.shape, "recomputed_shape": b.shape}
    mismatches = {}
    for col in a.columns:
        if pd.api.types.is_numeric_dtype(a[col]) and pd.api.types.is_numeric_dtype(b[col]):
            left, right = a[col].to_numpy(dtype=float), b[col].to_numpy(dtype=float)
            mask = ~np.isclose(left, right, rtol=1e-9, atol=1e-11, equal_nan=True)
        else:
            mask = a[col].fillna("").astype(str).to_numpy() != b[col].fillna("").astype(str).to_numpy()
        if mask.any():
            mismatches[col] = int(mask.sum())
    return {"same": not mismatches, "rows": len(a), "mismatches": mismatches}


def main() -> None:
    source = ROOT / "data/metadata"
    pairs = {
        "event_filing_results": (
            source / "event_study_final/event_filing_results.csv",
            OUT / "event_study/event_filing_results.csv",
        ),
        "event_daily_summary": (
            source / "event_study_final/event_daily_summary.csv",
            OUT / "event_study/event_daily_summary.csv",
        ),
        "event_study_summary": (
            source / "event_study_final/event_study_summary.csv",
            OUT / "event_study/event_study_summary.csv",
        ),
        "regression_results": (
            source / "regression_analysis/regression_results.csv",
            OUT / "regression/regression_results.csv",
        ),
        "regression_sample": (
            source / "regression_analysis/regression_sample.csv",
            OUT / "regression/regression_sample.csv",
        ),
    }
    comparisons = {name: compare_table(*paths) for name, paths in pairs.items()}

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
    if len(comparison) != len(tone):
        raise AssertionError("Dictionary comparison does not cover all tone rows")
    summary = {
        "source_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in [
            ROOT / "data/market_data/daily_prices.csv",
            source / "filings_2016_2025.csv",
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
        "table_comparisons": comparisons,
        "tone_arithmetic": tone_checks,
        "car_arithmetic": car_checks,
        "raw_10k_text_in_zip": False,
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "verification.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "source_sha256"},
                     ensure_ascii=False, indent=2))
    if not all(x["same"] for x in comparisons.values()):
        raise AssertionError("Recomputed table differs from supplied original")
    if any(x["mismatches"] for x in [*tone_checks.values(), *car_checks.values()]):
        raise AssertionError("Tone or CAR arithmetic mismatch")


if __name__ == "__main__":
    main()
