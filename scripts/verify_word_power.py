"""Independently reconstruct exported out-of-year Word Power scores."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/item7_corpus/item7_lm_sentiment_counts.csv.gz"
OUT = ROOT / "analysis_outputs/word_power"
KEY = ["ticker", "filing_date", "accession_number"]


def main() -> None:
    terms = pd.read_csv(CORPUS, dtype={"accession_number": str})
    scores = pd.read_csv(OUT / "scores.csv", dtype={"accession_number": str})
    weights = pd.read_csv(OUT / "annual_weights.csv.gz")
    qa = json.loads((OUT / "qa.json").read_text(encoding="utf-8"))
    if len(scores) != 971 or scores.duplicated(KEY).any():
        raise AssertionError("Score filing coverage or keys changed")
    if len(qa["folds"]) != 20:
        raise AssertionError("Expected two sentiment folds for each of ten years")
    if weights.duplicated(["held_out_year", "category", "term"]).any():
        raise AssertionError("Duplicate saved Word Power weight")
    if set(weights.held_out_year) != set(range(2016, 2026)):
        raise AssertionError("Missing held-out year")
    for fold in qa["folds"]:
        year = fold["held_out_year"]
        category = fold["category"]
        if year in fold["train_years"] or len(fold["train_years"]) != 9:
            raise AssertionError(f"Held-out year leakage: {year}/{category}")
        block = weights.loc[weights.held_out_year.eq(year) & weights.category.eq(category)]
        if len(block) != fold["active_terms"]:
            raise AssertionError(f"Active term count changed: {year}/{category}")
        if abs(block.weight.mean()) > 1e-9 or abs(block.weight.std(ddof=0) - 1) > 1e-9:
            raise AssertionError(f"Eq. 7 weight standardization failed: {year}/{category}")
        if (block.training_document_frequency < 5).any():
            raise AssertionError(f"Rare term entered weight model: {year}/{category}")

    year_lookup = scores[KEY + ["filing_year", "lm_total_words"]]
    joined = terms.merge(year_lookup, on=["ticker", "filing_date"], how="left",
                         validate="many_to_one", suffixes=("_term", "_score"))
    if joined.filing_year.isna().any():
        raise AssertionError("Unmatched corpus filing")
    term_accession = joined.accession_number_term.str.replace("-", "", regex=False)
    score_accession = joined.accession_number_score.str.replace("-", "", regex=False)
    if not term_accession.eq(score_accession).all():
        raise AssertionError("Corpus accession mismatch")
    joined["accession_number"] = joined.accession_number_score
    joined = joined.merge(weights, left_on=["filing_year", "category", "term"],
                          right_on=["held_out_year", "category", "term"],
                          how="left", validate="many_to_one")
    joined["contribution"] = (joined["count"] / joined.lm_total_words
                              * joined.weight.fillna(0))
    reconstructed = joined.groupby(KEY + ["category"], as_index=False).contribution.sum()
    for category in ("positive", "negative"):
        reference = scores[KEY + [f"lm_{category}_wp"]]
        actual = reconstructed.loc[reconstructed.category.eq(category),
                                   KEY + ["contribution"]]
        checked = reference.merge(actual, on=KEY, how="left", validate="one_to_one")
        if not np.allclose(checked.contribution.fillna(0), checked[f"lm_{category}_wp"],
                           rtol=1e-9, atol=1e-12):
            raise AssertionError(f"Saved {category} scores differ from term-weight sum")
    print("Word Power PASS: 971 scores reconstructed, 20 folds, no held-year leakage")


if __name__ == "__main__":
    main()
