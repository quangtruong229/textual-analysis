"""Brown–Warner windows, serial-correlation sensitivity, rank test and power."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata


ROOT = Path(__file__).resolve().parents[1]
EVENT = ROOT / "analysis_outputs/event_study"
WINDOWS = {"CAR_m1_p1": (-1, 1), "CAR_0_p3": (0, 3),
           "CAR_m3_p3": (-3, 3), "CAR_m5_p5": (-5, 5)}


def two_sided_p(z: float) -> float:
    return float(2 * norm.sf(abs(z)))


def brown_warner_windows(estimation: pd.DataFrame, event: pd.DataFrame) -> pd.DataFrame:
    est_aar = estimation.groupby("event_time").ar.mean().sort_index()
    event_aar = event.groupby("event_time").ar.mean().sort_index()
    if len(est_aar) != 239 or len(event_aar) != 11:
        raise ValueError("Expected 239 estimation and 11 event relative days")
    sd = float(est_aar.std(ddof=1))
    if sd <= 0:
        raise ValueError("Estimation AAR has zero variance")
    centered = est_aar.to_numpy() - est_aar.mean()
    rhos = []
    for lag in (1, 2, 3):
        rho = float(np.dot(centered[lag:], centered[:-lag]) / np.dot(centered, centered))
        if abs(rho) * np.sqrt(len(centered)) > norm.ppf(.975):
            rhos.append(rho)
        else:
            break
    while len(rhos) < 3:
        rhos.append(0.0)
    # Brown–Warner A.3: use an event-window covariance matrix, only if positive definite.
    matrix = np.fromfunction(lambda i, j: np.where(
        i == j, 1., np.where(abs(i-j) <= 3,
        np.take([0., *rhos], abs(i-j).astype(int).clip(max=3)), 0.)), (11, 11))
    if np.linalg.eigvalsh(matrix).min() <= 0:
        rhos = [0., 0., 0.]
    records = []
    for name, (lo, hi) in WINDOWS.items():
        aar = event_aar.loc[lo:hi]
        length = len(aar)
        numerator = float(aar.sum())
        baseline_se = sd * np.sqrt(length)
        corrected_variance = sd ** 2 * (length + 2 * sum(
            (length-lag) * rho for lag, rho in enumerate(rhos, 1) if lag < length
        ))
        corrected_se = float(np.sqrt(corrected_variance))
        baseline_z = numerator / baseline_se
        corrected_z = numerator / corrected_se
        records.append({"window": name, "window_start": lo, "window_end": hi,
                        "n_event_days": length, "caar": numerator,
                        "estimation_aar_sd": sd, "brown_warner_z": baseline_z,
                        "brown_warner_p": two_sided_p(baseline_z),
                        "rho_1": rhos[0], "rho_2": rhos[1], "rho_3": rhos[2],
                        "autocorr_se": corrected_se, "autocorr_z": corrected_z,
                        "autocorr_p": two_sided_p(corrected_z)})
    return pd.DataFrame(records)


def corrado_daily(estimation: pd.DataFrame, event: pd.DataFrame) -> pd.DataFrame:
    keys = ["ticker", "accession_number"]
    combined = pd.concat([estimation[keys + ["event_time", "ar"]],
                          event[keys + ["event_time", "ar"]]], ignore_index=True)
    lengths = combined.groupby(keys).size()
    if not lengths.eq(250).all():
        raise ValueError("Corrado requires 239 estimation and 11 event AR per filing")
    combined["rank"] = combined.groupby(keys).ar.transform(
        lambda values: rankdata(values.to_numpy(), method="average")
    )
    expected_rank = 125.5
    mean_ranks = combined.groupby("event_time")["rank"].mean()
    est_sd = float(mean_ranks.loc[-244:-6].std(ddof=1))
    if est_sd <= 0:
        raise ValueError("Estimation mean ranks have zero variance")
    output = []
    for day, mean_rank in mean_ranks.loc[-5:5].items():
        z = (float(mean_rank) - expected_rank) / est_sd
        output.append({"event_time": day, "n": len(lengths),
                       "mean_rank": float(mean_rank), "expected_rank": expected_rank,
                       "estimation_rank_sd": est_sd, "corrado_z": z,
                       "corrado_p": two_sided_p(z)})
    return pd.DataFrame(output)


def theoretical_power(tests: pd.DataFrame, effects=(0.0025, 0.005, 0.01)) -> pd.DataFrame:
    """Normal-approximation sensitivity for CAAR, not power of H1 tone regression."""
    critical = norm.ppf(.975)
    rows = []
    for test in tests.itertuples():
        se = test.estimation_aar_sd * np.sqrt(test.n_event_days)
        for effect in effects:
            signal = effect / se
            rows.append({"window": test.window, "assumed_caar": effect,
                         "baseline_se": se, "alpha_two_sided": .05,
                         "theoretical_power": float(norm.sf(critical-signal) + norm.cdf(-critical-signal))})
    return pd.DataFrame(rows)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    estimation_file = EVENT / "estimation_ar_long.csv"
    if not estimation_file.exists():
        raise FileNotFoundError("Estimation AR missing; run python scripts/run_analysis.py")
    estimation = pd.read_csv(estimation_file, dtype={"accession_number": str})
    event = pd.read_csv(EVENT / "event_ar_long.csv", dtype={"accession_number": str})
    tests = brown_warner_windows(estimation, event)
    rank = corrado_daily(estimation, event)
    power = theoretical_power(tests)
    tests.to_csv(EVENT / "extended_window_tests.csv", index=False)
    rank.to_csv(EVENT / "corrado_daily.csv", index=False)
    power.to_csv(EVENT / "theoretical_power.csv", index=False)
    print(tests[["window", "brown_warner_z", "brown_warner_p", "autocorr_z", "autocorr_p"]].to_string(index=False))
    print(f"Corrado day 0 p={rank.loc[rank.event_time.eq(0), 'corrado_p'].item():.6g}")
    print("Power is theoretical for assumed CAAR, not H1 word-power regression.")


if __name__ == "__main__":
    main()
