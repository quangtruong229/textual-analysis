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
    "data/metadata/event_study_final"
)

FILING_OUT = OUT_DIR / "event_filing_results.csv"
AR_OUT = OUT_DIR / "event_ar_long.csv"
DAILY_OUT = OUT_DIR / "event_daily_summary.csv"
SUMMARY_OUT = OUT_DIR / "event_study_summary.csv"

BENCHMARK = "^GSPC"

EST_START = -244
EST_END = -6

EVENT_START = -5
EVENT_END = 5

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
    return (
        str(ticker)
        .strip()
        .upper()
        .replace(".", "-")
    )


def two_sided_p(z):
    if not np.isfinite(z):
        return np.nan
    return float(
        2.0 * norm.sf(abs(z))
    )


# ============================================================
# MARKET MODEL
# ============================================================

def fit_market_model(estimation):
    y = estimation[
        "firm_return"
    ].to_numpy(float)

    x = estimation[
        "market_return"
    ].to_numpy(float)

    mask = (
        np.isfinite(y)
        & np.isfinite(x)
    )

    y = y[mask]
    x = x[mask]

    n = len(y)

    required_n = (
        EST_END - EST_START + 1
    )

    if n != required_n:
        return None

    xm = float(x.mean())
    ym = float(y.mean())

    sxx = float(
        np.sum(
            (x - xm) ** 2
        )
    )

    if sxx <= 0:
        return None

    beta = float(
        np.sum(
            (x - xm)
            * (y - ym)
        )
        / sxx
    )

    alpha = float(
        ym - beta * xm
    )

    residuals = (
        y
        - alpha
        - beta * x
    )

    residual_var = float(
        np.sum(
            residuals ** 2
        )
        / (n - 2)
    )

    return {
        "alpha": alpha,
        "beta": beta,
        "residual_var": residual_var,
        "market_mean": xm,
        "market_sxx": sxx,
        "n_estimation": n,
    }


# ============================================================
# EVENT-WINDOW VARIANCE
# ============================================================

def car_variance_market_model(
    event,
    model,
    start,
    end,
):
    """B4 in the supplied formula document: Var(CAR) ~= L * sigma_e^2.

    This is MacKinlay Eq. 11's large-estimation-window approximation.
    Do not sum individual forecast variances: estimated alpha/beta induce
    cross-day forecast covariance, even when the underlying errors are iid.
    """

    subset = event[
        (event["event_time"] >= start)
        & (event["event_time"] <= end)
    ].copy()

    if subset.empty:
        return np.nan

    return float(len(subset) * model["residual_var"])


# ============================================================
# PROCESS ONE FILING
# ============================================================

