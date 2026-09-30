"""Cache stock splits needed to align Yahoo historical prices with SEC shares."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import time

import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
COMPANIES = ROOT / "data/metadata/companies_100.csv"
PRICES = ROOT / "data/market_data/daily_prices.csv"
OUT = ROOT / "data/market_data/stock_splits.csv"
COVERAGE = ROOT / "data/market_data/stock_split_coverage.csv"


def fetch(ticker: str, last_price_date: pd.Timestamp) -> tuple[list[dict], dict]:
    yahoo_ticker = ticker.replace(".", "-")
    last_error = ""
    for attempt in range(3):
        try:
            splits = yf.Ticker(yahoo_ticker).splits
            rows = [
                {"ticker": ticker, "date": stamp.date().isoformat(), "ratio": float(ratio)}
                for stamp, ratio in splits.items()
                if stamp.date() <= last_price_date.date() and float(ratio) > 0
            ]
            return rows, {"ticker": ticker, "status": "ok", "n_splits": len(rows)}
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(1 + attempt)
    return [], {"ticker": ticker, "status": last_error, "n_splits": 0}


def main() -> None:
    companies = pd.read_csv(COMPANIES)
    tickers = companies["ticker"].dropna().astype(str).str.upper().unique().tolist()
    last_price_date = pd.to_datetime(pd.read_csv(PRICES, usecols=["date"])["date"]).max()
    splits, coverage = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch, ticker, last_price_date): ticker for ticker in tickers}
        for future in as_completed(futures):
            rows, status = future.result()
            splits.extend(rows)
            coverage.append(status)
    coverage_df = pd.DataFrame(coverage).sort_values("ticker")
    if not coverage_df.status.eq("ok").all():
        failed = coverage_df.loc[coverage_df.status.ne("ok"), "ticker"].tolist()
        raise RuntimeError(f"Stock-split lookup failed for: {failed}")
    pd.DataFrame(splits, columns=["ticker", "date", "ratio"]).sort_values(
        ["ticker", "date"]
    ).to_csv(OUT, index=False)
    coverage_df.to_csv(COVERAGE, index=False)
    print(f"Checked {len(tickers)} tickers; saved {len(splits)} split events through {last_price_date.date()}.")


if __name__ == "__main__":
    main()
