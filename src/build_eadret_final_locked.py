from __future__ import annotations

from pathlib import Path
import argparse
import json
import time
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import requests

from eadret_calendar import (
    resolve_event_session,
    event_sessions,
)


# ============================================================
# CONFIG
# ============================================================

FILINGS_PATH = Path("data/metadata/filings_2016_2025.csv")
PRICE_PATH = Path("data/market_data/daily_prices.csv")

OUT_DIR = Path("data/controls")
CACHE_DIR = Path("data/metadata/controls/sec_submissions_cache")
CHECKPOINT_PATH = OUT_DIR / "eadret_item7_checkpoint.csv"
FINAL_PATH = OUT_DIR / "eadret_item7.csv"
QA_SUMMARY_PATH = OUT_DIR / "eadret_item7_qa_summary.csv"
QA_FAILURES_PATH = OUT_DIR / "eadret_item7_failures.csv"

BENCHMARK = "^GSPC"

# Locked to the group's written methodology and Jegadeesh & Wu text definition:
# three-day window [t-1, t+1] around the earnings announcement.
EVENT_START = -1
EVENT_END = 1

SEC_USER_AGENT = "truongungquang1@gmail.com"
SEC_HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
}

SEC_SLEEP_SECONDS = 0.11
CHECKPOINT_EVERY = 25


# ============================================================
# SEC HELPERS
# ============================================================

