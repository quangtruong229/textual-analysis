#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fast SEC Company Facts profiler for the 1,000-filing Accruals project.

Why this version exists
-----------------------
The previous profiler converted every Company Facts observation to pandas
Timestamp objects while flattening the entire JSON. SEC Company Facts files
can contain a very large number of observations, so this caused unnecessary
CPU/RAM usage and made the profiling step look "stuck".

This version:
    - keeps SEC dates as ISO strings (YYYY-MM-DD) for comparison;
    - does NOT call pd.to_datetime() for every XBRL fact;
    - does NOT coerce every value through pandas numeric conversion;
    - keeps only candidate concepts needed for Accruals discovery;
    - indexes candidate facts by (concept, end) for fast filing-level lookup;
    - produces one clean coverage row per filing.

It DOES NOT calculate Accruals.
It only profiles the XBRL structure so we can build robust mapping rules.

Outputs
-------
data/metadata/controls/accrual_profile/
    company_structure.csv
    concept_inventory.csv
    filing_coverage.csv
    filing_candidate_facts.csv
    target_concept_usage.csv
    profiling_summary.txt

Run
---
python src/profile_accrual_inputs.py
python src/profile_accrual_inputs.py --ticker A
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_FILINGS = ROOT / "data" / "metadata" / "filings_2016_2025.csv"
DEFAULT_CACHE = ROOT / "data" / "metadata" / "controls" / "sec_facts_cache"
DEFAULT_OUT = ROOT / "data" / "metadata" / "controls" / "accrual_profile"


TARGET_FIELDS = {
    "current_assets": [
        "AssetsCurrent",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashAndCashEquivalentsAtCarryingValueIncludingDiscontinuedOperations",
    ],
    "current_liabilities": [
        "LiabilitiesCurrent",
    ],
    "current_debt": [
        "DebtCurrent",
        "LongTermDebtCurrent",
        "CurrentPortionOfLongTermDebt",
        "CurrentPortionOfLongTermDebtAndFinanceLeaseObligations",
        "ShortTermBorrowings",
        "CommercialPaper",
        "FinanceLeaseLiabilityCurrent",
        "NotesPayableCurrent",
    ],
    "taxes_payable": [
        "TaxesPayableCurrent",
        "AccruedIncomeTaxesCurrent",
        "IncomeTaxesPayableCurrent",
    ],
    "total_assets": [
        "Assets",
    ],
    "depreciation": [
        "Depreciation",
        "DepreciationPropertyPlantAndEquipment",
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
    ],
}


CANDIDATE_RE = re.compile(
    r"(?:asset|cash|liabilit|debt|borrow|commercialpaper|"
    r"note.?payable|tax|income.?tax|depreci|amort|lease|accru|payable)",
    re.IGNORECASE,
)

ANCHORS = {
    "AssetsCurrent",
    "CashAndCashEquivalentsAtCarryingValue",
    "LiabilitiesCurrent",
    "Assets",
}

TARGET_CONCEPTS = {
    concept
    for concepts in TARGET_FIELDS.values()
    for concept in concepts
}


def norm_cik(value: Any) -> str:
    s = str(value).strip()
    s = re.sub(r"\.0$", "", s)
    return s.zfill(10)


def norm_date_str(value: Any) -> str:
    """
    SEC Company Facts dates are normally YYYY-MM-DD.
    Keep them as strings to avoid expensive per-observation datetime parsing.
    """
    if value is None:
        return ""

    s = str(value).strip()

    # Normal SEC ISO date.
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]

    # Conservative fallback for unexpected strings.
    try:
        return pd.Timestamp(s).strftime("%Y-%m-%d")
    except Exception:
        return ""


def norm_filing_date_series(series: pd.Series) -> pd.Series:
    # We only have ~1,000 filing metadata rows, so pandas conversion here is cheap.
    dt = pd.to_datetime(series, errors="coerce")
    return dt.dt.strftime("%Y-%m-%d")


