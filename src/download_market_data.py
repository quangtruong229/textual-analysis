from pathlib import Path
import argparse
import time

import pandas as pd
import yfinance as yf


COMPANIES = Path("data/metadata/companies_100.csv")
OUT_DIR = Path("data/market_data")
OUT_FILE = OUT_DIR / "daily_prices.csv"

# Earliest filing is in 2016, but estimation window goes back ~244 trading days.
START = "2015-01-01"
# Yahoo's end date is exclusive. This covers +22 trading sessions after the
# latest December 2025 filings, including the late-December C6 observations.
END = "2026-03-01"

BENCHMARK = "^GSPC"
BATCH_SIZE = 15


def load_tickers():
    df = pd.read_csv(COMPANIES)

    candidates = [
        c for c in df.columns
        if c.lower() in {"ticker", "symbol"}
    ]

    if not candidates:
        raise ValueError(
            "Không tìm thấy cột ticker/symbol trong companies_100.csv"
        )

    col = candidates[0]

    tickers = (
        df[col]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
        .drop_duplicates()
        .tolist()
    )

    # Yahoo uses BRK-B instead of BRK.B, etc.
    return [x.replace(".", "-") for x in tickers]


def download_one_batch(tickers, start=START):
    return yf.download(
        tickers=tickers,
        start=start,
        end=END,
        interval="1d",
        auto_adjust=False,
        actions=False,
        progress=True,
        threads=True,
        group_by="column",
        timeout=30,
    )


def multi_to_long(data, fallback_ticker=None):
    rows = []

    if isinstance(data.columns, pd.MultiIndex):
        available_tickers = list(
            data.columns.get_level_values(1).unique()
        )

        for ticker in available_tickers:
            sub = pd.DataFrame(index=data.index)

            for field in [
                "Open",
                "High",
                "Low",
                "Close",
                "Adj Close",
                "Volume",
            ]:
                key = (field, ticker)
                if key in data.columns:
                    sub[field] = data[key]

            if "Adj Close" not in sub.columns:
                continue

            sub = sub.reset_index()

            for _, r in sub.iterrows():
                if pd.isna(r["Adj Close"]):
                    continue

                rows.append({
                    "ticker": str(ticker).upper(),
                    "date": pd.to_datetime(r["Date"]).date(),
                    "open": r.get("Open"),
                    "high": r.get("High"),
                    "low": r.get("Low"),
                    "close": r.get("Close"),
                    "adj_close": r.get("Adj Close"),
                    "volume": r.get("Volume"),
                })

    else:
        sub = data.reset_index()

        ticker = fallback_ticker

        for _, r in sub.iterrows():
            if pd.isna(r.get("Adj Close")):
                continue

            rows.append({
                "ticker": str(ticker).upper()
                if ticker else None,
                "date": pd.to_datetime(r["Date"]).date(),
                "open": r.get("Open"),
                "high": r.get("High"),
                "low": r.get("Low"),
                "close": r.get("Close"),
                "adj_close": r.get("Adj Close"),
                "volume": r.get("Volume"),
            })

    return pd.DataFrame(rows)


