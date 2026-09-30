from pathlib import Path
import pandas as pd

FAILURES = Path("data/controls/eadret_item7_failures.csv")
CACHE_DIR = Path("data/metadata/controls/sec_submissions_cache")
OUT = Path("data/controls/eadret_item7_failure_audit.csv")

def norm_cik(v):
    s = str(v)
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(10)

def has_item_202(v):
    if pd.isna(v):
        return False
    return any(x.strip() == "2.02" for x in str(v).split(","))

rows = []
fail = pd.read_csv(FAILURES, dtype={"tenk_accession": str})

for _, r in fail.iterrows():
    cik = norm_cik(r["cik"])
    cache = CACHE_DIR / f"CIK{cik}.csv"
    tenk_date = pd.to_datetime(r["tenk_filing_date"], errors="coerce")
    tenk_accept = pd.to_datetime(r.get("tenk_acceptance_datetime_utc"), utc=True, errors="coerce")

    if not cache.exists():
        rows.append({
            "ticker": r["ticker"],
            "cik": cik,
            "tenk_filing_date": r["tenk_filing_date"],
            "tenk_accession": r["tenk_accession"],
            "candidate_accession": "",
            "candidate_filing_date": "",
            "candidate_acceptance": "",
            "items": "",
            "days_from_10k": "",
            "relation_to_10k_acceptance": "",
            "audit_note": "SEC cache missing",
        })
        continue

    x = pd.read_csv(cache, dtype={"accessionNumber": str})
    x["filingDate"] = pd.to_datetime(x["filingDate"], errors="coerce")
    x["acceptance_utc"] = pd.to_datetime(x.get("acceptanceDateTime"), utc=True, errors="coerce")

    cand = x[
        x["form"].astype(str).str.upper().eq("8-K")
        & x["filingDate"].notna()
        & x["items"].map(has_item_202)
        & (x["filingDate"] >= tenk_date - pd.Timedelta(days=400))
        & (x["filingDate"] <= tenk_date + pd.Timedelta(days=10))
    ].copy()

    if cand.empty:
        rows.append({
            "ticker": r["ticker"],
            "cik": cik,
            "tenk_filing_date": r["tenk_filing_date"],
            "tenk_accession": r["tenk_accession"],
            "candidate_accession": "",
            "candidate_filing_date": "",
            "candidate_acceptance": "",
            "items": "",
            "days_from_10k": "",
            "relation_to_10k_acceptance": "",
            "audit_note": "No Item 2.02 candidate within -400/+10 days",
        })
        continue

    cand = cand.sort_values(["filingDate", "acceptance_utc"])
    for _, c in cand.iterrows():
        relation = ""
        if pd.notna(c["acceptance_utc"]) and pd.notna(tenk_accept):
            if c["acceptance_utc"] < tenk_accept:
                relation = "before_10k_acceptance"
            elif c["acceptance_utc"] == tenk_accept:
                relation = "same_as_10k_acceptance"
            else:
                relation = "after_10k_acceptance"

        rows.append({
            "ticker": r["ticker"],
            "cik": cik,
            "tenk_filing_date": r["tenk_filing_date"],
            "tenk_accession": r["tenk_accession"],
            "candidate_accession": c.get("accessionNumber", ""),
            "candidate_filing_date": (
                c["filingDate"].date().isoformat() if pd.notna(c["filingDate"]) else ""
            ),
            "candidate_acceptance": (
                c["acceptance_utc"].isoformat() if pd.notna(c["acceptance_utc"]) else ""
            ),
            "items": c.get("items", ""),
            "days_from_10k": (
                (c["filingDate"] - tenk_date).days if pd.notna(c["filingDate"]) else ""
            ),
            "relation_to_10k_acceptance": relation,
            "audit_note": "",
        })

out = pd.DataFrame(rows)
out.to_csv(OUT, index=False)

print("=" * 100)
print("EADRET FAILURE AUDIT")
print("=" * 100)
print(out.to_string(index=False))
print()
print(f"Saved: {OUT}")