def process_filing(
    filing,
    prices,
):
    ticker_raw = str(
        filing["ticker"]
    ).strip().upper()

    ticker = yahoo_ticker(
        ticker_raw
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
        return None, None, None, "firm_missing"

    if market.empty:
        return None, None, None, "market_missing"

    firm = firm[
        [
            "date",
            "return",
            "adj_close",
        ]
    ].rename(
        columns={
            "return": "firm_return",
            "adj_close": "firm_adj_close",
        }
    )

    market = market[
        [
            "date",
            "return",
            "adj_close",
        ]
    ].rename(
        columns={
            "return": "market_return",
            "adj_close": "market_adj_close",
        }
    )

    # Use the benchmark's trading calendar, retaining missing firm returns.
    # Dropping rows would silently compress event time and move CAR windows.
    merged = market.merge(
        firm,
        on="date",
        how="left",
        validate="one_to_one",
    )

    merged = (
        merged
        .sort_values("date")
        .reset_index(drop=True)
    )

    if merged.empty:
        return None, None, None, "no_returns"

    # --------------------------------------------------------
    # Locate event date
    # --------------------------------------------------------

    exact = merged[
        merged["date"] == filing_date
    ]

    if exact.empty:
        future = merged[
            merged["date"] >= filing_date
        ]

        if future.empty:
            return (
                None,
                None,
                None,
                "no_event_date",
            )

        event_idx = int(
            future.index[0]
        )

        event_shift = 1

    else:
        event_idx = int(
            exact.index[0]
        )

        event_shift = 0

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
        return (
            None,
            None,
            None,
            "insufficient_estimation_history",
        )

    if event_end_idx >= len(merged):
        return (
            None,
            None,
            None,
            "insufficient_event_forward_window",
        )

    estimation = merged.iloc[
        est_start_idx:
        est_end_idx + 1
    ].copy()

    event = merged.iloc[
        event_start_idx:
        event_end_idx + 1
    ].copy()

    for frame, window in ((estimation, "estimation"), (event, "event")):
        if not np.isfinite(frame[["firm_return", "market_return"]].to_numpy(float)).all():
            return None, None, None, f"missing_returns_in_{window}_calendar"

    if len(estimation) != 239:
        return (
            None,
            None,
            None,
            "bad_estimation_length",
        )

    if len(event) != 11:
        return (
            None,
            None,
            None,
            "bad_event_length",
        )

    # Give both windows explicit relative time.
    estimation = estimation.copy()

    estimation["event_time"] = np.arange(
        EST_START,
        EST_END + 1,
    )

    event = event.copy()

    event["event_time"] = np.arange(
        EVENT_START,
        EVENT_END + 1,
    )

    # --------------------------------------------------------
    # Market model
    # --------------------------------------------------------

    model = fit_market_model(
        estimation
    )

    if model is None:
        return (
            None,
            None,
            None,
            "market_model_failed",
        )

    expected = (
        model["alpha"]
        + model["beta"]
        * event["market_return"]
    )

    event["expected_return"] = expected

    event["ar"] = (
        event["firm_return"]
        - event["expected_return"]
    )

    # --------------------------------------------------------
    # Filing-level results
    # --------------------------------------------------------

    result = {
        "ticker": ticker_raw,
        "yahoo_ticker": ticker,
        "filing_date": filing_date,
        "event_date": merged.loc[
            event_idx,
            "date"
        ],
        "event_date_shift": event_shift,
        "accession_number": filing[
            "accession_number"
        ],

        "alpha": model["alpha"],
        "beta": model["beta"],
        "residual_var": model[
            "residual_var"
        ],
        "residual_sd": math.sqrt(
            max(
                model["residual_var"],
                0.0,
            )
        ),
        "market_mean_estimation": model[
            "market_mean"
        ],
        "market_sxx_estimation": model[
            "market_sxx"
        ],
        "n_estimation": model[
            "n_estimation"
        ],
    }

    # CAR + variance for each required event window.
    for name, (start, end) in CAR_WINDOWS.items():

        mask = (
            event["event_time"] >= start
        ) & (
            event["event_time"] <= end
        )

        car = float(
            event.loc[
                mask,
                "ar",
            ].sum()
        )

        var_car = car_variance_market_model(
            event,
            model,
            start,
            end,
        )

        result[
            f"{name}"
        ] = car

        result[
            f"{name}_var"
        ] = var_car

        result[
            f"{name}_se"
        ] = (
            math.sqrt(var_car)
            if np.isfinite(var_car)
            else np.nan
        )

    # --------------------------------------------------------
    # Estimation AR rows for Brown-Warner
    # --------------------------------------------------------

    estimation["expected_return"] = (
        model["alpha"]
        + model["beta"]
        * estimation["market_return"]
    )

    estimation["ar"] = (
        estimation["firm_return"]
        - estimation["expected_return"]
    )

    estimation["ticker"] = ticker_raw
    estimation["accession_number"] = filing[
        "accession_number"
    ]
    estimation["filing_date"] = filing_date

    # --------------------------------------------------------
    # Event AR rows
    # --------------------------------------------------------

    event["ticker"] = ticker_raw
    event["accession_number"] = filing[
        "accession_number"
    ]
    event["filing_date"] = filing_date
    event["event_date"] = merged.loc[
        event_idx,
        "date"
    ]

    if event.loc[event.event_time.eq(0), "date"].iloc[0] != result["event_date"]:
        raise AssertionError("Event day zero must match the declared event date")

    return (
        result,
        event,
        estimation,
        "success",
    )


# ============================================================
# BROWN-WARNER
# ============================================================

def brown_warner_test(
    event_ar,
    estimation_ar,
):
    """
    Brown-Warner time-series test.

    For each relative day:
        Abar_t = mean_i(AR_it)

    Estimation period:
        Abar_bar = mean_t(Abar_t)
        S(Abar) =
            sqrt[
                sum_t(Abar_t-Abar_bar)^2/(L1-1)
            ]

    Daily event statistic:
        Z_t = Abar_t / S(Abar)

    For [-5,+5]:
        Z_BW =
            sum_t Abar_t /
            sqrt(11) * S(Abar)
    """

    est = (
        estimation_ar
        .groupby("event_time")["ar"]
        .mean()
        .sort_index()
    )

    if len(est) < 239:
        return None, None

    abar_bar = float(
        est.mean()
    )

    s_abar = float(
        np.sqrt(
            np.sum(
                (est - abar_bar) ** 2
            )
            / (len(est) - 1)
        )
    )

    event_daily = (
        event_ar
        .groupby("event_time")["ar"]
        .agg(
            AAR="mean",
            N="count",
        )
        .reset_index()
        .sort_values("event_time")
    )

    event_daily["BW_Z"] = (
        event_daily["AAR"]
        / s_abar
    )

    event_daily["BW_p"] = (
        event_daily["BW_Z"]
        .map(two_sided_p)
    )

    window = event_daily[
        (
            event_daily["event_time"] >= -5
        )
        &
        (
            event_daily["event_time"] <= 5
        )
    ]

    bw_11_z = (
        window["AAR"].sum()
        / (
            math.sqrt(
                len(window)
            )
            * s_abar
        )
    )

    bw_11_p = two_sided_p(
        bw_11_z
    )

    stats = {
        "BW_estimation_AAR_mean": abar_bar,
        "BW_estimation_AAR_sd": s_abar,
        "BW_11day_z": bw_11_z,
        "BW_11day_p": bw_11_p,
    }

    return (
        event_daily,
        stats,
    )


# ============================================================
# SIGN TEST
# ============================================================

def sign_test(
    filing_results,
    car_col,
):
    x = pd.to_numeric(
        filing_results[car_col],
        errors="coerce",
    ).dropna()

    N = len(x)

    positive = int(
        (x > 0).sum()
    )

    negative = int(
        (x < 0).sum()
    )

    zero = int(
        (x == 0).sum()
    )

    nonzero = (
        positive + negative
    )

    if nonzero == 0:
        return {
            "N": N,
            "positive": positive,
            "negative": negative,
            "zero": zero,
            "z": np.nan,
            "p": np.nan,
        }

    z = (
        (
            positive
            - 0.5 * nonzero
        )
        / math.sqrt(
            0.25 * nonzero
        )
    )

    return {
        "N": N,
        "positive": positive,
        "negative": negative,
        "zero": zero,
        "z": z,
        "p": two_sided_p(z),
    }


# ============================================================
# MACKINLAY CROSS-SECTIONAL SUMMARY
# ============================================================

def mackinlay_summary(
    filings,
    car_col,
    var_col,
):
    x = filings[
        [car_col, var_col]
    ].copy()

    x[car_col] = pd.to_numeric(
        x[car_col],
        errors="coerce",
    )

    x[var_col] = pd.to_numeric(
        x[var_col],
        errors="coerce",
    )

    x = x.dropna()

    N = len(x)

    if N == 0:
        return None

    caar = float(
        x[car_col].mean()
    )

    var_caar = float(
        x[var_col].sum()
        / (N ** 2)
    )

    se = (
        math.sqrt(var_caar)
        if var_caar > 0
        else np.nan
    )

    z = (
        caar / se
        if np.isfinite(se) and se > 0
        else np.nan
    )

    p = (
        two_sided_p(z)
        if np.isfinite(z)
        else np.nan
    )

    sign = sign_test(
        filings,
        car_col,
    )

    return {
        "N": N,
        "CAAR": caar,
        "Var_CAAR": var_caar,
        "SE_CAAR": se,
        "MacKinlay_Z": z,
        "MacKinlay_p": p,
        "Sign_positive": sign["positive"],
        "Sign_negative": sign["negative"],
        "Sign_zero": sign["zero"],
        "Sign_Z": sign["z"],
        "Sign_p": sign["p"],
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("FINAL EVENT STUDY — MACKINLAY + BROWN-WARNER")
    print("=" * 80)

    tone = pd.read_csv(
        TONE_PATH,
        dtype={
            "accession_number": str,
        },
    )

    prices = pd.read_csv(
        PRICE_PATH,
    )

    prices["date"] = pd.to_datetime(
        prices["date"]
    )

    prices["return"] = pd.to_numeric(
        prices["return"],
        errors="coerce",
    )

    print(
        "Tone filings:",
        len(tone),
    )

    print(
        "Price rows:",
        len(prices),
    )

    filings = []
    event_rows = []
    estimation_rows = []

    failures = {}
    failure_rows = []

    for i, filing in tone.iterrows():

        result, event, estimation, status = process_filing(
            filing,
            prices,
        )

        if status == "success":

            filings.append(result)

            event_rows.append(
                event[
                    [
                        "ticker",
                        "accession_number",
                        "filing_date",
                        "event_date",
                        "event_time",
                        "date",
                        "firm_return",
                        "market_return",
                        "expected_return",
                        "ar",
                    ]
                ].copy()
            )

            estimation_rows.append(
                estimation[
                    [
                        "ticker",
                        "accession_number",
                        "filing_date",
                        "event_time",
                        "date",
                        "firm_return",
                        "market_return",
                        "expected_return",
                        "ar",
                    ]
                ].copy()
            )

        else:
            failures[status] = (
                failures.get(status, 0)
                + 1
            )
            failure_rows.append({
                "ticker": filing["ticker"],
                "filing_date": filing["filing_date"],
                "accession_number": filing["accession_number"],
                "event_exclusion_reason": status,
            })

        if (
            (i + 1) % 100
            == 0
        ):
            print(
                f"Processed "
                f"{i + 1}/"
                f"{len(tone)}"
            )

    filing_df = pd.DataFrame(
        filings
    )

    event_df = pd.concat(
        event_rows,
        ignore_index=True,
    ) if event_rows else pd.DataFrame()

    estimation_df = pd.concat(
        estimation_rows,
        ignore_index=True,
    ) if estimation_rows else pd.DataFrame()

    # --------------------------------------------------------
    # Brown-Warner daily results
    # --------------------------------------------------------

    daily_bw, bw_stats = (
        brown_warner_test(
            event_df,
            estimation_df,
        )
        if (
            not event_df.empty
            and not estimation_df.empty
        )
        else (None, None)
    )

    if daily_bw is None:
        daily_bw = pd.DataFrame()
        bw_stats = {}

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summary_rows = []

    for name, (start, end) in CAR_WINDOWS.items():

        car_col = name
        var_col = (
            f"{name}_var"
        )

        result = mackinlay_summary(
            filing_df,
            car_col,
            var_col,
        )

        if result is not None:

            result["window"] = name
            result["window_start"] = start
            result["window_end"] = end
            result["model"] = "market_model"

            summary_rows.append(
                result
            )

    summary_df = pd.DataFrame(
        summary_rows
    )

    # Add Brown-Warner info to the [-5,+5] row.
    if (
        not summary_df.empty
        and bw_stats
    ):

        mask = (
            summary_df["window"]
            == "CAR_m5_p5"
        )

        summary_df.loc[
            mask,
            "Brown_Warner_Z"
        ] = bw_stats[
            "BW_11day_z"
        ]

        summary_df.loc[
            mask,
            "Brown_Warner_p"
        ] = bw_stats[
            "BW_11day_p"
        ]

        summary_df.loc[
            mask,
            "BW_estimation_AAR_mean"
        ] = bw_stats[
            "BW_estimation_AAR_mean"
        ]

        summary_df.loc[
            mask,
            "BW_estimation_AAR_sd"
        ] = bw_stats[
            "BW_estimation_AAR_sd"
        ]

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    filing_df.to_csv(
        FILING_OUT,
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame(failure_rows, columns=[
        "ticker", "filing_date", "accession_number", "event_exclusion_reason",
    ]).to_csv(
        OUT_DIR / "event_exclusions.csv", index=False, encoding="utf-8-sig",
    )

    event_df.to_csv(
        AR_OUT,
        index=False,
        encoding="utf-8-sig",
    )

    estimation_df.to_csv(
        OUT_DIR / "estimation_ar_long.csv",
        index=False,
        encoding="utf-8-sig",
    )

    daily_bw.to_csv(
        DAILY_OUT,
        index=False,
        encoding="utf-8-sig",
    )

    summary_df.to_csv(
        SUMMARY_OUT,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Print final results
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("FINAL EVENT STUDY COMPLETE")
    print("=" * 80)

    print(
        "Successful events:",
        len(filing_df),
    )

    print(
        "Failed events:",
        sum(failures.values()),
    )

    if failures:
        print()
        print("Failures:")
        for k, v in sorted(
            failures.items(),
            key=lambda x: -x[1],
        ):
            print(
                f"  {k}: {v}"
            )

    if not filing_df.empty:

        print()
        print(
            "Mean beta:",
            f"{filing_df['beta'].mean():.6f}",
        )

        print(
            "Mean estimation observations:",
            f"{filing_df['n_estimation'].mean():.2f}",
        )

        print(
            "Events shifted to next trading day:",
            int(
                (
                    filing_df[
                        "event_date_shift"
                    ] == 1
                ).sum()
            ),
        )

    print()
    print("MACKINLAY RESULTS")
    print(
        summary_df.to_string(
            index=False
        )
    )

    if bw_stats:

        print()
        print(
            "BROWN-WARNER [-5,+5]"
        )

        print(
            "  Estimation AAR mean:",
            f"{bw_stats['BW_estimation_AAR_mean']:.8f}",
        )

        print(
            "  Estimation AAR SD:",
            f"{bw_stats['BW_estimation_AAR_sd']:.8f}",
        )

        print(
            "  Z:",
            f"{bw_stats['BW_11day_z']:.6f}",
        )

        print(
            "  p-value:",
            f"{bw_stats['BW_11day_p']:.6g}",
        )

    print()
    print("OUTPUTS")
    print(FILING_OUT)
    print(AR_OUT)
    print(OUT_DIR / "estimation_ar_long.csv")
    print(DAILY_OUT)
    print(SUMMARY_OUT)


if __name__ == "__main__":
    main()
