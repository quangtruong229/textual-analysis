from pathlib import Path
import math

import numpy as np
import pandas as pd
from scipy.stats import norm


# ============================================================
# PATHS
# ============================================================

TONE_PATH = Path(
    "data/metadata/tone_method_item7.csv"
)

PRICE_PATH = Path(
    "data/market_data/daily_prices.csv"
)

OUT_DIR = Path(
    "data/metadata/event_study"
)

EVENT_LONG = OUT_DIR / "event_ar_long.csv"
EVENT_FILING = OUT_DIR / "event_filing_results.csv"
EVENT_SUMMARY = OUT_DIR / "event_study_summary.csv"


# ============================================================
# SETTINGS — MATCH GROUP METHOD
# ============================================================

EST_START = -244
EST_END = -6

EVENT_START = -5
EVENT_END = 5

BENCHMARK = "^GSPC"

CAR_WINDOWS = {
    "CAR_m1_p1": (-1, 1),
    "CAR_0_p3": (0, 3),
    "CAR_m3_p3": (-3, 3),
    "CAR_m5_p5": (-5, 5),
}


# ============================================================
# HELPERS
# ============================================================

def yahoo_ticker(ticker):
    return str(ticker).strip().upper().replace(".", "-")


def pvalue_from_z(z):
    if z is None or not np.isfinite(z):
        return np.nan

    return 2.0 * norm.sf(abs(z))


def safe_mean(values):
    values = pd.Series(values).dropna()

    if values.empty:
        return np.nan

    return float(values.mean())


# ============================================================
# MARKET MODEL
# ============================================================

def estimate_market_model(
    estimation,
):
    """
    R_i,t = alpha_i + beta_i R_m,t + epsilon_i,t

    Uses closed-form OLS to match the formula sheet.
    """

    y = estimation["firm_return"].to_numpy(
        dtype=float
    )

    x = estimation["market_return"].to_numpy(
        dtype=float
    )

    mask = (
        np.isfinite(y)
        & np.isfinite(x)
    )

    y = y[mask]
    x = x[mask]

    n = len(y)

    if n < (EST_END - EST_START + 1):
        return None

    x_bar = x.mean()
    y_bar = y.mean()

    denominator = np.sum(
        (x - x_bar) ** 2
    )

    if denominator <= 0:
        return None

    beta = np.sum(
        (x - x_bar)
        * (y - y_bar)
    ) / denominator

    alpha = (
        y_bar
        - beta * x_bar
    )

    residuals = (
        y
        - alpha
        - beta * x
    )

    # Formula sheet: residual variance divided by L1 - 2.
    residual_var = (
        np.sum(residuals ** 2)
        / (n - 2)
    )

    return {
        "alpha": float(alpha),
        "beta": float(beta),
        "residual_var": float(residual_var),
        "market_mean": float(x_bar),
        "firm_mean": float(y_bar),
        "n_estimation": int(n),
    }


# ============================================================
# CONSTANT MEAN MODEL
# ============================================================

def estimate_constant_mean(
    estimation,
):
    y = pd.to_numeric(
        estimation["firm_return"],
        errors="coerce",
    ).dropna().to_numpy()

    if len(y) < (
        EST_END - EST_START + 1
    ):
        return None

    mu = float(y.mean())

    residuals = y - mu

    residual_var = (
        np.sum(residuals ** 2)
        / (len(y) - 1)
    )

    return {
        "mu": mu,
        "residual_var": float(
            residual_var
        ),
        "n_estimation": int(
            len(y)
        ),
    }


# ============================================================
# PROCESS ONE FILING
# ============================================================