def load_company_facts_fast(path: Path) -> tuple[
    dict[tuple[str, str], list[dict[str, Any]]],
    set[str],
    set[str],
    int,
]:
    """
    Load only candidate concepts, preserving custom namespaces.

    Returns
    -------
    index:
        keyed by (concept, end_date), value = list of fact dictionaries.
    all_concepts:
        all concepts declared in the Company Facts file.
    namespaces:
        namespaces present in the file.
    raw_observation_count:
        count of all observations in all units.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    facts_root = payload.get("facts", {})

    index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    all_concepts: set[str] = set()
    namespaces: set[str] = set()
    raw_obs = 0

    for namespace, namespace_facts in facts_root.items():
        namespaces.add(str(namespace))

        for concept, meta in namespace_facts.items():
            concept = str(concept)
            all_concepts.add(concept)

            # Only retain observations for:
            #   1) explicit target concepts, OR
            #   2) candidate concepts discovered by name.
            is_candidate = (
                concept in TARGET_CONCEPTS
                or CANDIDATE_RE.search(concept) is not None
            )

            units = meta.get("units", {})
            for unit, values in units.items():
                if not isinstance(values, list):
                    continue

                raw_obs += len(values)

                if not is_candidate:
                    continue

                unit = str(unit)

                for v in values:
                    if not isinstance(v, dict):
                        continue

                    end = norm_date_str(v.get("end"))
                    filed = norm_date_str(v.get("filed"))

                    if not end:
                        continue

                    rec = {
                        "namespace": str(namespace),
                        "concept": concept,
                        "unit": unit,
                        "val": v.get("val"),
                        "start": norm_date_str(v.get("start")),
                        "end": end,
                        "filed": filed,
                        "form": str(v.get("form", "")),
                        "fy": v.get("fy"),
                        "fp": v.get("fp"),
                        "accn": str(v.get("accn", "")),
                        "frame": str(v.get("frame", "")),
                    }

                    index[(concept, end)].append(rec)

    # Deterministic order and easy "latest admissible" selection.
    for key in index:
        index[key].sort(
            key=lambda x: (
                x.get("filed", ""),
                x.get("form", ""),
                x.get("fp", ""),
            ),
            reverse=True,
        )

    return index, all_concepts, namespaces, raw_obs


def choose_best_fact(
    facts: list[dict[str, Any]],
    filing_date: str,
) -> dict[str, Any] | None:
    """
    Choose the best admissible fact for one concept/end date.

    Ranking mirrors build_accruals.py:
        10-K + FY > 10-K > everything else,
    then latest filed observation available as of the filing.
    """
    admissible = [
        f for f in facts
        if f.get("filed", "") and f["filed"] <= filing_date
    ]

    if not admissible:
        return None

    def rank(f: dict[str, Any]) -> tuple[int, str]:
        form = str(f.get("form", "")).upper()
        fp = str(f.get("fp", "")).upper()

        if form == "10-K" and fp == "FY":
            r = 0
        elif form == "10-K/A" and fp == "FY":
            r = 1
        elif form == "10-K":
            r = 2
        elif form == "10-K/A":
            r = 3
        else:
            r = 4

        return r, f.get("filed", "")

    return sorted(
        admissible,
        key=lambda f: rank(f),
    )[0]


def admissible_target_facts(
    index: dict[tuple[str, str], list[dict[str, Any]]],
    concepts: list[str],
    end_date: str,
    filing_date: str,
) -> list[dict[str, Any]]:
    if not end_date:
        return []

    result: list[dict[str, Any]] = []

    for concept in concepts:
        rows = index.get((concept, end_date), [])
        best = choose_best_fact(rows, filing_date)
        if best is not None:
            result.append(best)

    return result


def choose_prior_fiscal_end(
    index: dict[tuple[str, str], list[dict[str, Any]]],
    current_end: str,
    filing_date: str,
) -> str:
    """
    Choose one common prior fiscal end.

    Strict preference:
        annual 10-K/10-KA with FY
        -> annual 10-K/10-KA
        -> no fallback to arbitrary non-annual observations.

    A candidate prior end is considered supported when >=2 anchor concepts
    are available by the current filing date.
    """
    if not current_end or not filing_date:
        return ""

    date_support: dict[str, set[str]] = defaultdict(set)

    for concept in ANCHORS:
        # Inspect all end dates available for this concept.
        for (c, end), rows in index.items():
            if c != concept:
                continue
            if not end or end >= current_end:
                continue

            for fact in rows:
                if fact.get("filed", "") > filing_date:
                    continue

                form = str(fact.get("form", "")).upper()
                fp = str(fact.get("fp", "")).upper()

                # Prefer annual facts for the primary candidate set.
                if form in {"10-K", "10-K/A"} and fp == "FY":
                    date_support[end].add(concept)
                    break

    supported = [
        end for end, concepts in date_support.items()
        if len(concepts) >= 2
    ]

    if supported:
        return max(supported)

    # Second pass: annual form even if fp is missing/non-FY.
    date_support.clear()

    for concept in ANCHORS:
        for (c, end), rows in index.items():
            if c != concept:
                continue
            if not end or end >= current_end:
                continue

            for fact in rows:
                if fact.get("filed", "") > filing_date:
                    continue

                form = str(fact.get("form", "")).upper()
                if form in {"10-K", "10-K/A"}:
                    date_support[end].add(concept)
                    break

    supported = [
        end for end, concepts in date_support.items()
        if len(concepts) >= 2
    ]

    return max(supported) if supported else ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fast SEC Company Facts profiling for Accruals mapping."
    )
    parser.add_argument(
        "--filings",
        type=str,
        default=str(DEFAULT_FILINGS),
    )
    parser.add_argument(
        "--cache",
        type=str,
        default=str(DEFAULT_CACHE),
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(DEFAULT_OUT),
    )
    parser.add_argument(
        "--ticker",
        type=str,
        default=None,
    )
    args = parser.parse_args()

    filings_path = Path(args.filings)
    cache_dir = Path(args.cache)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    filings = pd.read_csv(filings_path, dtype=str)

    filings["ticker"] = filings["ticker"].astype(str).str.upper()
    filings["cik"] = filings["cik"].map(norm_cik)
    filings["filing_date"] = norm_filing_date_series(filings["filing_date"])
    filings["report_date"] = norm_filing_date_series(filings["report_date"])

    if args.ticker:
        filings = filings[
            filings["ticker"].eq(args.ticker.upper())
        ].copy()

    if filings.empty:
        raise SystemExit("No filings matched the filter.")

    cache_paths = {
        norm_cik(p.stem.replace("CIK", "")): p
        for p in cache_dir.glob("CIK*.json")
    }

    company_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []

    # (cik, concept) -> company presence
    concept_company_counter: Counter[tuple[str, str]] = Counter()

    # (field, concept, period) -> number of filing observations
    target_usage_counter: Counter[tuple[str, str, str]] = Counter()

    # discovery concept -> number of filing contexts
    discovery_counter: Counter[str] = Counter()

    total = len(filings)
    processed = 0

    # Process only companies appearing in the selected filing sample.
    for cik, company_filings in filings.groupby("cik", sort=True):
        path = cache_paths.get(cik)

        if path is None:
            company_rows.append({
                "cik": cik,
                "cache_file": "",
                "facts_rows_all": 0,
                "unique_concepts_all": 0,
                "candidate_concepts": 0,
                "namespaces": "",
                "error": "cache not found",
            })

            for _, filing in company_filings.iterrows():
                coverage_rows.append({
                    "ticker": filing["ticker"],
                    "cik": cik,
                    "filing_date": filing["filing_date"],
                    "report_date": filing["report_date"],
                    "prior_fiscal_end": "",
                    "cache_available": 0,
                    **{
                        f"{field}_current_available": 0
                        for field in TARGET_FIELDS
                    },
                    **{
                        f"{field}_prior_available": 0
                        for field in TARGET_FIELDS
                    },
                })

            continue

        try:
            (
                index,
                all_concepts,
                namespaces,
                raw_obs,
            ) = load_company_facts_fast(path)
        except Exception as exc:
            company_rows.append({
                "cik": cik,
                "cache_file": str(path),
                "facts_rows_all": 0,
                "unique_concepts_all": 0,
                "candidate_concepts": 0,
                "namespaces": "",
                "error": repr(exc),
            })
            continue

        candidate_concepts = sorted({
            concept
            for concept, _end in index.keys()
        })

        for concept in all_concepts:
            concept_company_counter[(cik, concept)] = 1

        company_rows.append({
            "cik": cik,
            "cache_file": str(path),
            "facts_rows_all": raw_obs,
            "unique_concepts_all": len(all_concepts),
            "candidate_concepts": len(candidate_concepts),
            "namespaces": "|".join(sorted(namespaces)),
            "error": "",
        })

        company_filings = company_filings.sort_values(
            ["filing_date", "report_date"]
        )

        for _, filing in company_filings.iterrows():
            processed += 1

            ticker = filing["ticker"]
            filing_date = filing["filing_date"]
            report_date = filing["report_date"]

            prior_end = choose_prior_fiscal_end(
                index,
                report_date,
                filing_date,
            )

            coverage = {
                "ticker": ticker,
                "cik": cik,
                "filing_date": filing_date,
                "report_date": report_date,
                "prior_fiscal_end": prior_end,
                "cache_available": 1,
            }

            for field, concepts in TARGET_FIELDS.items():
                current_facts = admissible_target_facts(
                    index,
                    concepts,
                    report_date,
                    filing_date,
                )

                prior_facts = admissible_target_facts(
                    index,
                    concepts,
                    prior_end,
                    filing_date,
                )

                coverage[f"{field}_current_available"] = int(
                    bool(current_facts)
                )
                coverage[f"{field}_prior_available"] = int(
                    bool(prior_facts)
                )

                for period, facts_for_period in (
                    ("current", current_facts),
                    ("prior", prior_facts),
                ):
                    for fact in facts_for_period:
                        target_usage_counter[
                            (field, fact["concept"], period)
                        ] += 1

                        candidate_rows.append({
                            "ticker": ticker,
                            "cik": cik,
                            "filing_date": filing_date,
                            "report_date": report_date,
                            "prior_fiscal_end": prior_end,
                            "target": field,
                            "period": period,
                            **fact,
                        })

            # Discovery: candidate concepts outside current whitelist.
            # Use only the filing's current/prior end dates and admissible
            # filing date.
            discovery_seen_this_filing: set[str] = set()

            for end_date, period in (
                (report_date, "current"),
                (prior_end, "prior"),
            ):
                if not end_date:
                    continue

                for (concept, end), rows in index.items():
                    if end != end_date:
                        continue
                    if concept in TARGET_CONCEPTS:
                        continue

                    best = choose_best_fact(rows, filing_date)
                    if best is None:
                        continue

                    if concept in discovery_seen_this_filing:
                        continue

                    discovery_seen_this_filing.add(concept)
                    discovery_counter[concept] += 1

                    candidate_rows.append({
                        "ticker": ticker,
                        "cik": cik,
                        "filing_date": filing_date,
                        "report_date": report_date,
                        "prior_fiscal_end": prior_end,
                        "target": "DISCOVERY",
                        "period": period,
                        **best,
                    })

            coverage_rows.append(coverage)

            # Lightweight progress output: once per filing, not once per fact.
            if processed == 1 or processed % 100 == 0 or processed == total:
                print(
                    f"[{processed:>4}/{total:>4}] "
                    f"{ticker} {report_date} "
                    f"prior={prior_end or 'NA'}"
                )

    # ------------------------------------------------------------------
    # Write outputs
    # ------------------------------------------------------------------

    coverage_df = pd.DataFrame(coverage_rows)
    coverage_df.to_csv(
        out_dir / "filing_coverage.csv",
        index=False,
        encoding="utf-8-sig",
    )

    candidate_df = pd.DataFrame(candidate_rows)
    candidate_df.to_csv(
        out_dir / "filing_candidate_facts.csv",
        index=False,
        encoding="utf-8-sig",
    )

    concept_inventory_df = pd.DataFrame(
        [
            {
                "cik": cik,
                "concept": concept,
            }
            for (cik, concept) in sorted(concept_company_counter.keys())
        ]
    )

    if not concept_inventory_df.empty:
        concept_summary = (
            concept_inventory_df.groupby("concept")
            .agg(
                companies=("cik", "nunique"),
            )
            .reset_index()
            .sort_values(
                ["companies", "concept"],
                ascending=[False, True],
            )
        )
    else:
        concept_summary = pd.DataFrame(
            columns=["concept", "companies"]
        )

    concept_summary.to_csv(
        out_dir / "concept_inventory.csv",
        index=False,
        encoding="utf-8-sig",
    )

    company_structure_df = pd.DataFrame(company_rows)
    company_structure_df.to_csv(
        out_dir / "company_structure.csv",
        index=False,
        encoding="utf-8-sig",
    )

    usage_rows = [
        {
            "target": field,
            "concept": concept,
            "period": period,
            "filings": count,
        }
        for (field, concept, period), count
        in sorted(target_usage_counter.items())
    ]

    pd.DataFrame(usage_rows).to_csv(
        out_dir / "target_concept_usage.csv",
        index=False,
        encoding="utf-8-sig",
    )

    discovery_rows = [
        {
            "concept": concept,
            "filing_contexts": count,
        }
        for concept, count
        in discovery_counter.most_common()
    ]

    pd.DataFrame(discovery_rows).to_csv(
        out_dir / "discovery_concepts.csv",
        index=False,
        encoding="utf-8-sig",
    )

    summary = [
        "SEC ACCRUAL INPUT PROFILING COMPLETE",
        f"Filings profiled: {len(filings)}",
        f"Companies profiled: {filings['cik'].nunique()}",
        f"Cache files available: {len(cache_paths)}",
        f"Candidate fact rows written: {len(candidate_df)}",
        f"Unique concepts in inventory: {len(concept_summary)}",
        "",
        "Files:",
        "  company_structure.csv",
        "  concept_inventory.csv",
        "  filing_coverage.csv",
        "  filing_candidate_facts.csv",
        "  target_concept_usage.csv",
        "  discovery_concepts.csv",
        "  profiling_summary.txt",
        "",
        "Important:",
        "  filing_coverage.csv contains exactly one row per selected filing.",
        "  Dates are handled as ISO strings to avoid expensive per-fact datetime parsing.",
        "  Candidate facts obey fact.filed <= filing.filing_date.",
    ]

    (out_dir / "profiling_summary.txt").write_text(
        "\n".join(summary) + "\n",
        encoding="utf-8",
    )

    print("\n" + "=" * 80)
    print("SEC ACCRUAL INPUT PROFILING COMPLETE")
    print("=" * 80)
    for line in summary:
        print(line)
    print(f"Saved to: {out_dir}")


if __name__ == "__main__":
    main()