def get_json(url: str) -> dict:
    r = requests.get(url, headers=SEC_HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def _normalize_submission_frame(obj) -> pd.DataFrame:
    if not obj:
        return pd.DataFrame()

    df = pd.DataFrame(obj)

    for col in ("filingDate", "reportDate"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


def _load_company_submissions_from_sec(cik: str) -> pd.DataFrame:
    cik = str(cik).zfill(10)
    base_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    payload = get_json(base_url)

    frames = []

    recent = payload.get("filings", {}).get("recent", {})
    recent_df = _normalize_submission_frame(recent)
    if not recent_df.empty:
        frames.append(recent_df)

    historical = payload.get("filings", {}).get("files", []) or []
    for item in historical:
        name = item.get("name")
        if not name:
            continue

        url = f"https://data.sec.gov/submissions/{name}"
        hist_payload = get_json(url)
        hist_df = _normalize_submission_frame(hist_payload)
        if not hist_df.empty:
            frames.append(hist_df)

        time.sleep(SEC_SLEEP_SECONDS)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    if "accessionNumber" in combined.columns:
        combined = combined.drop_duplicates(
            subset=["accessionNumber"],
            keep="last",
        )

    sort_cols = [
        c for c in ["filingDate", "acceptanceDateTime", "accessionNumber"]
        if c in combined.columns
    ]
    if sort_cols:
        combined = combined.sort_values(
            sort_cols,
            na_position="last",
        )

    return combined.reset_index(drop=True)


def load_submissions_cached(cik: str, refresh: bool = False) -> pd.DataFrame:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cik = str(cik).zfill(10)
    cache_path = CACHE_DIR / f"CIK{cik}.csv"

    if cache_path.exists() and not refresh:
        df = pd.read_csv(
            cache_path,
            dtype={"accessionNumber": str},
        )
        for col in ("filingDate", "reportDate"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return df

    df = _load_company_submissions_from_sec(cik)
    df.to_csv(cache_path, index=False)
    time.sleep(SEC_SLEEP_SECONDS)
    return df


def _parse_utc_timestamp(value):
    if value is None or value == "" or pd.isna(value):
        return pd.NaT
    return pd.to_datetime(value, utc=True, errors="coerce")


def get_10k_acceptance_timestamp(
    submissions: pd.DataFrame,
    accession_number: str,
):
    if submissions.empty or "accessionNumber" not in submissions.columns:
        return pd.NaT

    x = submissions[
        submissions["accessionNumber"].astype(str).eq(str(accession_number))
    ]

    if x.empty:
        return pd.NaT

    return _parse_utc_timestamp(
        x.iloc[0].get("acceptanceDateTime", "")
    )


def has_item_202(item_text: str) -> bool:
    if pd.isna(item_text):
        return False

    items = {
        x.strip()
        for x in str(item_text).split(",")
        if x.strip()
    }
    return "2.02" in items


def find_latest_earnings_announcement(
    submissions: pd.DataFrame,
    tenk_filing_date: pd.Timestamp,
    tenk_acceptance_utc=pd.NaT,
):
    """
    Resolve the latest valid prior 8-K Item 2.02 for the current annual reporting cycle.

    Rules:
      1) Candidate must be before the current 10-K acceptance timestamp when available.
      2) Same-day candidates are eligible only if accepted before the 10-K.
      3) Candidate must occur after the immediately preceding 10-K filing date.
         This prevents a stale Item 2.02 from an earlier annual reporting cycle from
         being used when no valid current-cycle earnings announcement exists.
    """
    if submissions.empty:
        return None, "no_submissions"

    required = {"form", "filingDate", "items"}
    if not required.issubset(submissions.columns):
        return None, "submission_schema_missing"

    all_subs = submissions.copy()

    # Determine the immediately preceding 10-K filing date.
    tenks = all_subs[
        all_subs["form"].astype(str).str.upper().isin(["10-K", "10-K/A"])
        & all_subs["filingDate"].notna()
        & (all_subs["filingDate"] < tenk_filing_date)
    ].sort_values("filingDate")

    previous_10k_date = (
        pd.Timestamp(tenks.iloc[-1]["filingDate"])
        if not tenks.empty else pd.NaT
    )

    x = all_subs[
        all_subs["form"].astype(str).str.upper().eq("8-K")
        & all_subs["filingDate"].notna()
        & all_subs["items"].map(has_item_202)
    ].copy()

    if x.empty:
        return None, "no_item_2_02_before_10k"

    if "acceptanceDateTime" not in x.columns:
        x["acceptanceDateTime"] = ""

    x["acceptance_utc"] = x["acceptanceDateTime"].map(_parse_utc_timestamp)

    earlier_day = x["filingDate"] < tenk_filing_date
    same_day = x["filingDate"].eq(tenk_filing_date)

    if pd.notna(tenk_acceptance_utc):
        same_day_before = (
            same_day
            & x["acceptance_utc"].notna()
            & (x["acceptance_utc"] < tenk_acceptance_utc)
        )
        eligible = earlier_day | same_day_before
    else:
        eligible = earlier_day

    # Restrict to the current annual reporting cycle.
    if pd.notna(previous_10k_date):
        eligible = eligible & (x["filingDate"] > previous_10k_date)

    x = x[eligible].copy()

    if x.empty:
        return None, "no_valid_prior_earnings_announcement"

    sort_cols = [
        c for c in ["filingDate", "acceptance_utc", "accessionNumber"]
        if c in x.columns
    ]
    x = x.sort_values(
        sort_cols,
        ascending=[False] * len(sort_cols),
        na_position="last",
    ).reset_index(drop=True)

    return x.iloc[0].to_dict(), "success"


# ============================================================
# PRICE HELPERS
# ============================================================

def prepare_prices() -> pd.DataFrame:
    prices = pd.read_csv(PRICE_PATH)

    required = {"ticker", "date", "return", "adj_close"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"Missing price columns: {sorted(missing)}")

    prices["ticker"] = prices["ticker"].astype(str).str.strip().str.upper()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    prices["return"] = pd.to_numeric(prices["return"], errors="coerce")
    prices["adj_close"] = pd.to_numeric(prices["adj_close"], errors="coerce")

    prices = prices.dropna(subset=["ticker", "date"]).copy()
    return prices.sort_values(["ticker", "date"]).reset_index(drop=True)


def buy_hold_from_daily_returns(window: pd.DataFrame) -> float:
    r = pd.to_numeric(window["return"], errors="coerce")
    if r.isna().any():
        return np.nan
    return float(np.prod(1.0 + r.to_numpy(float)) - 1.0)


def get_window_return(
    prices: pd.DataFrame,
    ticker: str,
    dates: pd.DatetimeIndex,
):
    normalized_dates = pd.DatetimeIndex(dates).tz_localize(None).normalize()

    x = prices[
        prices["ticker"].eq(ticker)
        & prices["date"].dt.normalize().isin(normalized_dates)
    ].sort_values("date")

    if len(x) != len(normalized_dates):
        return np.nan, "missing_price_session"

    if x["return"].isna().any():
        return np.nan, "missing_daily_return"

    value = buy_hold_from_daily_returns(x)
    if not np.isfinite(value):
        return np.nan, "return_not_computable"

    return value, "success"


# ============================================================
# ONE FILING
# ============================================================

def empty_row(filing, status: str) -> Dict:
    ticker = str(filing["ticker"]).strip().upper()
    cik = str(filing["cik"]).zfill(10)
    tenk_date = pd.Timestamp(filing["filing_date"])

    return {
        "ticker": ticker,
        "cik": cik,
        "tenk_filing_date": tenk_date.date().isoformat()
            if pd.notna(tenk_date) else "",
        "tenk_report_date": str(filing.get("report_date", "")),
        "tenk_accession": str(filing["accession_number"]),
        "tenk_acceptance_datetime_utc": "",
        "announcement_accession": "",
        "announcement_filing_date": "",
        "announcement_report_date": "",
        "acceptance_datetime_utc": "",
        "acceptance_datetime_et": "",
        "announcement_session": "",
        "event_start": EVENT_START,
        "event_end": EVENT_END,
        "event_rule": "",
        "session_close_utc": "",
        "window_dates": "",
        "stock_return": np.nan,
        "market_return": np.nan,
        "eadret": np.nan,
        "status": status,
        "note": "",
    }


def process_one_filing(
    filing,
    submissions: pd.DataFrame,
    prices: pd.DataFrame,
) -> Dict:
    base = empty_row(filing, "unprocessed")

    ticker = base["ticker"]
    tenk_date = pd.Timestamp(filing["filing_date"])
    accession_10k = str(filing["accession_number"])

    tenk_acceptance_utc = get_10k_acceptance_timestamp(
        submissions,
        accession_10k,
    )

    base["tenk_acceptance_datetime_utc"] = (
        tenk_acceptance_utc.isoformat()
        if pd.notna(tenk_acceptance_utc)
        else ""
    )

    announcement, ann_status = find_latest_earnings_announcement(
        submissions,
        tenk_date,
        tenk_acceptance_utc=tenk_acceptance_utc,
    )

    if announcement is None:
        base["status"] = ann_status
        return base

    acceptance_utc = announcement.get("acceptanceDateTime", "")
    ann_filing_date = announcement.get("filingDate")
    ann_report_date = announcement.get("reportDate")

    base.update({
        "announcement_accession": announcement.get("accessionNumber", ""),
        "announcement_filing_date": (
            ann_filing_date.date().isoformat()
            if pd.notna(ann_filing_date) else ""
        ),
        "announcement_report_date": (
            ann_report_date.date().isoformat()
            if pd.notna(ann_report_date) else ""
        ),
        "acceptance_datetime_utc": acceptance_utc or "",
    })

    ts_utc = _parse_utc_timestamp(acceptance_utc)
    if pd.isna(ts_utc):
        base["status"] = "bad_acceptance_timestamp"
        return base

    base["acceptance_datetime_et"] = (
        ts_utc.tz_convert("America/New_York").isoformat()
    )

    try:
        resolution = resolve_event_session(acceptance_utc)
    except Exception as exc:
        base["status"] = "event_session_resolution_error"
        base["note"] = repr(exc)
        return base

    event_session = resolution.event_session

    try:
        dates = event_sessions(
            event_session,
            EVENT_START,
            EVENT_END,
        )
    except Exception as exc:
        base["status"] = "insufficient_event_window"
        base["note"] = repr(exc)
        return base

    stock_ret, stock_status = get_window_return(
        prices,
        ticker,
        dates,
    )
    market_ret, market_status = get_window_return(
        prices,
        BENCHMARK,
        dates,
    )

    base.update({
        "announcement_session": event_session.date().isoformat(),
        "event_rule": resolution.rule,
        "session_close_utc": resolution.session_close_utc.isoformat(),
        "window_dates": ",".join(
            d.date().isoformat() for d in dates
        ),
        "stock_return": stock_ret,
        "market_return": market_ret,
    })

    if stock_status != "success":
        base["status"] = f"stock_{stock_status}"
        return base

    if market_status != "success":
        base["status"] = f"market_{market_status}"
        return base

    base["eadret"] = stock_ret - market_ret
    base["status"] = "success"
    base["note"] = (
        "Source: SEC Submissions recent + historical; "
        "earnings announcement = latest prior 8-K Item 2.02; "
        "same-day ordering uses acceptance timestamp; "
        "event session uses XNYS actual session close; "
        f"event window=[{EVENT_START},{EVENT_END}]; "
        "^GSPC adaptation benchmark; "
        "daily return reused from daily_prices.csv."
    )
    return base


# ============================================================
# QA
# ============================================================

def build_qa_summary(out: pd.DataFrame) -> pd.DataFrame:
    total = len(out)
    success = int(out["status"].eq("success").sum())

    rows = [
        ("total_filings", total),
        ("success", success),
        ("failures", total - success),
        ("success_rate", success / total if total else np.nan),
    ]

    for status, count in out["status"].value_counts(dropna=False).items():
        rows.append((f"status::{status}", int(count)))

    if "event_rule" in out.columns:
        for rule, count in (
            out.loc[out["event_rule"].astype(str).ne(""), "event_rule"]
            .value_counts(dropna=False)
            .items()
        ):
            rows.append((f"event_rule::{rule}", int(count)))

    return pd.DataFrame(rows, columns=["metric", "value"])


# ============================================================
# RESUME / CHECKPOINT
# ============================================================

def load_checkpoint() -> Tuple[pd.DataFrame, set]:
    if not CHECKPOINT_PATH.exists():
        return pd.DataFrame(), set()

    checkpoint = pd.read_csv(
        CHECKPOINT_PATH,
        dtype={"tenk_accession": str},
    )
    done = set(checkpoint["tenk_accession"].astype(str))
    return checkpoint, done


def save_checkpoint(rows):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(CHECKPOINT_PATH, index=False)


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh-sec-cache",
        action="store_true",
        help="Ignore cached SEC submission CSVs and fetch them again.",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Ignore/remove previous checkpoint and rebuild from scratch.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional number of filings to process for a batch smoke test.",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if args.restart and CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()

    filings = pd.read_csv(
        FILINGS_PATH,
        dtype={"accession_number": str},
    )
    filings["filing_date"] = pd.to_datetime(
        filings["filing_date"],
        errors="coerce",
    )

    required = {
        "ticker", "cik", "filing_date",
        "report_date", "accession_number",
    }
    missing = required - set(filings.columns)
    if missing:
        raise ValueError(
            f"Missing filing columns: {sorted(missing)}"
        )

    filings = filings.dropna(
        subset=["ticker", "cik", "filing_date", "accession_number"]
    ).copy()

    filings["ticker"] = (
        filings["ticker"].astype(str).str.strip().str.upper()
    )
    filings = filings.sort_values(
        ["ticker", "filing_date"],
    ).reset_index(drop=True)

    if args.limit > 0:
        filings = filings.head(args.limit).copy()

    prices = prepare_prices()

    checkpoint, done = load_checkpoint()
    rows = (
        checkpoint.to_dict("records")
        if not checkpoint.empty
        else []
    )

    remaining = filings[
        ~filings["accession_number"].astype(str).isin(done)
    ].copy()

    print("=" * 80)
    print("EADRET FULL BATCH")
    print("=" * 80)
    print(f"Total target filings : {len(filings):,}")
    print(f"Already checkpointed : {len(done):,}")
    print(f"Remaining            : {len(remaining):,}")
    print(f"Event window         : [{EVENT_START}, {EVENT_END}]")
    print(f"Benchmark            : {BENCHMARK}")
    print()

    submissions_by_cik: Dict[str, pd.DataFrame] = {}
    processed_this_run = 0

    for i, (_, filing) in enumerate(remaining.iterrows(), start=1):
        ticker = str(filing["ticker"]).strip().upper()
        cik = str(filing["cik"]).zfill(10)
        accession = str(filing["accession_number"])

        print(
            f"[{i:04d}/{len(remaining):04d}] "
            f"{ticker} {accession}",
            flush=True,
        )

        try:
            if cik not in submissions_by_cik:
                submissions_by_cik[cik] = load_submissions_cached(
                    cik,
                    refresh=args.refresh_sec_cache,
                )

            row = process_one_filing(
                filing,
                submissions_by_cik[cik],
                prices,
            )

        except requests.RequestException as exc:
            row = empty_row(filing, "sec_request_error")
            row["note"] = repr(exc)

        except Exception as exc:
            row = empty_row(filing, "unexpected_error")
            row["note"] = repr(exc)

        rows.append(row)
        processed_this_run += 1

        if (
            processed_this_run % CHECKPOINT_EVERY == 0
            or i == len(remaining)
        ):
            save_checkpoint(rows)
            print(
                f"  checkpoint saved: {len(rows):,} rows",
                flush=True,
            )

    out = pd.DataFrame(rows)

    # De-duplicate if checkpoint was resumed/restarted in an unusual way.
    if not out.empty:
        out = (
            out.sort_values(["ticker", "tenk_filing_date"])
            .drop_duplicates(
                subset=["tenk_accession"],
                keep="last",
            )
            .reset_index(drop=True)
        )

    out.to_csv(FINAL_PATH, index=False)

    failures = out[out["status"].ne("success")].copy()
    failures.to_csv(QA_FAILURES_PATH, index=False)

    qa = build_qa_summary(out)
    qa.to_csv(QA_SUMMARY_PATH, index=False)

    print()
    print("=" * 80)
    print("BATCH COMPLETE")
    print("=" * 80)
    print(f"Rows     : {len(out):,}")
    print(f"Success  : {int(out['status'].eq('success').sum()):,}")
    print(f"Failures : {int(out['status'].ne('success').sum()):,}")
    print()
    print("Status counts:")
    print(out["status"].value_counts(dropna=False).to_string())
    print()
    print("Event-rule counts:")
    print(
        out.loc[
            out["event_rule"].astype(str).ne(""),
            "event_rule",
        ].value_counts(dropna=False).to_string()
    )
    print()
    print(f"Final output : {FINAL_PATH}")
    print(f"QA summary   : {QA_SUMMARY_PATH}")
    print(f"Failures     : {QA_FAILURES_PATH}")
    print(f"Checkpoint   : {CHECKPOINT_PATH}")


if __name__ == "__main__":
    main()
