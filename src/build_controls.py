#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BUILD CONTROL VARIABLES — Size / BM / Volatility / Turnover
============================================================

Nguồn:
    - filings_2016_2025.csv
    - daily_prices.csv
    - SEC Company Facts API

Định nghĩa:
    Size:
        ln(shares outstanding at filing date
           * stock price on trading day -1)

    BM:
        book equity / market capitalization
        book equity = most recent annual SEC XBRL fact <= 1 year
        before filing date.
        BM <= 0 => missing for regression.
        Positive BM is winsorized at 1% / 99%.

    Turnover:
        ln(
            sum(volume, trading days [-252,-6])
            / shares outstanding
        )

    Volatility:
        standard deviation of daily market-model residuals using
        up to 60 calendar months ending at the month before filing.

Outputs:
    data/metadata/controls/controls_item7.csv
    data/metadata/controls/control_qa.csv
    data/metadata/controls/sec_facts_cache/*.json
"""

from __future__ import annotations

import json
import math
import os
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm


# ============================================================
# PATHS
# ============================================================

FILINGS_PATH = Path("data/metadata/filings_2016_2025.csv")
EVENT_PATH = Path(
    "data/metadata/event_study_final/event_filing_results.csv"
)
PRICE_PATH = Path("data/market_data/daily_prices.csv")
SPLITS_PATH = Path("data/market_data/stock_splits.csv")
COVERAGE_PATH = Path("data/market_data/stock_split_coverage.csv")

OUT_DIR = Path("data/metadata/controls")
OUTPUT_PATH = OUT_DIR / "controls_item7.csv"
QA_PATH = OUT_DIR / "control_qa.csv"

CACHE_DIR = OUT_DIR / "sec_facts_cache"

MARKET_TICKER = "^GSPC"

REQUEST_SLEEP = 0.25
REQUEST_TIMEOUT = 30

USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "",
)


# ============================================================
# SEC
# ============================================================

SEC_URL = (
    "https://data.sec.gov/api/xbrl/companyfacts/"
    "CIK{cik}.json"
)


def get_sec_facts(cik: str) -> dict:

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cik10 = str(cik).strip().zfill(10)
    cache_path = CACHE_DIR / f"CIK{cik10}.json"

    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass

    if not USER_AGENT:
        raise RuntimeError("Set SEC_USER_AGENT to a project name and contact email")

    url = SEC_URL.format(cik=cik10)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",
    }

    last_error = None

    for attempt in range(5):

        try:

            response = requests.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code == 200:

                data = response.json()

                with open(
                    cache_path,
                    "w",
                    encoding="utf-8",
                ) as fh:
                    json.dump(
                        data,
                        fh,
                        ensure_ascii=False,
                    )

                time.sleep(REQUEST_SLEEP)

                return data

            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue

            response.raise_for_status()

        except Exception as exc:
            last_error = exc
            time.sleep(2 ** attempt)

    raise RuntimeError(
        f"SEC Company Facts failed for CIK {cik10}: {last_error}"
    )


# ============================================================
# FACT HELPERS
# ============================================================

def iter_fact_entries(
    facts: dict,
    taxonomy: str,
    tag: str,
) -> list[dict]:

    try:
        block = facts["facts"][taxonomy][tag]
    except KeyError:
        return []

    units = block.get("units", {})

    entries = []

    for unit_name, values in units.items():

        for item in values:

            row = dict(item)
            row["_unit"] = unit_name
            row["_tag"] = tag
            row["_taxonomy"] = taxonomy

            entries.append(row)

    return entries


def choose_shares(
    facts: dict,
    filing_date: pd.Timestamp,
) -> tuple[float | None, str, str, str]:

    """
    Prefer DEI cover-page shares outstanding.
    Fallback: us-gaap CommonStockSharesOutstanding.
    """

    candidates = []

    # Primary source: DEI
    candidates.extend(
        iter_fact_entries(
            facts,
            "dei",
            "EntityCommonStockSharesOutstanding",
        )
    )

    if candidates:
        source = "dei_EntityCommonStockSharesOutstanding"
    else:
        candidates.extend(
            iter_fact_entries(
                facts,
                "us-gaap",
                "CommonStockSharesOutstanding",
            )
        )
        source = "us-gaap_CommonStockSharesOutstanding"

    if not candidates:
        return None, source, "missing", ""

    valid = []

    for row in candidates:

        if row.get("_unit") != "shares":
            continue

        if str(row.get("form", "")).upper() not in {
            "10-K",
            "10-K/A",
        }:
            continue

        try:
            filed = pd.Timestamp(row["filed"])
            end = pd.Timestamp(row["end"])
            value = float(row["val"])
        except Exception:
            continue

        if filed > filing_date:
            continue

        if end > filing_date:
            continue

        if value <= 0:
            continue

        valid.append(
            (
                end,
                filed,
                value,
                row,
            )
        )

    if not valid:
        return None, source, "no_valid_10k_fact", ""

    # Prefer latest as-of date, then latest filed date.
    valid.sort(
        key=lambda x: (x[0], x[1]),
        reverse=True,
    )

    asof, _, value, _ = valid[0]

    return value, source, "ok", asof.strftime("%Y-%m-%d")


BOOK_EQUITY_TAGS = [
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterestAndTemporaryEquity",
    "PartnersCapital",
]


def choose_book_equity(
    facts: dict,
    filing_date: pd.Timestamp,
) -> tuple[float | None, str, str, str]:

    """
    Choose the latest annual equity fact no more than one year
    before filing date.

    Preference:
        1. exact fiscal report date where possible
        2. latest valid annual 10-K fact
    """

    all_candidates = []

    for tag in BOOK_EQUITY_TAGS:

        entries = iter_fact_entries(
            facts,
            "us-gaap",
            tag,
        )

        for row in entries:

            if row.get("_unit") not in {
                "USD",
                "USD/shares",
                "USD",
            }:
                continue

            if str(row.get("form", "")).upper() not in {
                "10-K",
                "10-K/A",
            }:
                continue

            try:
                filed = pd.Timestamp(row["filed"])
                end = pd.Timestamp(row["end"])
                value = float(row["val"])
            except Exception:
                continue

            if filed > filing_date:
                continue

            if end > filing_date:
                continue

            age_days = (
                filing_date - end
            ).days

            if age_days < 0 or age_days > 366:
                continue

            all_candidates.append(
                (
                    end,
                    filed,
                    value,
                    tag,
                    age_days,
                )
            )

    if not all_candidates:
        return (
            None,
            "",
            "missing",
            "no_annual_equity_fact_within_1_year",
        )

    # Latest balance-sheet date first.
    all_candidates.sort(
        key=lambda x: (
            x[0],
            x[1],
        ),
        reverse=True,
    )

    end, filed, value, tag, age_days = all_candidates[0]

    return (
        value,
        tag,
        "ok",
        str(end.date()),
    )


# ============================================================
# MARKET DATA HELPERS
# ============================================================

def previous_trading_price(
    ticker_df: pd.DataFrame,
    filing_date: pd.Timestamp,
) -> tuple[float | None, str | None]:

    prior = ticker_df[
        ticker_df["date"] < filing_date
    ].sort_values("date")

    if prior.empty:
        return None, None

    row = prior.iloc[-1]

    price = pd.to_numeric(
        row["close"],
        errors="coerce",
    )

    if not np.isfinite(price) or price <= 0:
        return None, None

    return (
        float(price),
        str(row["date"].date()),
    )


def split_factor(splits: pd.DataFrame, ticker: str, shares_asof: str,
                 last_price_date: pd.Timestamp) -> float:
    """Align historical SEC shares with Yahoo's split-adjusted Close/Volume."""
    asof = pd.Timestamp(shares_asof)
    relevant = splits.loc[
        splits["ticker"].eq(ticker)
        & splits["date"].gt(asof)
        & splits["date"].le(last_price_date), "ratio"
    ]
    return float(relevant.prod()) if not relevant.empty else 1.0


def compute_turnover(
    ticker_df: pd.DataFrame,
    filing_date: pd.Timestamp,
    shares: float,
) -> tuple[float | None, float | None, int]:

    if shares is None or shares <= 0:
        return None, None, 0

    prior = ticker_df[
        ticker_df["date"] < filing_date
    ].sort_values("date")

    if len(prior) < 60:
        return None, None, len(prior)

    # Trading days -252 through -6.
    period = prior.tail(252)

    if len(period) > 5:
        period = period.iloc[:-5]

    volume = pd.to_numeric(
        period["volume"],
        errors="coerce",
    ).dropna()

    volume = volume[volume >= 0]

    n = len(volume)

    if n < 60:
        return None, None, n

    total_volume = float(volume.sum())

    raw_turnover = total_volume / shares

    if raw_turnover <= 0:
        return None, None, n

    log_turnover = float(
        np.log(raw_turnover)
    )

    return (
        raw_turnover,
        log_turnover,
        n,
    )


def compute_volatility(
    ticker_df: pd.DataFrame,
    market_df: pd.DataFrame,
    filing_date: pd.Timestamp,
) -> tuple[float | None, float | None, int]:

    """
    Daily market model over up to 60 calendar months,
    ending at the end of the month before filing.

        R_i,t = alpha + beta R_m,t + epsilon_i,t

    Volatility = SD(epsilon_i,t)
    """

    prev_month = (
        filing_date.to_period("M") - 1
    )

    start_month = (
        prev_month - 59
    )

    start_date = (
        start_month
        .to_timestamp(how="start")
    )

    end_date = (
        prev_month
        .to_timestamp(how="end")
    )

    stock = ticker_df[
        (
            ticker_df["date"] >= start_date
        )
        & (
            ticker_df["date"] <= end_date
        )
    ][
        ["date", "return"]
    ].copy()

    market = market_df[
        (
            market_df["date"] >= start_date
        )
        & (
            market_df["date"] <= end_date
        )
    ][
        ["date", "return"]
    ].copy()

    stock["return"] = pd.to_numeric(
        stock["return"],
        errors="coerce",
    )

    market["return"] = pd.to_numeric(
        market["return"],
        errors="coerce",
    )

    merged = stock.merge(
        market,
        on="date",
        suffixes=("_i", "_m"),
    ).dropna()

    n = len(merged)

    if n < 60:
        return None, None, n

    y = merged["return_i"].to_numpy(
        dtype=float
    )

    x = merged["return_m"].to_numpy(
        dtype=float
    )

    X = sm.add_constant(x)

    try:
        fit = sm.OLS(y, X).fit()
        residuals = np.asarray(
            fit.resid,
            dtype=float,
        )

        volatility = float(
            np.std(
                residuals,
                ddof=1,
            )
        )

        beta = float(
            fit.params[1]
        )

    except Exception:
        return None, None, n

    return (
        volatility,
        beta,
        n,
    )


# ============================================================
# WINSORIZATION
# ============================================================

def winsorize_1pct(
    series: pd.Series,
) -> pd.Series:

    out = series.copy()

    valid = out.dropna()

    if valid.empty:
        return out

    lo = valid.quantile(0.01)
    hi = valid.quantile(0.99)

    return out.clip(
        lower=lo,
        upper=hi,
    )


# ============================================================
# MAIN
# ============================================================

def main() -> int:

    print("=" * 80)
    print("BUILD CONTROL VARIABLES")
    print("=" * 80)

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    filings = pd.read_csv(
        FILINGS_PATH
    )

    events = pd.read_csv(
        EVENT_PATH
    )

    prices = pd.read_csv(
        PRICE_PATH
    )

    coverage = pd.read_csv(COVERAGE_PATH)
    required_tickers = set(filings["ticker"].astype(str).str.upper().str.strip())
    checked = set(coverage.loc[coverage.status.eq("ok"), "ticker"])
    if not required_tickers.issubset(checked):
        raise ValueError("Missing verified split history for some companies")
    splits = pd.read_csv(SPLITS_PATH)
    splits["date"] = pd.to_datetime(splits["date"])
    last_price_date = pd.to_datetime(prices["date"]).max()

    filings["filing_date"] = pd.to_datetime(
        filings["filing_date"],
        errors="coerce",
    )

    events["filing_date"] = pd.to_datetime(
        events["filing_date"],
        errors="coerce",
    )

    prices["date"] = pd.to_datetime(
        prices["date"],
        errors="coerce",
    )

    filings["ticker"] = (
        filings["ticker"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    events["ticker"] = (
        events["ticker"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    prices["ticker"] = (
        prices["ticker"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    # --------------------------------------------------------
    # Only successful events
    # --------------------------------------------------------

    if "status" in events.columns:
        successful = events[
            events["status"].astype(str).str.lower()
            == "success"
        ].copy()
    else:
        successful = events.copy()

    print(
        f"Successful event rows: {len(successful)}"
    )

    # --------------------------------------------------------
    # Price lookup dictionary
    # --------------------------------------------------------

    price_groups = {
        ticker: group.sort_values("date").copy()
        for ticker, group
        in prices.groupby("ticker")
    }

    if MARKET_TICKER not in price_groups:
        print(
            f"ERROR: market ticker {MARKET_TICKER} "
            f"not found in daily_prices.csv"
        )
        return 1

    market_df = price_groups[
        MARKET_TICKER
    ].copy()

    # --------------------------------------------------------
    # CIK lookup
    # --------------------------------------------------------

    cik_map = (
        filings[
            ["ticker", "cik"]
        ]
        .drop_duplicates("ticker")
        .set_index("ticker")["cik"]
        .to_dict()
    )

    rows = []

    total = len(successful)

    for i, (_, event) in enumerate(
        successful.iterrows(),
        start=1,
    ):

        ticker = event["ticker"]
        filing_date = event["filing_date"]

        row = {
            "ticker": ticker,
            "filing_date": (
                filing_date.strftime("%Y-%m-%d")
                if pd.notna(filing_date)
                else ""
            ),
            "cik": cik_map.get(ticker),
            "shares_outstanding": np.nan,
            "shares_split_adjusted": np.nan,
            "split_factor": np.nan,
            "shares_source": "",
            "shares_status": "",
            "shares_asof": "",
            "price_tminus1": np.nan,
            "price_tminus1_date": "",
            "market_cap_tminus1": np.nan,
            "size": np.nan,
            "book_equity": np.nan,
            "book_equity_tag": "",
            "book_equity_status": "",
            "book_equity_end": "",
            "bm_raw": np.nan,
            "bm": np.nan,
            "log_bm": np.nan,
            "turnover_raw": np.nan,
            "turnover": np.nan,
            "turnover_obs": 0,
            "volatility": np.nan,
            "volatility_beta": np.nan,
            "volatility_obs": 0,
            "status": "failed",
            "failure_reason": "",
        }

        # ----------------------------------------------------
        # Validate
        # ----------------------------------------------------

        if ticker not in price_groups:
            row["failure_reason"] = (
                "ticker_missing_market_data"
            )
            rows.append(row)
            continue

        if pd.isna(filing_date):
            row["failure_reason"] = (
                "invalid_filing_date"
            )
            rows.append(row)
            continue

        cik = cik_map.get(ticker)

        if cik is None:
            row["failure_reason"] = (
                "cik_missing"
            )
            rows.append(row)
            continue

        stock_df = price_groups[ticker]

        # ----------------------------------------------------
        # SEC facts
        # ----------------------------------------------------

        try:
            facts = get_sec_facts(
                str(int(float(cik)))
            )
        except Exception as exc:
            row["failure_reason"] = (
                f"sec_facts_error:{type(exc).__name__}"
            )
            rows.append(row)
            continue

        shares, shares_source, shares_status, shares_asof = (
            choose_shares(
                facts,
                filing_date,
            )
        )

        row["shares_outstanding"] = (
            shares
            if shares is not None
            else np.nan
        )
        row["shares_source"] = shares_source
        row["shares_status"] = shares_status
        row["shares_asof"] = shares_asof

        if shares is not None:
            factor = split_factor(splits, ticker, shares_asof, last_price_date)
            row["split_factor"] = factor
            row["shares_split_adjusted"] = shares * factor

        # ----------------------------------------------------
        # Price t-1
        # ----------------------------------------------------

        price, price_date = (
            previous_trading_price(
                stock_df,
                filing_date,
            )
        )

        if price is None:
            row["failure_reason"] = (
                "missing_tminus1_price"
            )
            rows.append(row)
            continue

        row["price_tminus1"] = price
        row["price_tminus1_date"] = price_date

        # ----------------------------------------------------
        # Size
        # ----------------------------------------------------

        if shares is not None:

            market_cap = (
                price * row["shares_split_adjusted"]
            )

            if market_cap > 0:

                row[
                    "market_cap_tminus1"
                ] = market_cap

                row["size"] = float(
                    np.log(market_cap)
                )

        # ----------------------------------------------------
        # Book equity
        # ----------------------------------------------------

        (
            book_equity,
            book_tag,
            book_status,
            book_end,
        ) = choose_book_equity(
            facts,
            filing_date,
        )

        row["book_equity"] = (
            book_equity
            if book_equity is not None
            else np.nan
        )

        row["book_equity_tag"] = book_tag
        row["book_equity_status"] = book_status
        row["book_equity_end"] = book_end

        # BM
        if (
            book_equity is not None
            and shares is not None
            and row["market_cap_tminus1"] > 0
        ):

            bm_raw = (
                book_equity
                / row["market_cap_tminus1"]
            )

            row["bm_raw"] = bm_raw

            if bm_raw > 0:
                row["bm"] = bm_raw
                row["log_bm"] = (
                    np.log(bm_raw)
                )

        # ----------------------------------------------------
        # Turnover
        # ----------------------------------------------------

        if shares is not None:

            (
                turnover_raw,
                turnover_log,
                turnover_n,
            ) = compute_turnover(
                stock_df,
                filing_date,
                row["shares_split_adjusted"],
            )

            row["turnover_raw"] = (
                turnover_raw
                if turnover_raw is not None
                else np.nan
            )

            row["turnover"] = (
                turnover_log
                if turnover_log is not None
                else np.nan
            )

            row["turnover_obs"] = (
                turnover_n
            )

        # ----------------------------------------------------
        # Volatility
        # ----------------------------------------------------

        (
            volatility,
            vol_beta,
            vol_n,
        ) = compute_volatility(
            stock_df,
            market_df,
            filing_date,
        )

        row["volatility"] = (
            volatility
            if volatility is not None
            else np.nan
        )

        row["volatility_beta"] = (
            vol_beta
            if vol_beta is not None
            else np.nan
        )

        row["volatility_obs"] = vol_n

        # ----------------------------------------------------
        # QA
        # ----------------------------------------------------

        required = [
            row["size"],
            row["bm"],
            row["volatility"],
            row["turnover"],
        ]

        if all(
            pd.notna(x)
            and np.isfinite(float(x))
            for x in required
        ):
            row["status"] = "success"
        else:

            missing = []

            for name, value in zip(
                [
                    "size",
                    "bm",
                    "volatility",
                    "turnover",
                ],
                required,
            ):
                if (
                    pd.isna(value)
                    or not np.isfinite(
                        float(value)
                    )
                ):
                    missing.append(name)

            row["failure_reason"] = (
                "missing_controls:"
                + ",".join(missing)
            )

        rows.append(row)

        if i % 100 == 0:
            print(
                f"Processed {i}/{total}"
            )

    # --------------------------------------------------------
    # DataFrame
    # --------------------------------------------------------

    controls = pd.DataFrame(rows)

    # --------------------------------------------------------
    # BM winsorization
    # --------------------------------------------------------

    positive_bm = controls[
        controls["bm_raw"] > 0
    ]["bm_raw"]

    if not positive_bm.empty:

        lo = positive_bm.quantile(
            0.01
        )
        hi = positive_bm.quantile(
            0.99
        )

        controls["bm"] = (
            controls["bm_raw"]
            .where(
                controls["bm_raw"] > 0
            )
            .clip(
                lower=lo,
                upper=hi,
            )
        )

        controls["log_bm"] = np.where(
            controls["bm"] > 0,
            np.log(controls["bm"]),
            np.nan,
        )

        controls["bm_winsor_lower"] = lo
        controls["bm_winsor_upper"] = hi

    else:

        controls["bm_winsor_lower"] = np.nan
        controls["bm_winsor_upper"] = np.nan

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    controls.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    qa = (
        controls[
            [
                "ticker",
                "filing_date",
                "status",
                "failure_reason",
                "shares_status",
                "book_equity_status",
                "turnover_obs",
                "volatility_obs",
            ]
        ]
        .copy()
    )

    qa.to_csv(
        QA_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("\n" + "=" * 80)
    print("CONTROL BUILD COMPLETE")
    print("=" * 80)

    print(
        f"Rows processed : {len(controls)}"
    )

    print(
        f"Successful all-controls rows: "
        f"{(controls['status'] == 'success').sum()}"
    )

    print(
        f"Rows with incomplete controls: "
        f"{(controls['status'] != 'success').sum()}"
    )

    print(
        f"Unique firms: "
        f"{controls['ticker'].nunique()}"
    )

    print("\nCONTROL COVERAGE")

    for col in [
        "size",
        "bm",
        "volatility",
        "turnover",
    ]:
        print(
            f"  {col:<15} "
            f"{controls[col].notna().sum()}/"
            f"{len(controls)}"
        )

    print("\nBM winsorization:")

    if positive_bm.empty:
        print("  No positive BM observations.")
    else:
        print(
            f"  1% lower = {lo:.6g}"
        )
        print(
            f"  99% upper = {hi:.6g}"
        )

    print("\nOUTPUTS")
    print(OUTPUT_PATH)
    print(QA_PATH)
    print(CACHE_DIR)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
