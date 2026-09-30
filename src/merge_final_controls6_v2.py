#!/usr/bin/env python3
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "metadata" / "controls" / "controls_item7.csv"
EAD = ROOT / "data" / "controls" / "eadret_item7.csv"
ACC = ROOT / "data" / "metadata" / "controls" / "accruals_item7.csv"
OUT = ROOT / "data" / "metadata" / "controls" / "controls_item7_final6.csv"

def pick(df, candidates, required=True):
    lower = {str(c).strip().lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    if required:
        raise ValueError(f"Missing one of {candidates}. Available={list(df.columns)}")
    return None

def normalize_keys(df):
    d = df.copy()
    tc = pick(d, ["ticker"])
    dc = pick(d, ["filing_date", "date", "tenk_filing_date"])
    d = d.rename(columns={tc: "ticker", dc: "filing_date"})
    d["ticker"] = d["ticker"].astype(str).str.upper().str.strip()
    d["filing_date"] = pd.to_datetime(d["filing_date"], errors="coerce")
    return d

def main():
    base = normalize_keys(pd.read_csv(BASE, low_memory=False))
    ead = normalize_keys(pd.read_csv(EAD, low_memory=False))
    acc = normalize_keys(pd.read_csv(ACC, low_memory=False))

    ead_value = pick(
        ead,
        ["eadret", "EADRet", "ead_ret", "earnings_announcement_return",
         "earnings_announcement_abnormal_return"],
        required=False,
    )
    if ead_value is None:
        candidates = [c for c in ead.columns
                      if "ead" in str(c).lower() and c not in {"ticker","filing_date"}]
        if not candidates:
            raise ValueError(f"Cannot identify EADRet column. Columns={list(ead.columns)}")
        ead_value = candidates[0]

    ead_status = pick(ead, ["status", "eadret_status", "event_status"], required=False)
    ead_reason = pick(ead, ["failure_reason", "reason", "note", "eadret_note"], required=False)
    ead_source = pick(ead, ["source", "eadret_source", "event_source"], required=False)
    ead_session = pick(ead, ["event_session", "event_date", "earnings_event_session"], required=False)

    keep = ["ticker", "filing_date", ead_value]
    for c in [ead_status, ead_reason, ead_source, ead_session]:
        if c and c not in keep:
            keep.append(c)
    e = ead[keep].drop_duplicates(["ticker", "filing_date"]).copy()
    rename = {ead_value: "eadret"}
    if ead_status: rename[ead_status] = "eadret_status"
    if ead_reason: rename[ead_reason] = "eadret_note"
    if ead_source: rename[ead_source] = "eadret_source"
    if ead_session: rename[ead_session] = "eadret_event_session"
    e = e.rename(columns=rename)
    e["eadret"] = pd.to_numeric(e["eadret"], errors="coerce")

    accrual_col = pick(acc, ["accruals", "Accruals"])
    status_col = pick(acc, ["status", "accruals_status"])
    depq_col = pick(acc, ["depreciation_quality"], required=False)
    currq_col = pick(acc, ["current_ltd_quality"], required=False)
    taxq_col = pick(acc, ["taxes_payable_quality"], required=False)
    note_col = pick(acc, ["note", "accruals_note"], required=False)

    keep = ["ticker", "filing_date", accrual_col, status_col]
    for c in [depq_col, currq_col, taxq_col, note_col]:
        if c and c not in keep:
            keep.append(c)
    a = acc[keep].drop_duplicates(["ticker", "filing_date"]).copy()
    rename = {accrual_col: "accruals_raw", status_col: "accruals_status"}
    if depq_col: rename[depq_col] = "depreciation_quality"
    if currq_col: rename[currq_col] = "current_ltd_quality"
    if taxq_col: rename[taxq_col] = "taxes_payable_quality"
    if note_col: rename[note_col] = "accruals_note"
    a = a.rename(columns=rename)
    a["accruals_raw"] = pd.to_numeric(a["accruals_raw"], errors="coerce")
    a["accruals_primary_ok"] = a["accruals_status"].astype(str).str.upper().eq("PASS")
    a["accruals"] = a["accruals_raw"].where(a["accruals_primary_ok"], np.nan)

    out = (
        base
        .merge(e, on=["ticker", "filing_date"], how="left", validate="one_to_one")
        .merge(a, on=["ticker", "filing_date"], how="left", validate="one_to_one")
        .sort_values(["ticker", "filing_date"])
        .reset_index(drop=True)
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")

    print("="*88)
    print("FINAL 6-CONTROL MERGE")
    print("="*88)
    print(f"rows                         : {len(out)}")
    print(f"firms                        : {out['ticker'].nunique()}")
    for c in ["size","bm","volatility","turnover","eadret","accruals"]:
        if c in out.columns:
            n = pd.to_numeric(out[c], errors="coerce").notna().sum()
            print(f"{c:28s}: {n}/{len(out)}")
    print("\nAccruals status:")
    print(out["accruals_status"].fillna("<MISSING>").value_counts().to_string())
    complete6 = out[["size","bm","volatility","turnover","eadret","accruals"]].apply(
        pd.to_numeric, errors="coerce"
    ).notna().all(axis=1)
    print(f"\ncomplete 6 controls          : {int(complete6.sum())}/{len(out)}")
    print(f"saved                        : {OUT}")

if __name__ == "__main__":
    main()