def process_event(
    filing,
    prices,
):
    original_ticker = str(
        filing["ticker"]
    ).strip().upper()

    ticker = yahoo_ticker(
        original_ticker
    )

    filing_date = pd.Timestamp(
        filing["filing_date"]
    )

    firm = prices[
        prices["ticker"] == ticker
    ].copy()

    market = prices[
        prices["ticker"] == BENCHMARK
    ].copy()

    if firm.empty:
        return None, [], "firm_missing"

    if market.empty:
        return None, [], "market_missing"

    merged = firm[
        ["date", "return", "adj_close"]
    ].rename(
        columns={
            "return": "firm_return",
            "adj_close": "firm_adj_close",
        }
    ).merge(
        market[
            ["date", "return", "adj_close"]
        ].rename(
            columns={
                "return": "market_return",
                "adj_close": "market_adj_close",
            }
        ),
        on="date",
        how="inner",
    )

    merged = (
        merged
        .sort_values("date")
        .reset_index(drop=True)
    )

    merged = merged[
        merged["firm_return"].notna()
        & merged["market_return"].notna()
    ].copy()

    if merged.empty:
        return None, [], "no_returns"

    # --------------------------------------------------------
    # Event date
    # --------------------------------------------------------

    exact = merged[
        merged["date"] == filing_date
    ]

    event_date_shift = 0

    if exact.empty:
        candidates = merged[
            merged["date"] >= filing_date
        ]

        if candidates.empty:
            return None, [], "no_event_date"

        event_date = candidates.iloc[0]["date"]
        event_date_shift = 1

    else:
        event_date = exact.iloc[0]["date"]

    event_idx_list = merged.index[
        merged["date"] == event_date
    ].tolist()

    if not event_idx_list:
        return None, [], "event_index_missing"

    event_idx = event_idx_list[0]

    est_start_idx = (
        event_idx + EST_START
    )
    est_end_idx = (
        event_idx + EST_END
    )

    event_start_idx = (
        event_idx + EVENT_START
    )
    event_end_idx = (
        event_idx + EVENT_END
    )

    if est_start_idx < 0:
        return None, [], "insufficient_estimation_history"

    if event_end_idx >= len(merged):
        return None, [], "insufficient_event_forward_window"

    estimation = merged.iloc[
        est_start_idx:
        est_end_idx + 1
    ].copy()

    event = merged.iloc[
        event_start_idx:
        event_end_idx + 1
    ].copy()

    if len(estimation) != (
        EST_END - EST_START + 1
    ):
        return None, [], "bad_estimation_length"

    if len(event) != (
        EVENT_END - EVENT_START + 1
    ):
        return None, [], "bad_event_length"

    # --------------------------------------------------------
    # Estimate models
    # --------------------------------------------------------

    mm = estimate_market_model(
        estimation
    )

    cm = estimate_constant_mean(
        estimation
    )

    if mm is None:
        return None, [], "market_model_failed"

    if cm is None:
        return None, [], "constant_mean_failed"

    market_mean = float(
        estimation["market_return"].mean()
    )

    # --------------------------------------------------------
    # Event-time index
    # --------------------------------------------------------

    event = event.copy()

    event["event_time"] = (
        np.arange(
            EVENT_START,
            EVENT_END + 1,
        )
    )

    # --------------------------------------------------------
    # Expected returns / AR
    # --------------------------------------------------------

    event["expected_constant_mean"] = cm["mu"]

    event["ar_constant_mean"] = (
        event["firm_return"]
        - event["expected_constant_mean"]
    )

    event["expected_market_adjusted"] = (
        event["market_return"]
    )

    event["ar_market_adjusted"] = (
        event["firm_return"]
        - event["expected_market_adjusted"]
    )

    event["expected_market_model"] = (
        mm["alpha"]
        + mm["beta"]
        * event["market_return"]
    )

    event["ar_market_model"] = (
        event["firm_return"]
        - event["expected_market_model"]
    )

    # --------------------------------------------------------
    # Filing-level result
    # --------------------------------------------------------

    result = {
        "ticker": original_ticker,
        "yahoo_ticker": ticker,
        "filing_date": filing_date,
        "event_date": event_date,
        "event_date_shift": event_date_shift,
        "accession_number": filing[
            "accession_number"
        ],

        "alpha": mm["alpha"],
        "beta": mm["beta"],
        "residual_var": mm[
            "residual_var"
        ],
        "residual_sd": math.sqrt(
            max(
                mm["residual_var"],
                0.0,
            )
        ),
        "n_estimation": mm[
            "n_estimation"
        ],

        "n_event_days": len(event),
    }

    # CAR for all three models.
    for model in [
        "constant_mean",
        "market_adjusted",
        "market_model",
    ]:

        ar_col = f"ar_{model}"

        for name, (
            start,
            end,
        ) in CAR_WINDOWS.items():

            mask = (
                event["event_time"]
                >= start
            ) & (
                event["event_time"]
                <= end
            )

            result[
                f"{name}_{model}"
            ] = float(
                event.loc[
                    mask,
                    ar_col,
                ].sum()
            )

    # Store event-day ARs.
    event_rows = []

    for _, row in event.iterrows():

        event_rows.append({
            "ticker": original_ticker,
            "yahoo_ticker": ticker,
            "filing_date": filing_date,
            "event_date": event_date,
            "accession_number": filing[
                "accession_number"
            ],
            "event_time": int(
                row["event_time"]
            ),
            "date": row["date"],

            "firm_return": row[
                "firm_return"
            ],
            "market_return": row[
                "market_return"
            ],

            "ar_constant_mean": row[
                "ar_constant_mean"
            ],
            "ar_market_adjusted": row[
                "ar_market_adjusted"
            ],
            "ar_market_model": row[
                "ar_market_model"
            ],
        })

    return (
        result,
        event_rows,
        "success",
    )


# ============================================================
# CROSS-SECTIONAL SUMMARY
# ============================================================

