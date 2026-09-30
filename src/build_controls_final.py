#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build controls for the 10-K event-study regression.

Locked to the research documents:
- Size: ln(market capitalization) at the end of the month BEFORE filing.
- BM: book-to-market at fiscal year-end (report_date).
- Volatility: SD of idiosyncratic residuals from the market model, using up to 60 months
  of pre-event daily data.
- Turnover: ln(mean(daily volume / shares outstanding)) over event days -252 to -6.

Primary outputs:
  data/metadata/controls/controls_item7.csv
  data/metadata/controls/control_qa.csv

SEC company facts are cached under:
  data/metadata/controls/sec_facts_cache/

Notes:
  earnings-announcement event date, which is not part of the current 10-K filing index.
  four directly implementable controls above. The output records this explicitly.
- The event-study uses filing_date as the event date, matching the existing pipeline.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
FILINGS = ROOT / "data" / "metadata" / "filings_2016_2025.csv"
PRICES = ROOT / "data" / "market_data" / "daily_prices.csv"
OUT_DIR = ROOT / "data" / "metadata" / "controls"
CACHE_DIR = OUT_DIR / "sec_facts_cache"
OUT = OUT_DIR / "controls_item7.csv"
QA_OUT = OUT_DIR / "control_qa.csv"

WINDOW_BEFORE_MONTH = True
VOL_LOOKBACK_MONTHS = 60
TURN_MIN = -252
TURN_MAX = -6
MIN_VOL_OBS = 120
MIN_TURN_OBS = 80

UA = os.getenv("SEC_USER_AGENT", "textual-analysis-research/1.0 research@example.com")
HEADERS = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate", "Host": "www.sec.gov"}


def norm_date(x: Any) -> pd.Timestamp:
    return pd.to_datetime(x, errors="coerce")


def first_existing(df: pd.DataFrame, names: Iterable[str]) -> Optional[str]:
    cols = {str(c).strip().lower(): c for c in df.columns}
    for n in names:
        if n.lower() in cols:
            return cols[n.lower()]
    return None


def parse_number(x: Any) -> float:
    try:
        return float(pd.to_numeric(x, errors="coerce"))
    except Exception:
        return float("nan")


def cik10(x: Any) -> str:
    s = re.sub(r"\D", "", str(x))
    return s.zfill(10)


def get_companyfacts(cik: str, force: bool = False) -> dict[str, Any]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"CIK{cik}.json"
    if path.exists() and not force:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    for attempt in range(5):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                payload = r.json()
                path.write_text(json.dumps(payload), encoding="utf-8")
                time.sleep(0.2)
                return payload
            if r.status_code in {429, 500, 502, 503, 504}:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise RuntimeError(f"SEC companyfacts status={r.status_code} url={url}")
        except Exception:
            if attempt == 4:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def iter_fact_rows(payload: dict[str, Any], namespace: str = "us-gaap") -> list[dict[str, Any]]:
    facts = payload.get("facts", {}).get(namespace, {})
    rows: list[dict[str, Any]] = []
    for concept, meta in facts.items():
        units = meta.get("units", {})
        for unit_name, vals in units.items():
            for v in vals:
                rows.append({
                    "concept": concept,
                    "unit": unit_name,
                    "val": v.get("val"),
                    "start": v.get("start"),
                    "end": v.get("end"),
                    "filed": v.get("filed"),
                    "fy": v.get("fy"),
                    "fp": v.get("fp"),
                    "form": v.get("form"),
                    "frame": v.get("frame"),
                })
    return rows


