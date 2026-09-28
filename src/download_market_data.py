from pathlib import Path
import time

import pandas as pd
import yfinance as yf


COMPANIES = Path("data/metadata/companies_100.csv")
OUT_DIR = Path("data/market_data")
OUT_FILE = OUT_DIR / "daily_prices.csv"

# Earliest filing is in 2016, but estimation window goes back ~244 trading days.
START = "2015-01-01"
END = "2026-01-15"

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


def download_one_batch(tickers):
    return yf.download(
        tickers=tickers,
        start=START,
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


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    tickers = load_tickers()

    print("=" * 80)
    print("MARKET DATA DOWNLOAD")
    print("=" * 80)
    print("Company tickers:", len(tickers))
    print("Benchmark:", BENCHMARK)
    print("Period:", START, "to", END)

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
            data = download_one_batch(batch)
            long = multi_to_long(data)

            if not long.empty:
                frames.append(long)
                print("Rows received:", len(long))
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
            start=START,
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

    out = pd.concat(frames, ignore_index=True)

    out["date"] = pd.to_datetime(out["date"])

    out = (
        out
        .drop_duplicates(["ticker", "date"])
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)
    )

    out["return"] = (
        out.groupby("ticker")["adj_close"]
        .pct_change()
    )

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
