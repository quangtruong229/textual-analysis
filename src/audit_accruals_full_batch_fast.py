#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import json
import re
from functools import lru_cache

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ACCRUALS = ROOT / "data" / "metadata" / "controls" / "accruals_item7.csv"
CACHE_DIR = ROOT / "data" / "metadata" / "controls" / "sec_facts_cache"
OUT_DIR = ROOT / "data" / "metadata" / "controls" / "accruals_qa"

DEBT_PAT = re.compile(
    r"(debt|borrow|commercialpaper|notespayable|creditfacility|financelease|"
    r"capitallease|shortterm|currentportion|maturit)",
    re.I,
)
DA_PAT = re.compile(r"(depreci|amorti|depletion)", re.I)


def norm_cik(x):
    s = str(x)
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(10)


def date_str(x):
    """Normalize a pandas/CSV date-like value to YYYY-MM-DD without repeated parsing."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ""
    s = str(x).strip()
    if not s or s.lower() == "nan":
        return ""
    return s[:10]


@lru_cache(maxsize=None)
def load_relevant_facts(cik):
    """
    Read one Company Facts JSON once and pre-flatten only debt/D&A-relevant US-GAAP facts.
    This avoids repeatedly calling pd.to_datetime inside millions of inner-loop iterations.
    """
    p = CACHE_DIR / f"CIK{norm_cik(cik)}.json"
    if not p.exists():
        return [], []

    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return [], []

    debt_rows = []
    da_rows = []

    facts = payload.get("facts", {}).get("us-gaap", {})
    for concept, meta in facts.items():
        is_debt = bool(DEBT_PAT.search(concept))
        is_da = bool(DA_PAT.search(concept))
        if not is_debt and not is_da:
            continue

        for unit, vals in meta.get("units", {}).items():
            for v in vals:
                end = str(v.get("end", "") or "")
                if not end:
                    continue

                val = v.get("val")
                try:
                    val = float(val)
                except (TypeError, ValueError):
                    continue

                row = {
                    "concept": concept,
                    "unit": unit,
                    "value": val,
                    "start": str(v.get("start", "") or ""),
                    "end": end[:10],
                    "filed": str(v.get("filed", "") or ""),
                    "form": str(v.get("form", "") or ""),
                    "fy": v.get("fy", ""),
                    "fp": v.get("fp", ""),
                    "accn": str(v.get("accn", "") or ""),
                    "frame": str(v.get("frame", "") or ""),
                }

                if is_debt:
                    debt_rows.append(row)
                if is_da:
                    da_rows.append(row)

    return debt_rows, da_rows


def facts_for_end(rows, target_end):
    target = date_str(target_end)
    if not target:
        return []
    return [r for r in rows if r["end"] == target]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading accruals output...", flush=True)
    df = pd.read_csv(ACCRUALS, dtype={"cik": str})

    # Basic QA splits.
    firm_status = (
        df.groupby(["ticker", "status"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    firm_status.to_csv(OUT_DIR / "firm_status_matrix.csv", index=False)

    warn = df[df["status"].eq("WARN")].copy()
    warn.to_csv(OUT_DIR / "warn_rows.csv", index=False)

    structural = df[df["status"].eq("STRUCTURAL_MISSING")].copy()
    structural.to_csv(OUT_DIR / "structural_missing_rows.csv", index=False)

    numeric_warn = warn[warn["accruals"].notna()].copy()
    numeric_warn.to_csv(OUT_DIR / "numeric_warn_rows.csv", index=False)

    debt_missing = df[
        df["current_ltd"].isna() | df["prior_current_ltd"].isna()
    ].copy()
    debt_missing.to_csv(OUT_DIR / "debt_missing_rows.csv", index=False)

    dep_problem = df[
        df["depreciation_quality"].isin(["PURE_DEP_FALLBACK", "MISSING"])
    ].copy()
    dep_problem.to_csv(OUT_DIR / "depreciation_problem_rows.csv", index=False)

    # Preload each CIK once.
    ciks = sorted(
        set(debt_missing["cik"].map(norm_cik))
        | set(dep_problem["cik"].map(norm_cik))
    )

    print(f"Preloading relevant SEC facts for {len(ciks)} CIK(s)...", flush=True)
    for i, cik in enumerate(ciks, start=1):
        load_relevant_facts(cik)
        if i % 10 == 0 or i == len(ciks):
            print(f"  cached {i}/{len(ciks)}", flush=True)

    # Debt candidate audit.
    print(f"Auditing {len(debt_missing)} debt-missing rows...", flush=True)
    candidate_rows = []

    for n, (_, r) in enumerate(debt_missing.iterrows(), start=1):
        cik = norm_cik(r["cik"])
        debt_rows, _ = load_relevant_facts(cik)

        targets = [
            ("current_ltd", r.get("report_date"), r.get("current_ltd")),
            ("prior_current_ltd", r.get("prior_fiscal_end"), r.get("prior_current_ltd")),
        ]

        for side, target_end, existing in targets:
            if pd.notna(existing):
                continue

            facts = facts_for_end(debt_rows, target_end)
            if not facts:
                candidate_rows.append({
                    "ticker": r["ticker"],
                    "cik": cik,
                    "filing_date": r.get("filing_date", ""),
                    "report_date": r.get("report_date", ""),
                    "side": side,
                    "target_end": date_str(target_end),
                    "candidate_concept": "",
                    "value": np.nan,
                    "filed": "",
                    "form": "",
                    "accn": "",
                })
            else:
                for f in facts:
                    candidate_rows.append({
                        "ticker": r["ticker"],
                        "cik": cik,
                        "filing_date": r.get("filing_date", ""),
                        "report_date": r.get("report_date", ""),
                        "side": side,
                        "target_end": date_str(target_end),
                        "candidate_concept": f["concept"],
                        "value": f["value"],
                        "filed": f["filed"],
                        "form": f["form"],
                        "accn": f["accn"],
                    })

        if n % 50 == 0 or n == len(debt_missing):
            print(f"  debt rows {n}/{len(debt_missing)}", flush=True)

    pd.DataFrame(candidate_rows).to_csv(
        OUT_DIR / "debt_candidate_concepts.csv",
        index=False,
    )

    # D&A candidate audit.
    print(f"Auditing {len(dep_problem)} depreciation-problem rows...", flush=True)
    dep_candidates = []

    for n, (_, r) in enumerate(dep_problem.iterrows(), start=1):
        cik = norm_cik(r["cik"])
        _, da_rows = load_relevant_facts(cik)
        facts = facts_for_end(da_rows, r.get("report_date"))

        if not facts:
            dep_candidates.append({
                "ticker": r["ticker"],
                "cik": cik,
                "filing_date": r.get("filing_date", ""),
                "report_date": r.get("report_date", ""),
                "depreciation_quality": r["depreciation_quality"],
                "candidate_concept": "",
                "value": np.nan,
                "start": "",
                "end": "",
                "filed": "",
                "form": "",
                "accn": "",
            })
        else:
            for f in facts:
                dep_candidates.append({
                    "ticker": r["ticker"],
                    "cik": cik,
                    "filing_date": r.get("filing_date", ""),
                    "report_date": r.get("report_date", ""),
                    "depreciation_quality": r["depreciation_quality"],
                    "candidate_concept": f["concept"],
                    "value": f["value"],
                    "start": f["start"],
                    "end": f["end"],
                    "filed": f["filed"],
                    "form": f["form"],
                    "accn": f["accn"],
                })

        if n % 50 == 0 or n == len(dep_problem):
            print(f"  depreciation rows {n}/{len(dep_problem)}", flush=True)

    pd.DataFrame(dep_candidates).to_csv(
        OUT_DIR / "depreciation_candidate_concepts.csv",
        index=False,
    )

    print()
    print("=" * 88)
    print("ACCRUALS QA TRIAGE COMPLETE")
    print("=" * 88)
    print(f"Rows total                : {len(df)}")
    print(f"PASS                      : {(df['status'] == 'PASS').sum()}")
    print(f"WARN                      : {(df['status'] == 'WARN').sum()}")
    print(f"STRUCTURAL_MISSING        : {(df['status'] == 'STRUCTURAL_MISSING').sum()}")
    print(f"Numeric accruals          : {df['accruals'].notna().sum()}")
    print(f"Numeric WARN              : {len(numeric_warn)}")
    print(f"Debt-missing rows         : {len(debt_missing)}")
    print(f"Dep fallback/missing rows : {len(dep_problem)}")

    print("\nFirms with most WARN rows:")
    if len(warn):
        print(
            warn.groupby("ticker")
            .size()
            .sort_values(ascending=False)
            .head(20)
            .to_string()
        )

    print("\nFirms with most STRUCTURAL_MISSING rows:")
    if len(structural):
        print(
            structural.groupby("ticker")
            .size()
            .sort_values(ascending=False)
            .head(20)
            .to_string()
        )

    print(f"\nSaved QA files under: {OUT_DIR}")


if __name__ == "__main__":
    main()
