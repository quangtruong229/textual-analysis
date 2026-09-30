from pathlib import Path
from zoneinfo import ZoneInfo
import argparse
import re

import numpy as np
import pandas as pd
import requests


# ============================================================
# CONFIG
# ============================================================

FILINGS_PATH = Path("data/metadata/filings_2016_2025.csv")
PRICE_PATH = Path("data/market_data/daily_prices.csv")
OUT_DIR = Path("data/metadata/controls")
PILOT_OUT = OUT_DIR / "eadret_pilot.csv"

BENCHMARK = "^GSPC"

# J&W Table 5 footnote: announcement session through +2.
# Keep configurable because the paper text also mentions [t-1, t+1].
EVENT_START = 0
EVENT_END = 2

MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0
EASTERN = ZoneInfo("America/New_York")

SEC_USER_AGENT = "truongungquang1@gmail.com"
SEC_HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
}

AAPL_CIK = "0000320193"


# ============================================================
# SEC
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


def load_submissions(cik: str) -> pd.DataFrame:
    """
    Load both SEC recent submissions and any historical submission files.

    SEC's main CIK submissions JSON can expose up to the recent filing set,
    while older filings are listed under filings.files. We combine all
    available submission records so old 2016 observations are not lost.
    """
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

        # Historical SEC submission files are flat arrays/dicts rather than
        # nested under filings.recent.
        hist_df = _normalize_submission_frame(hist_payload)
        if not hist_df.empty:
            frames.append(hist_df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    # Defensive de-duplication by accession number.
    if "accessionNumber" in combined.columns:
        combined = combined.drop_duplicates(
            subset=["accessionNumber"],
            keep="last",
        )

    return combined.sort_values(
        ["filingDate", "acceptanceDateTime", "accessionNumber"],
        na_position="last",
    ).reset_index(drop=True)


def _parse_utc_timestamp(value):
    if not value:
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
    # Item field is normally comma-separated, e.g. "2.02,9.01".
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
    Find the latest Item 2.02 8-K before the 10-K.

    Rule:
      - Earlier calendar date than the 10-K -> eligible.
      - Same calendar date -> eligible only if its acceptance timestamp
        is strictly earlier than the 10-K acceptance timestamp.
      - If the 10-K acceptance timestamp is unavailable, same-day candidates
        are conservatively excluded rather than ordered by filing date alone.
    """
    if submissions.empty:
        return None, "no_submissions"

    x = submissions.copy()

    x = x[
        x["form"].eq("8-K")
        & x["filingDate"].notna()
        & x["items"].map(has_item_202)
    ].copy()

    if x.empty:
        return None, "no_item_2_02_before_10k"

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
        # Without the 10-K acceptance timestamp we cannot safely order
        # same-day 8-K and 10-K filings.
        eligible = earlier_day

    x = x[eligible].copy()

    if x.empty:
        return None, "no_8k_before_10k"

    x = x.sort_values(
        ["filingDate", "acceptance_utc", "accessionNumber"],
        ascending=[False, False, False],
        na_position="last",
    ).reset_index(drop=True)

    return x.iloc[0].to_dict(), "success"


# ============================================================
# TRADING SESSION
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
    prices = prices.sort_values(["ticker", "date"])

    return prices


def acceptance_to_event_session(
    acceptance_datetime: str,
    trading_dates: pd.DatetimeIndex,
):
    if not acceptance_datetime:
        return pd.NaT, "missing_acceptance_timestamp"

    ts = pd.to_datetime(acceptance_datetime, utc=True, errors="coerce")
    if pd.isna(ts):
        return pd.NaT, "bad_acceptance_timestamp"

    et = ts.tz_convert(EASTERN)

    # SEC acceptance time is used to decide whether the information
    # is assigned to the same trading session or the next available one.
    same_day = pd.Timestamp(et.date())

    if et.hour > MARKET_CLOSE_HOUR or (
        et.hour == MARKET_CLOSE_HOUR and et.minute >= MARKET_CLOSE_MINUTE
    ):
        candidate = same_day + pd.Timedelta(days=1)
        rule = "AFTER_MARKET_CLOSE_NEXT_SESSION"
    else:
        candidate = same_day
        rule = "DURING_OR_BEFORE_MARKET_CLOSE"

    future = trading_dates[trading_dates >= candidate]

    if len(future) == 0:
        return pd.NaT, "no_future_trading_session"

    event_session = future[0]

    # Weekend/holiday is implicitly handled by selecting the next
    # available price session.
    if event_session != candidate and rule == "DURING_OR_BEFORE_MARKET_CLOSE":
        rule = "NON_TRADING_DAY_NEXT_SESSION"

    return event_session, rule


def trading_window(
    trading_dates: pd.DatetimeIndex,
    event_session: pd.Timestamp,
    start: int,
    end: int,
):
    matches = np.where(trading_dates == event_session)[0]
    if len(matches) == 0:
        return None

    idx = int(matches[0])
    lo = idx + start
    hi = idx + end

    if lo < 0 or hi >= len(trading_dates):
        return None

    return trading_dates[lo : hi + 1]


# ============================================================
# BUY-AND-HOLD RETURN
# ============================================================

def buy_hold_from_daily_returns(window: pd.DataFrame) -> float:
    r = pd.to_numeric(window["return"], errors="coerce").dropna()

    expected_len = EVENT_END - EVENT_START + 1
    if len(r) != expected_len:
        return np.nan

    return float(np.prod(1.0 + r.to_numpy(float)) - 1.0)


def get_window_return(
    prices: pd.DataFrame,
    ticker: str,
    dates: pd.DatetimeIndex,
):
    x = prices[
        prices["ticker"].eq(ticker)
        & prices["date"].isin(dates)
    ].sort_values("date")

    expected_len = len(dates)

    if len(x) != expected_len:
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

def process_one_filing(
    filing,
    submissions,
    prices,
):
    ticker = str(filing["ticker"]).strip().upper()
    cik = str(filing["cik"]).zfill(10)
    tenk_date = pd.Timestamp(filing["filing_date"])
    accession_10k = str(filing["accession_number"])

    tenk_acceptance_utc = get_10k_acceptance_timestamp(
        submissions,
        accession_10k,
    )

    announcement, ann_status = find_latest_earnings_announcement(
        submissions,
        tenk_date,
        tenk_acceptance_utc=tenk_acceptance_utc,
    )

    base = {
        "ticker": ticker,
        "cik": cik,
        "tenk_filing_date": tenk_date.date().isoformat(),
        "tenk_report_date": str(filing.get("report_date", "")),
        "tenk_accession": accession_10k,
        "tenk_acceptance_datetime_utc": (
            tenk_acceptance_utc.isoformat()
            if pd.notna(tenk_acceptance_utc) else ""
        ),
        "announcement_accession": "",
        "announcement_filing_date": "",
        "announcement_report_date": "",
        "acceptance_datetime_utc": "",
        "acceptance_datetime_et": "",
        "announcement_session": "",
        "event_start": EVENT_START,
        "event_end": EVENT_END,
        "event_rule": "",
        "window_dates": "",
        "stock_return": np.nan,
        "market_return": np.nan,
        "eadret": np.nan,
        "status": ann_status,
        "note": "",
    }

    if announcement is None:
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

    ts_utc = pd.to_datetime(acceptance_utc, utc=True, errors="coerce")
    if pd.isna(ts_utc):
        base["status"] = "bad_acceptance_timestamp"
        return base

    base["acceptance_datetime_et"] = ts_utc.tz_convert(EASTERN).isoformat()

    benchmark_dates = pd.DatetimeIndex(
        prices.loc[prices["ticker"].eq(BENCHMARK), "date"]
        .dropna()
        .sort_values()
        .unique()
    )

    event_session, event_rule = acceptance_to_event_session(
        acceptance_utc,
        benchmark_dates,
    )

    if pd.isna(event_session):
        base["status"] = event_rule
        return base

    dates = trading_window(
        benchmark_dates,
        event_session,
        EVENT_START,
        EVENT_END,
    )

    if dates is None:
        base["status"] = "insufficient_event_window"
        return base

    stock_ret, stock_status = get_window_return(prices, ticker, dates)
    market_ret, market_status = get_window_return(prices, BENCHMARK, dates)

    base.update({
        "announcement_session": event_session.date().isoformat(),
        "event_rule": event_rule,
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
        "Source: SEC Submissions (recent + historical) 8-K Item 2.02; "
        "announcement ordered against 10-K acceptance timestamp; "
        "mapped from acceptance timestamp to trading session; "
        "^GSPC benchmark; daily return from existing adjusted-close return column."
    )

    return base


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ticker",
        default="AAPL",
        help="Pilot ticker; default AAPL",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=10,
        help="Number of most recent filings for pilot",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output CSV path. Default: eadret_pilot_<TICKER>.csv",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    filings = pd.read_csv(FILINGS_PATH, dtype={"accession_number": str})
    filings["filing_date"] = pd.to_datetime(
        filings["filing_date"], errors="coerce"
    )

    ticker = args.ticker.strip().upper()
    company = filings[
        filings["ticker"].astype(str).str.upper().eq(ticker)
    ].sort_values("filing_date", ascending=False).head(args.n).copy()

    if company.empty:
        raise ValueError(f"No filings found for ticker={ticker}")

    prices = prepare_prices()

    results = []

    # One SEC Submissions request for the company, then reuse for all 10-Ks.
    cik = str(company.iloc[0]["cik"]).zfill(10)
    print(f"Ticker: {ticker}")
    print(f"CIK: {cik}")
    print(f"Pilot filings: {len(company)}")
    print(f"Event window: [{EVENT_START}, +{EVENT_END}]")
    print()

    submissions = load_submissions(cik)

    print(f"SEC submission records: {len(submissions)}")

    for _, filing in company.iterrows():
        row = process_one_filing(
            filing,
            submissions,
            prices,
        )
        results.append(row)

    out = pd.DataFrame(results)

    output_path = (
        Path(args.output)
        if args.output
        else OUT_DIR / f"eadret_pilot_{ticker}.csv"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    print()
    print("=" * 80)
    print("EADRET PILOT RESULT")
    print("=" * 80)
    print(out.to_string(index=False))
    print()
    print(f"Saved: {output_path}")
    print()
    print("Status counts:")
    print(out["status"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
