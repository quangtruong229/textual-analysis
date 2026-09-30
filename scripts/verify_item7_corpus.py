"""Check downloaded Item 7 text and per-filing term counts against LM tone."""

from __future__ import annotations

import csv
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.build_method_scores import load_lm, sentiment_counts, tokenize  # noqa: E402


def main() -> None:
    corpus = ROOT / "data/item7_corpus"
    manifest = pd.read_csv(corpus / "manifest.csv", dtype=str).fillna("")
    tone = pd.read_csv(ROOT / "data/metadata/tone_method_item7.csv", dtype=str)
    tone = tone.set_index(["ticker", "filing_date"])
    dictionary = load_lm()
    errors: list[dict[str, str]] = []
    verified = manifest[manifest["status"] == "verified"]
    token_total = 0
    for _, row in verified.iterrows():
        key = (row["ticker"], row["filing_date"])
        accession = row["accession_number"].replace("-", "")
        section = ROOT / "data/sections_v3/10k" / row["ticker"] / accession / "item_7_mda.txt"
        terms = corpus / "terms" / row["ticker"] / f"{accession}.csv.gz"
        if not section.is_file() or not terms.is_file() or key not in tone.index:
            errors.append({"key": str(key), "reason": "missing section, term file, or tone row"})
            continue
        tokens = tokenize(section.read_text(encoding="utf-8"))
        token_total += len(tokens)
        with gzip.open(terms, "rt", encoding="utf-8", newline="") as stream:
            rows = csv.DictReader(stream)
            saved = Counter({entry["term"]: int(entry["count"]) for entry in rows})
        if Counter(tokens) != saved:
            errors.append({"key": str(key), "reason": "term counts differ from Item 7"})
        if len(tokens) != int(float(row["item7_tokens"])):
            errors.append({"key": str(key), "reason": "manifest token count mismatch"})

        lm = tone.loc[key]
        counts, neg_pos, neg_neg = sentiment_counts(
            tokens, dictionary["positive"], dictionary["negative"]
        )
        observed = {
            "lm_total_words": len(tokens),
            "lm_positive_count": sum(v for (kind, _), v in counts.items() if kind == "positive"),
            "lm_negative_count": sum(v for (kind, _), v in counts.items() if kind == "negative"),
            "lm_negated_positive_count": neg_pos,
            "lm_negated_negative_count": neg_neg,
        }
        for column, value in observed.items():
            if value != int(float(lm[column])):
                errors.append({"key": str(key), "reason": f"{column}: {value} != {lm[column]}"})

    aggregate_rows = 0
    if not errors:
        aggregate = corpus / "item7_term_counts.csv.gz"
        temporary = corpus / "item7_term_counts.csv.gz.part"
        with gzip.open(temporary, "wt", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["ticker", "filing_date", "accession_number", "term", "count"])
            for _, row in verified.sort_values(["ticker", "filing_date"]).iterrows():
                accession = row["accession_number"].replace("-", "")
                terms = corpus / "terms" / row["ticker"] / f"{accession}.csv.gz"
                with gzip.open(terms, "rt", encoding="utf-8", newline="") as source:
                    for entry in csv.DictReader(source):
                        writer.writerow([row["ticker"], row["filing_date"],
                                         row["accession_number"], entry["term"], entry["count"]])
                        aggregate_rows += 1
        temporary.replace(aggregate)

    report = {
        "manifest_rows": len(manifest),
        "verified_item7": len(verified),
        "excluded_invalid_item7": int((manifest["status"] == "no_valid_item7").sum()),
        "token_total": token_total,
        "term_rows": aggregate_rows,
        "checks": ["per-word frequency", "total words", "LM positive", "LM negative", "A1 negated positive", "A1 negated negative"],
        "mismatch_count": len(errors),
        "first_mismatches": errors[:20],
    }
    output = corpus / "verification.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