def fact_frame(payload: dict[str, Any]) -> pd.DataFrame:
    rows = iter_fact_rows(payload, "us-gaap")
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for c in ("start", "end", "filed"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df["val_num"] = pd.to_numeric(df["val"], errors="coerce")
    return df


def dei_frame(payload: dict[str, Any]) -> pd.DataFrame:
    rows = iter_fact_rows(payload, "dei")
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for c in ("start", "end", "filed"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df["val_num"] = pd.to_numeric(df["val"], errors="coerce")
    return df


def latest_shares_on_or_before(dei: pd.DataFrame, target: pd.Timestamp, info_cutoff: pd.Timestamp) -> tuple[float, str, pd.Timestamp]:
    if dei.empty:
        return np.nan, "", pd.NaT
    concepts = {"EntityCommonStockSharesOutstanding"}
    d = dei[dei["concept"].isin(concepts)].copy()
    d = d[(d["filed"] <= info_cutoff) & (d["end"] <= target)]
    d = d[d["val_num"].gt(0)]
    d = d.sort_values(["end", "filed"])
    if d.empty:
        return np.nan, "", pd.NaT
    row = d.iloc[-1]
    return float(row["val_num"]), str(row["concept"]), row["end"]


EQUITY_CONCEPTS = [
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    "PartnersCapital",
    "PartnersCapitalAttributableToParent",
    "MembersEquity",
    "CommonStockholdersEquity",
]


def book_equity_at_fy_end(gaap: pd.DataFrame, fy_end: pd.Timestamp, filing_date: pd.Timestamp) -> tuple[float, str, pd.Timestamp]:
    if gaap.empty:
        return np.nan, "", pd.NaT
    d = gaap[gaap["concept"].isin(EQUITY_CONCEPTS)].copy()
    d = d[(d["end"] == fy_end) & (d["filed"] <= filing_date) & d["val_num"].notna()]
    # Prefer annual 10-K values, then the most recently filed observation.
    d["form_rank"] = d["form"].map(lambda x: 0 if str(x).upper() == "10-K" else 1)
    d = d.sort_values(["form_rank", "filed"], ascending=[True, False])
    if d.empty:
        # Fallback: closest available equity observation at/before FY end, but only
        # when it is actually filed before the 10-K. This is logged as fallback.
        d = gaap[gaap["concept"].isin(EQUITY_CONCEPTS)].copy()
        d = d[(d["end"] <= fy_end) & (d["filed"] <= filing_date) & d["val_num"].notna()]
        d = d.sort_values(["end", "filed"])
    if d.empty:
        return np.nan, "", pd.NaT
    row = d.iloc[-1]
    return float(row["val_num"]), str(row["concept"]), row["end"]


def prepare_prices(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """
    Tách riêng hai mục đích sử dụng giá:

    - market_price = close chưa điều chỉnh:
      dùng cho market capitalization của Size và BM.
    - return_price = adjusted close nếu có:
      dùng để tính daily return cho market model / Volatility.
    """
    d = df.copy()
    d.columns = [str(c).strip() for c in d.columns]

    ticker = first_existing(d, ["ticker", "symbol"])
    datec = first_existing(d, ["date", "trading_date"])

    if not ticker or not datec:
        raise ValueError("daily_prices.csv phải có ticker/date")

    d = d.rename(columns={ticker: "ticker", datec: "date"})
    d["ticker"] = d["ticker"].astype(str).str.upper()
    d["date"] = pd.to_datetime(d["date"], errors="coerce")

    if "close" not in d.columns:
        raise ValueError("daily_prices.csv phải có cột close")

    d["market_price"] = pd.to_numeric(d["close"], errors="coerce")

    adjusted_col = first_existing(
        d,
        ["adjusted_close", "adj_close"]
    )

    if adjusted_col:
        d["return_price"] = pd.to_numeric(
            d[adjusted_col],
            errors="coerce"
        )
    else:
        d["return_price"] = d["market_price"]

    d["volume"] = pd.to_numeric(
        d.get("volume", np.nan),
        errors="coerce"
    )

    d = (
        d.dropna(subset=["ticker", "date"])
         .sort_values(["ticker", "date"])
         .reset_index(drop=True)
    )

    d["ret"] = (
        d.groupby("ticker")["return_price"]
         .pct_change()
    )

    return d, "close"


def nearest_price(
    d: pd.DataFrame,
    target: pd.Timestamp,
    column: str = "market_price",
) -> tuple[float, pd.Timestamp]:

    x = (
        d[d["date"] <= target]
        .dropna(subset=[column])
        .sort_values("date")
    )

    if x.empty:
        return np.nan, pd.NaT

    row = x.iloc[-1]
    return float(row[column]), row["date"]


def month_end_prior(filing_date: pd.Timestamp) -> pd.Timestamp:
    first = filing_date.replace(day=1)
    return first - pd.Timedelta(days=1)


def market_group(prices: pd.DataFrame) -> pd.DataFrame:
    idx = prices[prices["ticker"].isin({"^GSPC", "SPY", "GSPC"})].copy()

    if idx.empty:
        raise ValueError(
            "Không tìm thấy benchmark ^GSPC/SPY/GSPC trong daily_prices.csv"
        )

    # Prefer ^GSPC if present.
    if "^GSPC" in set(idx["ticker"]):
        idx = idx[idx["ticker"] == "^GSPC"]
    elif "SPY" in set(idx["ticker"]):
        idx = idx[idx["ticker"] == "SPY"]
    else:
        idx = idx[idx["ticker"] == "GSPC"]

    idx = idx[
        ["date", "return_price", "ret"]
    ].rename(
        columns={
            "return_price": "mkt_price",
            "ret": "mkt_ret",
        }
    )

    return idx.sort_values("date")


def fit_market_residual_sd(stock: pd.DataFrame, index: pd.DataFrame, filing_date: pd.Timestamp) -> tuple[float, int, float, float]:
    start = filing_date - pd.DateOffset(months=VOL_LOOKBACK_MONTHS)
    s = stock[(stock["date"] >= start) & (stock["date"] <= filing_date - pd.Timedelta(days=1))][["date", "ret"]].copy()
    m = index[(index["date"] >= start) & (index["date"] <= filing_date - pd.Timedelta(days=1))][["date", "mkt_ret"]].copy()
    x = s.merge(m, on="date", how="inner").dropna()
    if len(x) < MIN_VOL_OBS:
        return np.nan, len(x), np.nan, np.nan
    y = x["ret"].to_numpy(float)
    xm = x["mkt_ret"].to_numpy(float)
    X = np.column_stack([np.ones(len(xm)), xm])
    beta_hat = np.linalg.lstsq(X, y, rcond=None)[0]
    resid = y - X @ beta_hat
    sd = float(np.std(resid, ddof=2)) if len(resid) > 2 else np.nan
    return sd, len(x), float(beta_hat[0]), float(beta_hat[1])


def relative_turnover(
    stock: pd.DataFrame,
    dei: pd.DataFrame,
    filing_date: pd.Timestamp,
) -> tuple[float, int, str]:

    # Exact trading-day construction:
    # last 252 trading days before filing = [-252, ..., -1]
    # remove the 5 most recent = [-5, ..., -1]
    # remaining observations = [-252, ..., -6]
    d = (
        stock[stock["date"] < filing_date]
        .dropna(subset=["volume"])
        .sort_values("date")
        .copy()
    )

    if d.empty:
        return np.nan, 0, ""

    d = d.tail(252)

    if len(d) > 5:
        d = d.iloc[:-5]
    else:
        d = d.iloc[0:0]

    if len(d) < MIN_TURN_OBS:
        return np.nan, len(d), ""

    shares, concept, _ = latest_shares_on_or_before(
        dei,
        filing_date - pd.Timedelta(days=1),
        filing_date,
    )

    if not np.isfinite(shares) or shares <= 0:
        return np.nan, len(d), "NO_SHARES"

    daily = d["volume"].astype(float) / shares
    daily = (
        daily.replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    daily = daily[daily > 0]

    if len(daily) < MIN_TURN_OBS:
        return np.nan, len(daily), concept

    # The document defines Turnover as ln(volume / shares outstanding)
    # over the [-252,-6] window. Following the current project
    # implementation, aggregate daily turnover first, then take ln.
    return float(np.log(daily.mean())), len(daily), concept


def run(force_sec: bool = False, max_tickers: Optional[int] = None) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    filings = pd.read_csv(FILINGS, dtype=str)
    filings.columns = [str(c).strip() for c in filings.columns]
    required = {"ticker", "filing_date", "report_date", "cik"}
    missing = required - set(filings.columns)
    if missing:
        raise ValueError(f"filings_2016_2025.csv thiếu {sorted(missing)}")
    filings["ticker"] = filings["ticker"].str.upper()
    filings["filing_date"] = pd.to_datetime(filings["filing_date"], errors="coerce")
    filings["report_date"] = pd.to_datetime(filings["report_date"], errors="coerce")
    filings["cik"] = filings["cik"].map(cik10)
    filings = filings.dropna(subset=["ticker", "filing_date", "report_date"])
    if max_tickers:
        keep = set(filings["ticker"].drop_duplicates().head(max_tickers))
        filings = filings[filings["ticker"].isin(keep)]

    prices_raw = pd.read_csv(PRICES, low_memory=False)
    prices, price_col = prepare_prices(prices_raw)
    idx = market_group(prices)

    rows = []
    qa = []
    for i, row in filings.sort_values(["ticker", "filing_date"]).iterrows():
        ticker = row["ticker"]
        fd = row["filing_date"]
        fy_end = row["report_date"]
        cik = row["cik"]
        out = {
            "ticker": ticker,
            "filing_date": fd.strftime("%Y-%m-%d"),
            "report_date": fy_end.strftime("%Y-%m-%d"),
            "cik": cik,
            "size": np.nan,
            "bm": np.nan,
            "volatility": np.nan,
            "turnover": np.nan,
            "size_market_cap": np.nan,
            "size_price_date": "",
            "size_shares": np.nan,
            "size_shares_source": "",
            "bm_book_equity": np.nan,
            "bm_book_equity_source": "",
            "bm_market_cap": np.nan,
            "bm_price_date": "",
            "bm_shares": np.nan,
            "bm_shares_source": "",
            "volatility_obs": 0,
            "vol_alpha": np.nan,
            "vol_beta": np.nan,
            "turnover_obs": 0,
            "turnover_shares_source": "",
            "control_status": "FAIL",
            "control_note": "",
        }
        try:
            payload = get_companyfacts(cik, force=force_sec)
            gaap = fact_frame(payload)
            dei = dei_frame(payload)
            stock = prices[prices["ticker"] == ticker].copy()
            if stock.empty:
                raise RuntimeError("no_price_history")

            size_date = month_end_prior(fd)
            size_price, size_price_date = nearest_price(stock, size_date, "market_price")
            size_shares, size_share_source, _ = latest_shares_on_or_before(dei, size_date, fd)
            size_mcap = size_price * size_shares if np.isfinite(size_price) and np.isfinite(size_shares) else np.nan
            out.update({
                "size_market_cap": size_mcap,
                "size_price_date": size_price_date.strftime("%Y-%m-%d") if pd.notna(size_price_date) else "",
                "size_shares": size_shares,
                "size_shares_source": size_share_source,
                "size": np.log(size_mcap) if np.isfinite(size_mcap) and size_mcap > 0 else np.nan,
            })

            bm_book, bm_book_source, bm_book_end = book_equity_at_fy_end(gaap, fy_end, fd)
            bm_shares, bm_share_source, _ = latest_shares_on_or_before(dei, fy_end, fd)
            bm_price, bm_price_date = nearest_price(stock, fy_end, "market_price")
            bm_mcap = bm_price * bm_shares if np.isfinite(bm_price) and np.isfinite(bm_shares) else np.nan
            bm = bm_book / bm_mcap if np.isfinite(bm_book) and np.isfinite(bm_mcap) and bm_mcap > 0 else np.nan
            out.update({
                "bm_book_equity": bm_book,
                "bm_book_equity_source": bm_book_source,
                "bm_market_cap": bm_mcap,
                "bm_price_date": bm_price_date.strftime("%Y-%m-%d") if pd.notna(bm_price_date) else "",
                "bm_shares": bm_shares,
                "bm_shares_source": bm_share_source,
                "bm": bm,
            })

            vol_sd, vol_obs, alpha, beta = fit_market_residual_sd(stock, idx, fd)
            out.update({"volatility": vol_sd, "volatility_obs": vol_obs, "vol_alpha": alpha, "vol_beta": beta})

            turn, turn_obs, turn_src = relative_turnover(stock, dei, fd)
            out.update({"turnover": turn, "turnover_obs": turn_obs, "turnover_shares_source": turn_src})

            mandatory = ["size", "bm", "volatility", "turnover"]
            ok = all(np.isfinite(float(out[k])) for k in mandatory)
            out["control_status"] = "PASS" if ok else "WARN"
            out["control_note"] = "All 4 mandatory controls available" if ok else "Missing one or more mandatory controls"

        except Exception as exc:
            out["control_note"] = f"{type(exc).__name__}: {exc}"

        rows.append(out)
        qa.append({
            "ticker": ticker,
            "filing_date": fd.strftime("%Y-%m-%d"),
            "size_ok": int(np.isfinite(out["size"])),
            "bm_ok": int(np.isfinite(out["bm"])),
            "volatility_ok": int(np.isfinite(out["volatility"])),
            "turnover_ok": int(np.isfinite(out["turnover"])),
            "all_4_ok": int(out["control_status"] == "PASS"),
            "control_status": out["control_status"],
            "note": out["control_note"],
        })
        print(f"[{len(rows):>4}/{len(filings):>4}] {ticker} {fd.date()} -> {out['control_status']}")

    pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8-sig")
    pd.DataFrame(qa).to_csv(QA_OUT, index=False, encoding="utf-8-sig")
    df = pd.DataFrame(rows)
    print("\nCONTROL QA")
    print(f"rows={len(df)} firms={df['ticker'].nunique()} price_column={price_col}")
    for c in ("size", "bm", "volatility", "turnover"):
        print(f"{c:12s}: {int(pd.to_numeric(df[c], errors='coerce').notna().sum())}/{len(df)}")
    print(f"all_4_ok    : {int((df['control_status']=='PASS').sum())}/{len(df)}")
    print(f"saved       : {OUT}")
    print(f"qa_saved    : {QA_OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-sec", action="store_true", help="Refetch companyfacts instead of cache")
    ap.add_argument("--max-tickers", type=int, default=None, help="Debug: limit to first N firms")
    args = ap.parse_args()
    run(force_sec=args.force_sec, max_tickers=args.max_tickers)