def extend_prices(existing: pd.DataFrame, downloaded: pd.DataFrame) -> pd.DataFrame:
    """Append new sessions without rewriting the previously audited prices.

    Yahoo may restate historical adjusted closes after later dividends/splits.
    Align each downloaded series to its last overlapping saved session before
    computing returns across the old/new boundary.
    """
    existing = existing.copy()
    downloaded = downloaded.copy()
    for frame in (existing, downloaded):
        frame["date"] = pd.to_datetime(frame["date"])
        if frame.duplicated(["ticker", "date"]).any():
            raise ValueError("Duplicate ticker/date in market prices")
    appended = []
    for ticker, new_group in downloaded.groupby("ticker"):
        old_group = existing.loc[existing.ticker.eq(ticker)].sort_values("date")
        if old_group.empty:
            raise ValueError(f"No saved price history for {ticker}")
        new_group = new_group.sort_values("date")
        overlap = old_group[["date", "adj_close"]].merge(
            new_group[["date", "adj_close"]], on="date", suffixes=("_old", "_new")
        )
        if overlap.empty:
            raise ValueError(f"No overlapping price session for {ticker}")
        anchor = overlap.iloc[-1]
        scale = float(anchor.adj_close_old / anchor.adj_close_new)
        if not pd.notna(scale) or scale <= 0:
            raise ValueError(f"Invalid adjusted-close scale for {ticker}")
        tail = new_group.loc[new_group.date.gt(old_group.date.max())].copy()
        if tail.empty:
            continue
        tail["adj_close"] = tail["adj_close"].astype(float) * scale
        prior = float(old_group.iloc[-1].adj_close)
        tail["return"] = tail["adj_close"].pct_change(fill_method=None)
        tail.loc[tail.index[0], "return"] = float(tail.iloc[0].adj_close / prior - 1)
        appended.append(tail)
    if not appended:
        raise ValueError("No new market sessions downloaded")
    return (pd.concat([existing, *appended], ignore_index=True)
            .sort_values(["ticker", "date"]).reset_index(drop=True))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download or extend daily market prices")
    parser.add_argument("--extend", action="store_true",
                        help="Append new sessions to the existing audited CSV")
    args = parser.parse_args(argv)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str((OUT_DIR / ".yfinance_cache").resolve()))

    existing = None
    start_date = START
    if args.extend:
        if not OUT_FILE.exists():
            parser.error("--extend requires the existing daily_prices.csv")
        existing = pd.read_csv(OUT_FILE, low_memory=False)
        market_dates = pd.to_datetime(existing.loc[existing.ticker.eq(BENCHMARK), "date"])
        if market_dates.empty:
            parser.error("Existing prices have no benchmark sessions")
        start_date = (market_dates.max() - pd.Timedelta(days=14)).strftime("%Y-%m-%d")

    tickers = load_tickers()

    print("=" * 80)
    print("MARKET DATA DOWNLOAD")
    print("=" * 80)
    print("Company tickers:", len(tickers))
    print("Benchmark:", BENCHMARK)
    print("Period:", start_date, "to", END)

    frames = []
    failures = []

    for start in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[start:start + BATCH_SIZE]

        print()
        print(
            f"Batch {start + 1}-"
            f"{min(start + BATCH_SIZE, len(tickers))}"
            f"/{len(tickers)}"
        )

        try:
            data = download_one_batch(batch, start=start_date)
            long = multi_to_long(data)

            if not long.empty:
                frames.append(long)
                print("Rows received:", len(long))
                missing = set(batch) - set(long["ticker"])
                if missing:
                    failures.extend(sorted(missing))
                    print("NO DATA:", sorted(missing))
            else:
                failures.extend(batch)
                print("NO DATA:", batch)

        except Exception as exc:
            failures.extend(batch)
            print("BATCH ERROR:", exc)

        time.sleep(1)

    print()
    print("=" * 80)
    print("BENCHMARK DOWNLOAD")
    print("=" * 80)

    try:
        market = yf.download(
            tickers=BENCHMARK,
            start=start_date,
            end=END,
            interval="1d",
            auto_adjust=False,
            actions=False,
            progress=True,
            threads=False,
            timeout=30,
        )

        market_long = multi_to_long(
            market,
            fallback_ticker=BENCHMARK,
        )

        if not market_long.empty:
            market_long["ticker"] = BENCHMARK
            frames.append(market_long)
        else:
            raise RuntimeError("Benchmark returned no rows.")

    except Exception as exc:
        raise RuntimeError(
            f"Benchmark download failed: {exc}"
        )

    if not frames:
        raise RuntimeError("No market data downloaded.")
    if args.extend and failures:
        raise RuntimeError(f"Price extension incomplete for: {sorted(set(failures))}")

    out = pd.concat(frames, ignore_index=True)

    out["date"] = pd.to_datetime(out["date"])

    out = (
        out
        .drop_duplicates(["ticker", "date"])
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)
    )

    if existing is not None:
        if BENCHMARK not in set(out.ticker):
            raise RuntimeError("Cannot extend prices without the benchmark")
        out = extend_prices(existing, out)
    else:
        out["return"] = out.groupby("ticker")["adj_close"].pct_change(fill_method=None)

    out.to_csv(
        OUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 80)
    print("MARKET DATA COMPLETE")
    print("=" * 80)
    print(
        "Company tickers downloaded:",
        out.loc[
            out["ticker"] != BENCHMARK,
            "ticker"
        ].nunique(),
    )
    print(
        "Benchmark rows:",
        int((out["ticker"] == BENCHMARK).sum()),
    )
    print("Total rows:", len(out))
    print("Failed tickers:", sorted(set(failures)))
    print("Output:", OUT_FILE)


if __name__ == "__main__":
    main()
