#!/usr/bin/env python3
from pathlib import Path
import json, re
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ACCRUALS = ROOT / "data" / "metadata" / "controls" / "accruals_item7.csv"
CACHE_DIR = ROOT / "data" / "metadata" / "controls" / "sec_facts_cache"
OUT_DIR = ROOT / "data" / "metadata" / "controls" / "accruals_qa"

DEBT_PAT = re.compile(r"(debt|borrow|commercialpaper|notespayable|creditfacility|financelease|capitallease|shortterm|currentportion|maturit)", re.I)
DA_PAT = re.compile(r"(depreci|amorti|depletion)", re.I)

def norm_cik(x):
    s = str(x)
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(10)

def load_companyfacts(cik):
    p = CACHE_DIR / f"CIK{norm_cik(cik)}.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def facts_at_end(payload, target_end, pattern):
    target_end = pd.to_datetime(target_end, errors="coerce")
    if pd.isna(target_end):
        return []
    out = []
    facts = payload.get("facts", {}).get("us-gaap", {})
    for concept, meta in facts.items():
        if not pattern.search(concept):
            continue
        for unit, vals in meta.get("units", {}).items():
            for v in vals:
                end = pd.to_datetime(v.get("end"), errors="coerce")
                if pd.isna(end) or end != target_end:
                    continue
                val = pd.to_numeric(v.get("val"), errors="coerce")
                if pd.isna(val):
                    continue
                out.append({
                    "concept": concept, "value": val, "start": v.get("start",""),
                    "end": v.get("end",""), "filed": v.get("filed",""),
                    "form": v.get("form",""), "accn": v.get("accn","")
                })
    return out

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(ACCRUALS, dtype={"cik": str})

    firm_status = df.groupby(["ticker","status"]).size().unstack(fill_value=0).reset_index()
    firm_status.to_csv(OUT_DIR / "firm_status_matrix.csv", index=False)

    warn = df[df["status"].eq("WARN")].copy()
    warn.to_csv(OUT_DIR / "warn_rows.csv", index=False)

    structural = df[df["status"].eq("STRUCTURAL_MISSING")].copy()
    structural.to_csv(OUT_DIR / "structural_missing_rows.csv", index=False)

    numeric_warn = warn[warn["accruals"].notna()].copy()
    numeric_warn.to_csv(OUT_DIR / "numeric_warn_rows.csv", index=False)

    debt_missing = df[df["current_ltd"].isna() | df["prior_current_ltd"].isna()].copy()
    debt_missing.to_csv(OUT_DIR / "debt_missing_rows.csv", index=False)

    candidate_rows = []
    for _, r in debt_missing.iterrows():
        payload = load_companyfacts(r["cik"])
        for side, target_end in [("current_ltd", r.get("report_date")), ("prior_current_ltd", r.get("prior_fiscal_end"))]:
            if side == "current_ltd" and pd.notna(r.get("current_ltd")):
                continue
            if side == "prior_current_ltd" and pd.notna(r.get("prior_current_ltd")):
                continue
            facts = facts_at_end(payload, target_end, DEBT_PAT)
            if not facts:
                candidate_rows.append({
                    "ticker": r["ticker"], "cik": norm_cik(r["cik"]), "filing_date": r["filing_date"],
                    "report_date": r["report_date"], "side": side, "target_end": target_end,
                    "candidate_concept": "", "value": np.nan, "filed": "", "form": "", "accn": ""
                })
            else:
                for f in facts:
                    candidate_rows.append({
                        "ticker": r["ticker"], "cik": norm_cik(r["cik"]), "filing_date": r["filing_date"],
                        "report_date": r["report_date"], "side": side, "target_end": target_end,
                        "candidate_concept": f["concept"], "value": f["value"],
                        "filed": f["filed"], "form": f["form"], "accn": f["accn"]
                    })
    pd.DataFrame(candidate_rows).to_csv(OUT_DIR / "debt_candidate_concepts.csv", index=False)

    dep_problem = df[df["depreciation_quality"].isin(["PURE_DEP_FALLBACK","MISSING"])].copy()
    dep_problem.to_csv(OUT_DIR / "depreciation_problem_rows.csv", index=False)

    dep_candidates = []
    for _, r in dep_problem.iterrows():
        payload = load_companyfacts(r["cik"])
        facts = facts_at_end(payload, r["report_date"], DA_PAT)
        if not facts:
            dep_candidates.append({
                "ticker": r["ticker"], "cik": norm_cik(r["cik"]), "filing_date": r["filing_date"],
                "report_date": r["report_date"], "depreciation_quality": r["depreciation_quality"],
                "candidate_concept": "", "value": np.nan, "start": "", "end": "", "filed": "", "form": "", "accn": ""
            })
        else:
            for f in facts:
                dep_candidates.append({
                    "ticker": r["ticker"], "cik": norm_cik(r["cik"]), "filing_date": r["filing_date"],
                    "report_date": r["report_date"], "depreciation_quality": r["depreciation_quality"],
                    "candidate_concept": f["concept"], "value": f["value"], "start": f["start"], "end": f["end"],
                    "filed": f["filed"], "form": f["form"], "accn": f["accn"]
                })
    pd.DataFrame(dep_candidates).to_csv(OUT_DIR / "depreciation_candidate_concepts.csv", index=False)

    print("="*88)
    print("ACCRUALS QA TRIAGE COMPLETE")
    print("="*88)
    print(f"Rows total                : {len(df)}")
    print(f"PASS                      : {(df['status']=='PASS').sum()}")
    print(f"WARN                      : {(df['status']=='WARN').sum()}")
    print(f"STRUCTURAL_MISSING        : {(df['status']=='STRUCTURAL_MISSING').sum()}")
    print(f"Numeric accruals          : {df['accruals'].notna().sum()}")
    print(f"Numeric WARN              : {len(numeric_warn)}")
    print(f"Debt-missing rows         : {len(debt_missing)}")
    print(f"Dep fallback/missing rows : {len(dep_problem)}")
    print("\nFirms with most WARN rows:")
    print(warn.groupby("ticker").size().sort_values(ascending=False).head(20).to_string())
    print("\nFirms with most STRUCTURAL_MISSING rows:")
    print(structural.groupby("ticker").size().sort_values(ascending=False).head(20).to_string())
    print(f"\nSaved QA files under: {OUT_DIR}")

if __name__ == "__main__":
    main()