def summarize_window(
    filing_results,
    event_long,
    ar_col,
    start,
    end,
):
    """
    MacKinlay-style cross-sectional aggregation.

    CAAR = mean(CAR_i)

    Var(CAAR) = (1/N^2) * sum(var(CAR_i))

    We use each firm's estimation residual variance and
    the event-window market-model adjustment term.
    """

    rows = filing_results[
        filing_results["n_estimation"].notna()
    ].copy()

    rows = rows.dropna(
        subset=[
            f"CAR_m5_p5_{ar_col}"
        ]
        if f"CAR_m5_p5_{ar_col}" in rows.columns
        else []
    )

    if rows.empty:
        return None

    car_col = None

    if start == -1 and end == 1:
        car_col = f"CAR_m1_p1_{ar_col}"
    elif start == 0 and end == 3:
        car_col = f"CAR_0_p3_{ar_col}"
    elif start == -3 and end == 3:
        car_col = f"CAR_m3_p3_{ar_col}"
    elif start == -5 and end == 5:
        car_col = f"CAR_m5_p5_{ar_col}"

    car = pd.to_numeric(
        rows[car_col],
        errors="coerce",
    ).dropna()

    N = len(car)

    if N == 0:
        return None

    caar = float(car.mean())

    # Basic cross-sectional standard error.
    sample_sd = float(
        car.std(ddof=1)
    ) if N > 1 else np.nan

    se = (
        sample_sd / math.sqrt(N)
        if N > 1
        else np.nan
    )

    t_value = (
        caar / se
        if np.isfinite(se) and se > 0
        else np.nan
    )

    p_value = (
        2.0 * norm.sf(abs(t_value))
        if np.isfinite(t_value)
        else np.nan
    )

    # Sign test.
    positive = int(
        (car > 0).sum()
    )

    sign_z = (
        (
            positive - 0.5 * N
        )
        / math.sqrt(
            0.25 * N
        )
    )

    sign_p = (
        2.0 * norm.sf(abs(sign_z))
    )

    return {
        "ar_model": ar_col,
        "window_start": start,
        "window_end": end,
        "N": N,
        "CAAR": caar,
        "sample_sd_CAR": sample_sd,
        "parametric_t": t_value,
        "parametric_p": p_value,
        "positive_CAR": positive,
        "negative_CAR": int(
            (car < 0).sum()
        ),
        "zero_CAR": int(
            (car == 0).sum()
        ),
        "sign_z": sign_z,
        "sign_p": sign_p,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("EVENT STUDY")
    print("=" * 80)

    tone = pd.read_csv(
        TONE_PATH,
        dtype={
            "accession_number": str,
        },
    )

    prices = pd.read_csv(
        PRICE_PATH
    )

    prices["date"] = pd.to_datetime(
        prices["date"]
    )

    prices["return"] = pd.to_numeric(
        prices["return"],
        errors="coerce",
    )

    print(
        "Tone rows:",
        len(tone),
    )

    print(
        "Price rows:",
        len(prices),
    )

    print(
        "Benchmark rows:",
        int(
            (
                prices["ticker"]
                == BENCHMARK
            ).sum()
        ),
    )

    filing_results = []
    event_rows = []
    failure_counts = {}

    for i, filing in tone.iterrows():

        result, rows, status = process_event(
            filing,
            prices,
        )

        if status == "success":

            filing_results.append(
                result
            )

            event_rows.extend(
                rows
            )

        else:

            failure_counts[status] = (
                failure_counts.get(
                    status,
                    0,
                ) + 1
            )

        if (
            i + 1
        ) % 100 == 0:

            print(
                f"Processed "
                f"{i + 1}/"
                f"{len(tone)}"
            )

    filings = pd.DataFrame(
        filing_results
    )

    event_long = pd.DataFrame(
        event_rows
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summaries = []

    for model in [
        "constant_mean",
        "market_adjusted",
        "market_model",
    ]:

        for name, (
            start,
            end,
        ) in CAR_WINDOWS.items():

            result = summarize_window(
                filings,
                event_long,
                model,
                start,
                end,
            )

            if result is not None:
                result["window"] = name
                summaries.append(
                    result
                )

    summary = pd.DataFrame(
        summaries
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    filings.to_csv(
        EVENT_FILING,
        index=False,
        encoding="utf-8-sig",
    )

    event_long.to_csv(
        EVENT_LONG,
        index=False,
        encoding="utf-8-sig",
    )

    summary.to_csv(
        EVENT_SUMMARY,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Print
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("EVENT STUDY COMPLETE")
    print("=" * 80)

    print(
        "Successful events:",
        len(filings),
    )

    print(
        "Failed events:",
        sum(failure_counts.values()),
    )

    if failure_counts:
        print()
        print("Failure reasons:")
        for key, value in sorted(
            failure_counts.items(),
            key=lambda x: -x[1],
        ):
            print(
                f"  {key}: {value}"
            )

    print()
    print("Mean beta:")

    if not filings.empty:
        print(
            filings["beta"].mean()
        )

        print(
            "Mean estimation observations:",
            filings[
                "n_estimation"
            ].mean(),
        )

        print(
            "Events shifted to next trading day:",
            int(
                (
                    filings[
                        "event_date_shift"
                    ]
                    == 1
                ).sum()
            ),
        )

    print()
    print("SUMMARY")
    print(
        summary.to_string(
            index=False
        )
    )

    print()
    print("Outputs:")
    print(EVENT_FILING)
    print(EVENT_LONG)
    print(EVENT_SUMMARY)


if __name__ == "__main__":
    main()
