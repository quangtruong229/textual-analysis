"""Summarize supplied LM versus Harvard IV-4 tone without claiming ground truth."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis_outputs"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    score = pd.read_csv(ROOT / "data/metadata/tone_method_item7.csv",
                        dtype={"accession_number": str})
    if len(score) != 971 or score.duplicated(["ticker", "filing_date"]).any():
        raise ValueError("Unexpected tone comparison sample")
    lm = pd.to_numeric(score.lm_net_prop, errors="coerce")
    general = pd.to_numeric(score.harvard_net_prop, errors="coerce")
    if lm.isna().any() or general.isna().any():
        raise ValueError("Missing LM or Harvard score")
    opposite = lm.mul(general).lt(0)
    details = score[["ticker", "company_name", "filing_date", "report_date",
                     "accession_number", "lm_net_prop", "harvard_net_prop"]].copy()
    details["opposite_sign"] = opposite
    details["harvard_minus_lm"] = general - lm
    summary = pd.DataFrame([{
        "n_comparable_filings": len(score),
        "n_opposite_sign": int(opposite.sum()),
        "share_opposite_sign": float(opposite.mean()),
        "n_lm_negative_harvard_positive": int((lm.lt(0) & general.gt(0)).sum()),
        "n_both_positive": int((lm.gt(0) & general.gt(0)).sum()),
        "n_both_negative": int((lm.lt(0) & general.lt(0)).sum()),
        "n_either_zero": int((lm.eq(0) | general.eq(0)).sum()),
        "mean_lm_net_prop": float(lm.mean()),
        "mean_harvard_net_prop": float(general.mean()),
        "median_harvard_minus_lm": float((general - lm).median()),
        "interpretation_limit": "Score disagreement is not proof either dictionary is correct; raw context unavailable.",
    }])
    OUT.mkdir(exist_ok=True)
    details.to_csv(OUT / "dictionary_comparison_filings.csv", index=False,
                   encoding="utf-8-sig")
    summary.to_csv(OUT / "dictionary_comparison_summary.csv", index=False,
                   encoding="utf-8-sig")
    print(f"Comparable filings: {len(score)}")
    print(f"Opposite tone sign: {int(opposite.sum())} ({100 * opposite.mean():.1f}%)")
    print("This is dictionary disagreement, not a validated classification error.")


if __name__ == "__main__":
    main()
