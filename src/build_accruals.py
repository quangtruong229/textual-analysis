#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Build Sloan Accruals for each 10-K filing.

Version: v4 (post-targeted-QA update).

Strict implementation:

    Accruals =
        (ΔCurrentAssets
         - ΔCash
         - ΔCurrentLiabilities
         + ΔCurrentPortionOfDebt
         + ΔTaxesPayable
         - Depreciation)
        / AverageTotalAssets

Core rules:
1. Only SEC Company Facts available on or before the 10-K filing date.
2. ALL prior balance-sheet variables use ONE common prior fiscal year-end.
3. Missing data are NOT automatically treated as zero.
4. Current debt is aggregated carefully across non-overlapping debt concepts.
5. Current debt = 0 is inferred only after a structured current-liability
   reconciliation; the inference is explicitly marked in the output.
6. Pure depreciation is preferred over combined depreciation & amortization.
   Combined D&A is allowed only as an explicit fallback and is marked WARN.
7. No filing after the current 10-K may be used to populate a historical value.

Outputs:
    data/metadata/controls/accruals_item7.csv
"""

from __future__ import annotations

import argparse
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

FILINGS = ROOT / "data" / "metadata" / "filings_2016_2025.csv"
CACHE_DIR = ROOT / "data" / "metadata" / "controls" / "sec_facts_cache"
OUT = ROOT / "data" / "metadata" / "controls" / "accruals_item7.csv"


# -----------------------------------------------------------------------------
# BALANCE-SHEET CONCEPTS
# -----------------------------------------------------------------------------

BALANCE_CONCEPTS = {
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
    "current_ltd": [],  # handled by select_current_debt()
    "taxes_payable": [
        "TaxesPayableCurrent",
        "AccruedIncomeTaxesCurrent",
        "IncomeTaxesPayableCurrent",
    ],
    "total_assets": [
        "Assets",
    ],
}


# -----------------------------------------------------------------------------
# DEPRECIATION
# -----------------------------------------------------------------------------

# Important: Sloan/Compustat-style "Depreciation" should not silently be
# replaced by combined D&A when a pure depreciation fact is available.
DEPRECIATION_PURE = [
    # PP&E-specific depreciation is the cleanest match when disclosed.
    "DepreciationPropertyPlantAndEquipment",
    "DepreciationExpense",
    "Depreciation",
]

DEPRECIATION_DA_FALLBACK = [
    "DepreciationDepletionAndAmortization",
    "DepreciationAndAmortization",
]


# -----------------------------------------------------------------------------
# CURRENT-DEBT CONCEPTS
# -----------------------------------------------------------------------------

# Explicit aggregate is preferred.
CURRENT_DEBT_AGGREGATES = [
    "DebtCurrent",
]

# Current portion of long-term debt.
CURRENT_DEBT_LT_CURRENT = [
    "LongTermDebtCurrent",
    "CurrentPortionOfLongTermDebt",
    "CurrentPortionOfLongTermDebtAndFinanceLeaseObligations",
]

# Short-term financing. Treat ShortTermBorrowings as an aggregate if it exists;
# otherwise use CommercialPaper / short-term notes as a substitute, never add
# synonymous aggregates together.
CURRENT_DEBT_SHORT_TERM = [
    "ShortTermBorrowings",
    "CommercialPaper",
    "ShortTermNotesPayable",
    "NotesPayableCurrent",
]

# Current finance lease debt. Kept separate from operating lease liabilities.
CURRENT_DEBT_FINANCE_LEASE = [
    "FinanceLeaseLiabilityCurrent",
]


# -----------------------------------------------------------------------------
# CURRENT-LIABILITY RECONCILIATION
# -----------------------------------------------------------------------------

# These concepts are treated as non-debt current-liability components for the
# controlled zero-debt reconciliation. Broad catch-all aggregates are excluded
# because they may contain debt or tax components that are not separately tagged.
CURRENT_LIABILITY_COMPONENT_FAMILIES = [
    ["AccountsPayableCurrent"],
    [
        "EmployeeRelatedLiabilitiesCurrent",
        "AccruedEmployeeBenefitsCurrent",
        "AccruedEmployeeBenefitsCurrentAndNoncurrent",
    ],
    [
        "DeferredRevenueCurrent",
        "ContractWithCustomerLiabilityCurrent",
    ],
    ["OperatingLeaseLiabilityCurrent"],
    ["PensionAndOtherPostretirementDefinedBenefitPlansLiabilitiesCurrent"],
    ["DerivativeLiabilitiesCurrent"],
]


# -----------------------------------------------------------------------------
# GENERIC HELPERS
# -----------------------------------------------------------------------------


def candidate_rank(form: str, fp: str) -> int:
    form = str(form).upper()
    fp = str(fp).upper()

    if form == "10-K" and fp == "FY":
        return 0
    if form == "10-K/A" and fp == "FY":
        return 1
    if form == "10-K":
        return 2
    if form == "10-K/A":
        return 3
    return 4


def _ensure_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


@lru_cache(maxsize=None)
def load_facts(cik: str) -> pd.DataFrame:
    """Load cached SEC Company Facts once per CIK."""
    path = CACHE_DIR / f"CIK{cik}.json"

    if not path.exists():
        return pd.DataFrame()

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return pd.DataFrame()

    rows: list[dict] = []
    facts = payload.get("facts", {}).get("us-gaap", {})

    for concept, meta in facts.items():
        for unit, values in meta.get("units", {}).items():
            for v in values:
                rows.append(
                    {
                        "concept": concept,
                        "unit": unit,
                        "val": pd.to_numeric(v.get("val"), errors="coerce"),
                        "start": pd.to_datetime(v.get("start"), errors="coerce"),
                        "end": pd.to_datetime(v.get("end"), errors="coerce"),
                        "filed": pd.to_datetime(v.get("filed"), errors="coerce"),
                        "form": str(v.get("form", "")),
                        "fy": v.get("fy"),
                        "fp": v.get("fp"),
                    }
                )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def _admissible(facts: pd.DataFrame, filing_date: pd.Timestamp) -> pd.DataFrame:
    """Keep only observations available as of the current 10-K filing."""
    if facts.empty or pd.isna(filing_date):
        return pd.DataFrame()

    d = facts.copy()
    d["filed"] = _ensure_datetime(d["filed"])
    d["end"] = _ensure_datetime(d["end"])
    d["start"] = _ensure_datetime(d["start"])

    return d[
        d["filed"].notna()
        & d["filed"].le(filing_date)
        & d["val"].notna()
    ].copy()


# -----------------------------------------------------------------------------
# CURRENT BALANCE FACTS
# -----------------------------------------------------------------------------


def select_balance_fact(
    facts: pd.DataFrame,
    concepts: list[str],
    target_end: pd.Timestamp,
    filing_date: pd.Timestamp,
) -> tuple[float, str, pd.Timestamp]:
    """Select the best admissible balance fact at an exact end date."""
    if facts.empty or pd.isna(target_end):
        return np.nan, "", pd.NaT

    d = _admissible(facts, filing_date)
    if d.empty:
        return np.nan, "", pd.NaT

    d = d[
        d["concept"].isin(concepts)
        & d["end"].eq(target_end)
    ].copy()

    if d.empty:
        return np.nan, "", pd.NaT

    d["form"] = d["form"].fillna("").astype(str).str.upper()
    d["fp"] = d["fp"].fillna("").astype(str).str.upper()
    d["form_rank"] = [candidate_rank(a, b) for a, b in zip(d["form"], d["fp"])]

    # Most recently filed admissible observation among the best form ranking.
    d = d.sort_values(
        ["form_rank", "filed"],
        ascending=[True, False],
    )

    row = d.iloc[0]

    return float(row["val"]), str(row["concept"]), row["filed"]


# -----------------------------------------------------------------------------
# COMMON PRIOR FISCAL YEAR-END
# -----------------------------------------------------------------------------

PRIOR_END_ANCHOR_CONCEPTS = [
    "AssetsCurrent",
    "CashAndCashEquivalentsAtCarryingValue",
    "LiabilitiesCurrent",
    "Assets",
]


def select_prior_fiscal_end(
    facts: pd.DataFrame,
    current_end: pd.Timestamp,
    filing_date: pd.Timestamp,
) -> pd.Timestamp:
    """
    Determine ONE common prior fiscal year-end for all prior balance-sheet items.

    Preference:
      1) annual 10-K / 10-K/A with fp=FY;
      2) annual 10-K / 10-K/A with missing/non-FY fp.

    At least two independent anchor concepts must support the candidate end date.
    """
    if facts.empty or pd.isna(current_end):
        return pd.NaT

    d = _admissible(facts, filing_date)
    if d.empty:
        return pd.NaT

    d = d[
        d["concept"].isin(PRIOR_END_ANCHOR_CONCEPTS)
        & d["end"].notna()
        & d["end"].lt(current_end)
    ].copy()

    if d.empty:
        return pd.NaT

    d["form"] = d["form"].fillna("").astype(str).str.upper()
    d["fp"] = d["fp"].fillna("").astype(str).str.upper()

    annual_fy = d[
        d["form"].isin(["10-K", "10-K/A"])
        & d["fp"].eq("FY")
    ].copy()

    if annual_fy.empty:
        annual_fy = d[d["form"].isin(["10-K", "10-K/A"])].copy()

    if annual_fy.empty:
        return pd.NaT

    support = (
        annual_fy.groupby("end")["concept"]
        .nunique()
        .sort_index()
    )

    support = support[support >= 2]

    if support.empty:
        return pd.NaT

    return support.index.max()


# -----------------------------------------------------------------------------
# CURRENT-DEBT SELECTION / AGGREGATION
# -----------------------------------------------------------------------------


def _best_fact_for_concepts(
    facts: pd.DataFrame,
    concepts: list[str],
    target_end: pd.Timestamp,
    filing_date: pd.Timestamp,
) -> pd.DataFrame:
    """Return one best admissible observation for each requested concept."""
    if facts.empty or pd.isna(target_end):
        return pd.DataFrame()

    d = _admissible(facts, filing_date)
    if d.empty:
        return pd.DataFrame()

    d = d[
        d["concept"].isin(concepts)
        & d["end"].eq(target_end)
    ].copy()

    if d.empty:
        return pd.DataFrame()

    d["form"] = d["form"].fillna("").astype(str).str.upper()
    d["fp"] = d["fp"].fillna("").astype(str).str.upper()
    d["form_rank"] = [candidate_rank(a, b) for a, b in zip(d["form"], d["fp"])]

    d = (
        d.sort_values(
            ["concept", "form_rank", "filed"],
            ascending=[True, True, False],
        )
        .drop_duplicates("concept", keep="first")
    )

    return d


def _first_available_value(
    df: pd.DataFrame,
    ordered_concepts: list[str],
) -> tuple[float, str, bool]:
    """Pick the first available concept. Third return value means evidence exists."""
    if df.empty:
        return np.nan, "", False

    for concept in ordered_concepts:
        z = df[df["concept"].eq(concept)]
        if z.empty:
            continue

        value = float(z.iloc[0]["val"])
        return value, concept, True

    return np.nan, "", False


def select_current_debt(
    facts: pd.DataFrame,
    target_end: pd.Timestamp,
    filing_date: pd.Timestamp,
) -> tuple[float, str]:
    """
    Select/aggregate debt included in current liabilities.

    Priority:
      1) explicit DebtCurrent;
      2) current LT debt + short-term debt + current finance lease debt.

    Important:
      - Explicit zero is preserved as zero.
      - A missing debt fact is NOT zero.
      - Synonymous short-term aggregate concepts are never summed together.
    """

    # 1) Explicit aggregate.
    d = _best_fact_for_concepts(
        facts,
        CURRENT_DEBT_AGGREGATES,
        target_end,
        filing_date,
    )

    if not d.empty:
        row = d.iloc[0]
        return float(row["val"]), str(row["concept"])

    # 2) Current LT debt.
    lt = _best_fact_for_concepts(
        facts,
        CURRENT_DEBT_LT_CURRENT,
        target_end,
        filing_date,
    )
    lt_value, lt_source, lt_evidence = _first_available_value(
        lt,
        CURRENT_DEBT_LT_CURRENT,
    )
    if not lt_evidence:
        lt_value = 0.0

    # 3) Short-term debt: pick one aggregate.
    st = _best_fact_for_concepts(
        facts,
        CURRENT_DEBT_SHORT_TERM,
        target_end,
        filing_date,
    )

    st_value = 0.0
    st_source = ""
    st_evidence = False

    for concept in ["ShortTermBorrowings", "CommercialPaper", "ShortTermNotesPayable", "NotesPayableCurrent"]:
        z = st[st["concept"].eq(concept)] if not st.empty else pd.DataFrame()
        if z.empty:
            continue
        st_value = float(z.iloc[0]["val"])
        st_source = concept
        st_evidence = True
        break

    # 4) Current finance lease debt.
    lease = _best_fact_for_concepts(
        facts,
        CURRENT_DEBT_FINANCE_LEASE,
        target_end,
        filing_date,
    )
    lease_value, lease_source, lease_evidence = _first_available_value(
        lease,
        CURRENT_DEBT_FINANCE_LEASE,
    )

    # If the selected LT-debt concept explicitly includes finance leases,
    # do not add FinanceLeaseLiabilityCurrent again.
    if lt_source == "CurrentPortionOfLongTermDebtAndFinanceLeaseObligations":
        lease_value = 0.0
        lease_source = ""
        lease_evidence = False
    elif not lease_evidence:
        lease_value = 0.0

    evidence_sources = [
        x
        for x in [lt_source, st_source, lease_source]
        if x
    ]

    if not evidence_sources:
        return np.nan, ""

    total = lt_value + st_value + lease_value

    # Preserve an explicit zero rather than converting it to NaN.
    if np.isfinite(total):
        return float(total), " + ".join(evidence_sources)

    return np.nan, ""


# -----------------------------------------------------------------------------
# CONTROLLED ZERO-DEBT RECONCILIATION
# -----------------------------------------------------------------------------


def infer_current_ltd_zero(
    facts: pd.DataFrame,
    target_end: pd.Timestamp,
    filing_date: pd.Timestamp,
    current_liabilities: float,
) -> tuple[float, str]:
    """
    Infer current debt = 0 only when current liabilities can be reconciled
    to a controlled set of non-debt components.

    This is an implementation-level accounting reconciliation, not a generic
    "missing tag = 0" rule.
    """
    if (
        facts.empty
        or pd.isna(target_end)
        or not np.isfinite(current_liabilities)
    ):
        return np.nan, ""

    all_concepts = [c for family in CURRENT_LIABILITY_COMPONENT_FAMILIES for c in family]

    d = _best_fact_for_concepts(
        facts,
        all_concepts,
        target_end,
        filing_date,
    )

    if d.empty:
        return np.nan, ""

    values = dict(zip(d["concept"], d["val"]))
    sources: list[str] = []
    selected: list[tuple[str, float]] = []

    for family in CURRENT_LIABILITY_COMPONENT_FAMILIES:
        # One observation per mutually exclusive family.
        present = [
            (concept, float(values[concept]))
            for concept in family
            if concept in values and np.isfinite(float(values[concept]))
        ]

        if not present:
            continue

        # Family order is deliberately explicit and deterministic.
        concept, value = present[0]
        selected.append((concept, value))
        sources.append(concept)

    if not selected:
        return np.nan, ""

    component_sum = sum(value for _, value in selected)

    # Strict enough to accommodate unit/rounding differences while avoiding
    # a very large absolute tolerance on small issuers.
    tolerance = max(abs(float(current_liabilities)) * 0.005, 1000.0)

    if abs(component_sum - float(current_liabilities)) <= tolerance:
        return 0.0, "RECONCILIATION_ZERO[" + " + ".join(sources) + "]"

    return np.nan, ""


# -----------------------------------------------------------------------------
# DEPRECIATION SELECTION
# -----------------------------------------------------------------------------


def _select_annual_flow(
    facts: pd.DataFrame,
    concepts: list[str],
    target_end: pd.Timestamp,
    filing_date: pd.Timestamp,
) -> pd.DataFrame:
    """Return admissible annual flows ending at target_end."""
    if facts.empty or pd.isna(target_end):
        return pd.DataFrame()

    d = _admissible(facts, filing_date)
    if d.empty:
        return pd.DataFrame()

    d = d[
        d["concept"].isin(concepts)
        & d["end"].eq(target_end)
        & d["start"].notna()
    ].copy()

    if d.empty:
        return pd.DataFrame()

    d["days"] = (d["end"] - d["start"]).dt.days
    d = d[(d["days"] >= 300) & (d["days"] <= 400)].copy()

    if d.empty:
        return pd.DataFrame()

    d["form"] = d["form"].fillna("").astype(str).str.upper()
    d["fp"] = d["fp"].fillna("").astype(str).str.upper()
    d["form_rank"] = [candidate_rank(a, b) for a, b in zip(d["form"], d["fp"])]

    d = d.sort_values(
        ["form_rank", "filed"],
        ascending=[True, False],
    )

    return d


def _select_preferred_concept(
    d: pd.DataFrame,
    ordered_concepts: list[str],
) -> Optional[pd.Series]:
    if d.empty:
        return None

    for concept in ordered_concepts:
        z = d[d["concept"].eq(concept)]
        if not z.empty:
            return z.iloc[0]

    return None


def select_depreciation(
    facts: pd.DataFrame,
    target_end: pd.Timestamp,
    filing_date: pd.Timestamp,
) -> tuple[float, str, str, pd.Timestamp]:
    """
    Return:
        value, source concept, quality, filed date

    quality:
        PURE = pure depreciation concept used.
        DA_FALLBACK = combined depreciation & amortization was used because no
                      pure depreciation fact was available.
    """

    pure = _select_annual_flow(
        facts,
        DEPRECIATION_PURE,
        target_end,
        filing_date,
    )
    row = _select_preferred_concept(pure, DEPRECIATION_PURE)

    if row is not None:
        return (
            float(row["val"]),
            str(row["concept"]),
            "PURE",
            row["filed"],
        )

    # Controlled fallback. It is NOT silently considered equivalent to pure
    # depreciation; compute_row() will mark the row WARN.
    da = _select_annual_flow(
        facts,
        DEPRECIATION_DA_FALLBACK,
        target_end,
        filing_date,
    )
    row = _select_preferred_concept(da, DEPRECIATION_DA_FALLBACK)

    if row is not None:
        return (
            float(row["val"]),
            str(row["concept"]),
            "DA_FALLBACK",
            row["filed"],
        )

    return np.nan, "", "MISSING", pd.NaT


# -----------------------------------------------------------------------------
# ROW CALCULATION
# -----------------------------------------------------------------------------


def compute_row(
    ticker: str,
    filing_date: pd.Timestamp,
    report_date: pd.Timestamp,
    cik: str,
) -> dict:
    facts = load_facts(cik)

    out = {
        "ticker": ticker,
        "filing_date": filing_date.strftime("%Y-%m-%d"),
        "report_date": report_date.strftime("%Y-%m-%d"),
        "cik": cik,
        "prior_fiscal_end": "",
        "current_assets": np.nan,
        "prior_current_assets": np.nan,
        "cash": np.nan,
        "prior_cash": np.nan,
        "current_liabilities": np.nan,
        "prior_current_liabilities": np.nan,
        "current_ltd": np.nan,
        "prior_current_ltd": np.nan,
        "taxes_payable": np.nan,
        "prior_taxes_payable": np.nan,
        "depreciation": np.nan,
        "depreciation_quality": "MISSING",
        "total_assets": np.nan,
        "prior_total_assets": np.nan,
        "average_total_assets": np.nan,
        "accruals": np.nan,
        "current_assets_source": "",
        "prior_current_assets_source": "",
        "cash_source": "",
        "prior_cash_source": "",
        "current_liabilities_source": "",
        "prior_current_liabilities_source": "",
        "current_ltd_source": "",
        "current_ltd_quality": "MISSING",
        "prior_current_ltd_source": "",
        "prior_current_ltd_quality": "MISSING",
        "taxes_payable_source": "",
        "prior_taxes_payable_source": "",
        "depreciation_source": "",
        "total_assets_source": "",
        "prior_total_assets_source": "",
        "status": "FAIL",
        "note": "",
    }

    if facts.empty:
        out["note"] = "No SEC Company Facts cache"
        return out

    if pd.isna(filing_date) or pd.isna(report_date):
        out["note"] = "Invalid filing/report date"
        return out

    # -------------------------------------------------------------------------
    # Current balance-sheet facts.
    # -------------------------------------------------------------------------
    for key, concepts in BALANCE_CONCEPTS.items():
        if key == "current_ltd":
            val, source = select_current_debt(
                facts,
                report_date,
                filing_date,
            )
            out["current_ltd"] = val
            out["current_ltd_source"] = source
            if np.isfinite(val):
                out["current_ltd_quality"] = (
                    "EXPLICIT_ZERO" if float(val) == 0.0 else "DIRECT_OR_AGGREGATED"
                )
            continue

        val, source, _filed_source = select_balance_fact(
            facts,
            concepts,
            report_date,
            filing_date,
        )

        out[key] = val

        if key == "current_assets":
            out["current_assets_source"] = source
        elif key == "cash":
            out["cash_source"] = source
        elif key == "current_liabilities":
            out["current_liabilities_source"] = source
        elif key == "taxes_payable":
            out["taxes_payable_source"] = source
        elif key == "total_assets":
            out["total_assets_source"] = source

    # Controlled current-debt zero inference.
    if not np.isfinite(out["current_ltd"]):
        inferred_ltd, inferred_source = infer_current_ltd_zero(
            facts,
            report_date,
            filing_date,
            out["current_liabilities"],
        )

        if np.isfinite(inferred_ltd):
            out["current_ltd"] = inferred_ltd
            out["current_ltd_source"] = inferred_source
            out["current_ltd_quality"] = "RECONCILIATION_ZERO"

    # -------------------------------------------------------------------------
    # Determine ONE common prior fiscal year-end.
    # -------------------------------------------------------------------------
    prior_fiscal_end = select_prior_fiscal_end(
        facts,
        report_date,
        filing_date,
    )

    if pd.isna(prior_fiscal_end):
        out["status"] = "WARN"
        out["note"] = "Cannot determine common prior fiscal year-end"
        return out

    out["prior_fiscal_end"] = prior_fiscal_end.strftime("%Y-%m-%d")

    # -------------------------------------------------------------------------
    # Prior balance-sheet facts: ALL use exactly prior_fiscal_end.
    # -------------------------------------------------------------------------
    for key, concepts in BALANCE_CONCEPTS.items():
        if key == "current_ltd":
            val, source = select_current_debt(
                facts,
                prior_fiscal_end,
                filing_date,
            )
            out["prior_current_ltd"] = val
            out["prior_current_ltd_source"] = source
            if np.isfinite(val):
                out["prior_current_ltd_quality"] = (
                    "EXPLICIT_ZERO" if float(val) == 0.0 else "DIRECT_OR_AGGREGATED"
                )
            continue

        val, source, _filed_source = select_balance_fact(
            facts,
            concepts,
            prior_fiscal_end,
            filing_date,
        )

        out[f"prior_{key}"] = val

        if key == "current_assets":
            out["prior_current_assets_source"] = source
        elif key == "cash":
            out["prior_cash_source"] = source
        elif key == "current_liabilities":
            out["prior_current_liabilities_source"] = source
        elif key == "taxes_payable":
            out["prior_taxes_payable_source"] = source
        elif key == "total_assets":
            out["prior_total_assets_source"] = source

    # Controlled prior-year current-debt zero inference.
    if not np.isfinite(out["prior_current_ltd"]):
        inferred_ltd, inferred_source = infer_current_ltd_zero(
            facts,
            prior_fiscal_end,
            filing_date,
            out["prior_current_liabilities"],
        )

        if np.isfinite(inferred_ltd):
            out["prior_current_ltd"] = inferred_ltd
            out["prior_current_ltd_source"] = inferred_source
            out["prior_current_ltd_quality"] = "RECONCILIATION_ZERO"

    # -------------------------------------------------------------------------
    # Depreciation.
    # -------------------------------------------------------------------------
    dep, dep_source, dep_quality, _dep_filed = select_depreciation(
        facts,
        report_date,
        filing_date,
    )

    out["depreciation"] = dep
    out["depreciation_source"] = dep_source
    out["depreciation_quality"] = dep_quality

    # -------------------------------------------------------------------------
    # Completeness.
    # -------------------------------------------------------------------------
    required = [
        "current_assets",
        "prior_current_assets",
        "cash",
        "prior_cash",
        "current_liabilities",
        "prior_current_liabilities",
        "current_ltd",
        "prior_current_ltd",
        "taxes_payable",
        "prior_taxes_payable",
        "depreciation",
        "total_assets",
        "prior_total_assets",
    ]

    missing = [
        x
        for x in required
        if not np.isfinite(out[x])
    ]

    if missing:
        out["status"] = "WARN"
        out["note"] = "Missing: " + ", ".join(missing)
        return out

    avg_assets = (
        out["total_assets"] + out["prior_total_assets"]
    ) / 2.0

    if not np.isfinite(avg_assets) or avg_assets <= 0:
        out["status"] = "WARN"
        out["note"] = "Invalid average total assets"
        return out

    # -------------------------------------------------------------------------
    # Sloan accrual calculation.
    # -------------------------------------------------------------------------
    delta_ca = out["current_assets"] - out["prior_current_assets"]
    delta_cash = out["cash"] - out["prior_cash"]
    delta_cl = out["current_liabilities"] - out["prior_current_liabilities"]
    delta_ltd = out["current_ltd"] - out["prior_current_ltd"]
    delta_tax = out["taxes_payable"] - out["prior_taxes_payable"]

    numerator = (
        delta_ca
        - delta_cash
        - delta_cl
        + delta_ltd
        + delta_tax
        - out["depreciation"]
    )

    out["average_total_assets"] = avg_assets
    out["accruals"] = numerator / avg_assets

    # Pure depreciation -> strict PASS. D&A fallback -> numeric result exists,
    # but status remains WARN because the depreciation input is an adaptation.
    if out["depreciation_quality"] == "PURE":
        out["status"] = "PASS"
        out["note"] = "Strict Sloan Accruals"
    else:
        out["status"] = "WARN"
        out["note"] = "Uses D&A fallback instead of pure depreciation"

    return out


# -----------------------------------------------------------------------------
# MAIN / QA
# -----------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Sloan Accruals from SEC structured data."
    )
    parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Process only one ticker, e.g. A",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Process only one fiscal/report year, e.g. 2016",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Optional output CSV path",
    )

    args = parser.parse_args()

    filings = pd.read_csv(FILINGS, dtype=str)

    filings["ticker"] = filings["ticker"].astype(str).str.upper()
    filings["filing_date"] = pd.to_datetime(filings["filing_date"], errors="coerce")
    filings["report_date"] = pd.to_datetime(filings["report_date"], errors="coerce")

    if args.ticker:
        filings = filings[filings["ticker"].eq(args.ticker.upper())].copy()

    if args.year:
        filings = filings[filings["report_date"].dt.year.eq(args.year)].copy()

    if filings.empty:
        raise SystemExit("No filing matched the requested --ticker/--year filter.")

    filings = filings.sort_values(["ticker", "filing_date"]).copy()

    rows: list[dict] = []
    total = len(filings)

    for i, (_, row) in enumerate(filings.iterrows(), start=1):
        ticker = row["ticker"]
        fd = row["filing_date"]
        rd = row["report_date"]
        cik = str(row["cik"]).replace(".0", "").zfill(10)

        result = compute_row(ticker, fd, rd, cik)
        rows.append(result)

        print(
            f"[{i:>4}/{total:>4}] "
            f"{ticker} {fd.date()} -> {result['status']}"
        )

        if args.ticker or args.year:
            for col in [
                "report_date",
                "prior_fiscal_end",
                "current_assets",
                "prior_current_assets",
                "cash",
                "prior_cash",
                "current_liabilities",
                "prior_current_liabilities",
                "current_ltd",
                "current_ltd_source",
                "current_ltd_quality",
                "prior_current_ltd",
                "prior_current_ltd_source",
                "prior_current_ltd_quality",
                "taxes_payable",
                "taxes_payable_source",
                "prior_taxes_payable",
                "prior_taxes_payable_source",
                "depreciation",
                "depreciation_source",
                "depreciation_quality",
                "total_assets",
                "prior_total_assets",
                "average_total_assets",
                "accruals",
                "status",
                "note",
            ]:
                if col in result:
                    print(f"    {col:30s}: {result[col]}")

    df = pd.DataFrame(rows)

    if args.out:
        out_path = Path(args.out)
    elif args.ticker or args.year:
        out_path = ROOT / "data" / "metadata" / "controls" / "accruals_item7_test.csv"
    else:
        out_path = OUT

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 80)
    print("ACCRUALS QA")
    print("=" * 80)

    print(f"Rows: {len(df)}")
    print(f"Firms: {df['ticker'].nunique()}")

    for col in [
        "current_assets",
        "cash",
        "current_liabilities",
        "current_ltd",
        "taxes_payable",
        "depreciation",
        "total_assets",
        "accruals",
    ]:
        print(f"{col:25s}: {df[col].notna().sum()}/{len(df)}")

    print("\nStatus:")
    print(df["status"].value_counts(dropna=False).to_string())

    print("\nDepreciation quality:")
    print(df["depreciation_quality"].value_counts(dropna=False).to_string())

    print("\nTop current_ltd_source values:")
    print(
        df["current_ltd_source"]
        .replace("", "<MISSING>")
        .fillna("<MISSING>")
        .value_counts()
        .head(15)
        .to_string()
    )

    print("\nTop prior_current_ltd_source values:")
    print(
        df["prior_current_ltd_source"]
        .replace("", "<MISSING>")
        .fillna("<MISSING>")
        .value_counts()
        .head(15)
        .to_string()
    )

    warn_df = df[df["status"].eq("WARN")]
    if not warn_df.empty:
        print(f"\nWARN rows: {len(warn_df)}")
        print("Top WARN reasons:")
        print(warn_df["note"].fillna("").value_counts().head(20).to_string())
    else:
        print("\nWARN rows: 0")

    print(
        "\nStrict PASS:",
        int((df["status"] == "PASS").sum()),
        "/",
        len(df),
    )

    print(
        "Strict PASS firms:",
        df.loc[df["status"] == "PASS", "ticker"].nunique(),
    )

    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
